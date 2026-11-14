// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import {ISystemContract} from "@reactive/src/interfaces/ISystemContract.sol";
import {IReactive} from "@reactive/src/interfaces/IReactive.sol";
import {AbstractReactive} from "@reactive/src/base/AbstractReactive.sol";
import {ILoomEscrowEvents, ILoomBondsEvents, ILoomEscrowCallbacks, ILoomBondsCallbacks} from "./interfaces/ILoom.sol";

/// @title LoomReferee
/// @notice The reactive contract (Reactive Lasna) that runs LOOM.
///
/// It watches two chains at once: the buyer chain, where jobs are paid for and
/// stage commitments land (LoomEscrow on Base Sepolia), and the provider chain,
/// where GPU providers keep their bonds (LoomBonds on Unichain Sepolia). From
/// those events it keeps its own view of every job and every provider, and it
/// alone decides what happens next:
///
///  - schedules each new job onto distinct, bonded providers ranked by the
///    reputation recorded on the provider chain;
///  - counts verifier votes on a dispute and, at quorum, either has the faulty
///    stage wiped and rerouted (then slashes the provider on the other chain),
///    or rejects the challenge;
///  - runs every timer (stage deadlines, challenge windows, vote windows) off
///    Reactive's CRON, subscribing to the clock only while a job is live;
///  - retries any instruction until the destination chain confirms it.
///
/// There is no keeper and no backend: every state change on Base or Unichain
/// after a job is posted is a callback requested here.
contract LoomReferee is AbstractReactive, ILoomEscrowEvents, ILoomBondsEvents {
    // ---------------------------------------------------------------- types
    enum Phase {
        None,
        Assigning, // providers chosen, waiting for the escrow to confirm
        Running, // stages executing; `deadline` is the current stage's deadline
        Proposed, // result committed; `deadline` is the end of the challenge window
        Disputed, // challenge open; `deadline` is the end of the vote window
        Resolving, // verdict sent, waiting for the escrow to confirm
        Done
    }

    struct JobState {
        Phase phase;
        uint8 nStages;
        uint8 nextStage;
        uint8 disputedStage;
        uint8 votesFaulty;
        uint8 votesHonest;
        uint32 round;
        uint64 deadline;
        uint64 lastAttempt;
        address buyer;
        address challenger;
        address accused;
    }

    struct ProviderState {
        bool known;
        bool exiting;
        bool barred; // proven faulty: never scheduled again
        uint128 bond;
        uint32 jobsDone;
        uint32 faults;
        uint32 timeouts;
    }

    /// @dev An instruction to the buyer chain that must be confirmed by an event.
    /// Stored as a code plus one address (one slot) and re-encoded on retry.
    enum Action {
        None,
        Assign,
        ResolveFault,
        Reject,
        Refund
    }

    struct Pending {
        Action action;
        address arg; // replacement provider for ResolveFault
    }

    // ------------------------------------------------------------ constants
    address internal constant CRON_SOURCE = 0x0000000000000000000000000000000000fffFfF;
    /// @dev Cron10: every 10 Reactive blocks (~10 s on Omni).
    uint256 internal constant CRON10_TOPIC_0 = 0x04463f7c1651e6b9774d7f85c85bb94654e3c46ca79b0c16fb16d4183307b687;

    uint64 internal constant ESCROW_GAS = 600_000;
    uint64 internal constant BONDS_GAS = 300_000;
    /// @dev Destination clocks can lag Reactive's; wait this long past a deadline before acting.
    uint64 public constant GRACE = 4;
    /// @dev Minimum gap between two attempts at the same timed action.
    uint64 public constant RETRY = 30;
    /// @dev Bounded work per cron tick, so a tick never approaches the 900k reactive gas cap.
    uint256 public constant MAX_PER_TICK = 8;

    // ------------------------------------------------------------ config
    address public immutable owner;
    uint256 public immutable escrowChainId;
    uint256 public immutable bondsChainId;
    uint256 public immutable minBond;
    uint8 public immutable quorum;
    address public escrow;
    address public bonds;

    // ------------------------------------------------------------- state
    mapping(uint256 => JobState) public jobState;
    mapping(uint256 => address[]) internal _pipeline;
    mapping(uint256 => Pending) internal _pending;
    mapping(uint256 => mapping(uint32 => mapping(address => bool))) public counted;

    address[] public providerList;
    mapping(address => ProviderState) public providerState;

    uint256[] internal _watch;
    mapping(uint256 => uint256) internal _watchPos; // 1-based index into _watch
    bool public cronOn;

    // ------------------------------------------------------------- events
    event ProvidersSelected(uint256 indexed jobId, address[] providers);
    event NoProviders(uint256 indexed jobId, uint8 needed, uint256 available);
    event VoteCounted(
        uint256 indexed jobId, address indexed verifier, uint32 round, bool faulty, uint8 votesFaulty, uint8 votesHonest
    );
    event QuorumReached(uint256 indexed jobId, uint32 round, bool faulty, address accused, address replacement);
    event TimerFired(uint256 indexed jobId, Phase phase, uint64 deadline);
    event CallbackSent(uint256 indexed jobId, uint256 indexed chainId, bytes4 indexed selector);
    event CronToggled(bool on);

    error NotOwner();
    error AlreadyConfigured();

    constructor(uint256 escrowChainId_, uint256 bondsChainId_, uint256 minBond_, uint8 quorum_) payable {
        owner = msg.sender;
        escrowChainId = escrowChainId_;
        bondsChainId = bondsChainId_;
        minBond = minBond_;
        quorum = quorum_;
    }

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    // ------------------------------------------------------------- admin
    /// @notice One-time wiring. The destination contracts are deployed after this
    /// one (they need its address to authenticate callbacks), so subscriptions
    /// start here rather than in the constructor.
    function setTargets(address escrow_, address bonds_) external onlyOwner {
        if (escrow != address(0)) revert AlreadyConfigured();
        escrow = escrow_;
        bonds = bonds_;

        bytes32[13] memory escrowTopics = [
            JobCreated.selector,
            ProvidersAssigned.selector,
            StageCommitted.selector,
            ResultProposed.selector,
            Challenged.selector,
            VerdictVote.selector,
            FaultResolved.selector,
            StageReassigned.selector,
            StageTimedOut.selector,
            ChallengeRejected.selector,
            ChallengeVoided.selector,
            JobSettled.selector,
            JobRefunded.selector
        ];
        for (uint256 i; i < escrowTopics.length; ++i) {
            _sub(escrowChainId, escrow_, uint256(escrowTopics[i]));
        }

        bytes32[6] memory bondTopics = [
            ProviderBonded.selector,
            ProviderExiting.selector,
            ProviderWithdrawn.selector,
            ProviderSlashed.selector,
            ProviderTimedOut.selector,
            ReputationUpdated.selector
        ];
        for (uint256 i; i < bondTopics.length; ++i) {
            _sub(bondsChainId, bonds_, uint256(bondTopics[i]));
        }
    }

    /// @notice Anyone may settle this contract's debt from its own balance.
    function coverDebt() external {
        _coverDebt();
    }

    function withdraw(uint256 amount_) external onlyOwner {
        (bool ok,) = payable(owner).call{value: amount_}("");
        require(ok);
    }

    // ------------------------------------------------------------ react
    /// @inheritdoc IReactive
    function react(LogRecord calldata log_) external onlySystem {
        if (log_.contractAddress == CRON_SOURCE && log_.topic0 == CRON10_TOPIC_0) {
            _onCron();
        } else if (log_.chainId == escrowChainId && log_.contractAddress == escrow) {
            _onEscrow(log_);
        } else if (log_.chainId == bondsChainId && log_.contractAddress == bonds) {
            _onBonds(log_);
        }
        // Anything else falls through at no extra cost (reverting would still be billed).
    }

    // ------------------------------------------------- buyer chain events
    function _onEscrow(LogRecord calldata log_) internal {
        bytes32 t = bytes32(log_.topic0);
        uint256 jobId = log_.topic1;
        JobState storage st = jobState[jobId];

        if (t == JobCreated.selector) {
            (, uint8 nStages,,) = abi.decode(log_.data, (uint256, uint8, bytes32, string));
            if (st.phase != Phase.None) return;
            st.buyer = address(uint160(log_.topic2));
            st.nStages = nStages;
            address[] memory chosen = _select(nStages);
            if (chosen.length < nStages) {
                emit NoProviders(jobId, nStages, chosen.length);
                _await(jobId, st, Phase.Resolving, Action.Refund, address(0));
                return;
            }
            _pipeline[jobId] = chosen;
            emit ProvidersSelected(jobId, chosen);
            _await(jobId, st, Phase.Assigning, Action.Assign, address(0));
        } else if (t == ProvidersAssigned.selector) {
            (address[] memory provs, uint64 deadline) = abi.decode(log_.data, (address[], uint64));
            _pipeline[jobId] = provs;
            st.nextStage = 0;
            _arm(jobId, st, Phase.Running, deadline);
        } else if (t == StageCommitted.selector) {
            (,,, uint64 nextDeadline) = abi.decode(log_.data, (bytes32, bytes32, string, uint64));
            if (nextDeadline != 0) {
                st.nextStage = uint8(log_.topic2) + 1;
                _arm(jobId, st, Phase.Running, nextDeadline);
            }
        } else if (t == ResultProposed.selector) {
            (, uint64 challengeDeadline) = abi.decode(log_.data, (bytes32, uint64));
            st.nextStage = st.nStages;
            _arm(jobId, st, Phase.Proposed, challengeDeadline);
        } else if (t == Challenged.selector) {
            (uint8 stage, uint32 round,,, uint64 voteDeadline) =
                abi.decode(log_.data, (uint8, uint32, bytes32, bytes32, uint64));
            st.challenger = address(uint160(log_.topic2));
            st.accused = address(uint160(log_.topic3));
            st.disputedStage = stage;
            st.round = round;
            st.votesFaulty = 0;
            st.votesHonest = 0;
            _arm(jobId, st, Phase.Disputed, voteDeadline);
        } else if (t == VerdictVote.selector) {
            _onVote(jobId, st, address(uint160(log_.topic2)), log_.data);
        } else if (t == FaultResolved.selector) {
            // The escrow has wiped the faulty stage; now punish on the provider chain.
            (, address buyer) = abi.decode(log_.data, (uint8, address));
            address faulty = address(uint160(log_.topic2));
            address challenger = address(uint160(log_.topic3));
            _call(
                jobId,
                bondsChainId,
                bonds,
                BONDS_GAS,
                abi.encodeCall(ILoomBondsCallbacks.slash, (address(0), faulty, jobId, challenger, buyer))
            );
        } else if (t == StageReassigned.selector) {
            (, uint64 deadline) = abi.decode(log_.data, (address, uint64));
            uint8 stage = uint8(log_.topic2);
            _pipeline[jobId][stage] = address(uint160(log_.topic3));
            st.nextStage = stage;
            _arm(jobId, st, Phase.Running, deadline);
        } else if (t == StageTimedOut.selector) {
            address buyer = abi.decode(log_.data, (address));
            address provider = address(uint160(log_.topic3));
            _call(
                jobId,
                bondsChainId,
                bonds,
                BONDS_GAS,
                abi.encodeCall(ILoomBondsCallbacks.recordTimeout, (address(0), provider, jobId, buyer))
            );
        } else if (t == ChallengeRejected.selector) {
            (, uint64 challengeDeadline) = abi.decode(log_.data, (uint256, uint64));
            _arm(jobId, st, Phase.Proposed, challengeDeadline);
        } else if (t == ChallengeVoided.selector) {
            uint64 challengeDeadline = abi.decode(log_.data, (uint64));
            _arm(jobId, st, Phase.Proposed, challengeDeadline);
        } else if (t == JobSettled.selector) {
            (, address[] memory provs,) = abi.decode(log_.data, (bytes32, address[], uint256[]));
            _finish(jobId, st);
            _call(
                jobId,
                bondsChainId,
                bonds,
                BONDS_GAS,
                abi.encodeCall(ILoomBondsCallbacks.recordSuccess, (address(0), jobId, provs))
            );
        } else if (t == JobRefunded.selector) {
            _finish(jobId, st);
        }
    }

    function _onVote(uint256 jobId_, JobState storage st, address verifier_, bytes calldata data_) internal {
        (uint32 round, bool faulty) = abi.decode(data_, (uint32, bool));
        if (st.phase != Phase.Disputed || round != st.round || counted[jobId_][round][verifier_]) return;
        counted[jobId_][round][verifier_] = true;
        if (faulty) st.votesFaulty += 1;
        else st.votesHonest += 1;
        emit VoteCounted(jobId_, verifier_, round, faulty, st.votesFaulty, st.votesHonest);

        if (st.votesFaulty >= quorum) {
            // Stop scheduling the accused right away; the slash itself follows
            // once the buyer chain confirms the fault.
            providerState[st.accused].barred = true;
            address replacement = _pickReplacement(jobId_);
            emit QuorumReached(jobId_, round, true, st.accused, replacement);
            _await(jobId_, st, Phase.Resolving, Action.ResolveFault, replacement);
        } else if (st.votesHonest >= quorum) {
            emit QuorumReached(jobId_, round, false, st.accused, address(0));
            _await(jobId_, st, Phase.Resolving, Action.Reject, address(0));
        }
    }

    // ---------------------------------------------- provider chain events
    function _onBonds(LogRecord calldata log_) internal {
        bytes32 t = bytes32(log_.topic0);
        address provider = address(uint160(log_.topic1));
        ProviderState storage p = providerState[provider];
        if (!p.known) {
            p.known = true;
            providerList.push(provider);
        }

        if (t == ProviderBonded.selector) {
            (uint256 bond,) = abi.decode(log_.data, (uint256, string));
            p.bond = uint128(bond);
        } else if (t == ProviderExiting.selector) {
            p.exiting = true;
        } else if (t == ProviderWithdrawn.selector || t == ProviderSlashed.selector) {
            p.bond = 0;
        } else if (t == ProviderTimedOut.selector) {
            (, uint256 bondLeft) = abi.decode(log_.data, (uint256, uint256));
            p.bond = uint128(bondLeft);
        } else if (t == ReputationUpdated.selector) {
            (uint32 jobsDone, uint32 faults, uint32 timeouts) = abi.decode(log_.data, (uint32, uint32, uint32));
            p.jobsDone = jobsDone;
            p.faults = faults;
            p.timeouts = timeouts;
        }
    }

    // ------------------------------------------------------------- cron
    function _onCron() internal {
        uint64 nowTs = uint64(block.timestamp);
        uint256 work;
        // Walk backwards so _finish() can swap-remove safely.
        for (uint256 i = _watch.length; i > 0 && work < MAX_PER_TICK; --i) {
            uint256 jobId = _watch[i - 1];
            JobState storage st = jobState[jobId];
            if (nowTs < st.deadline + GRACE || nowTs < st.lastAttempt + RETRY) continue;
            st.lastAttempt = nowTs;
            ++work;
            emit TimerFired(jobId, st.phase, st.deadline);

            if (st.phase == Phase.Running) {
                // A stage missed its deadline: reroute it to the best standby provider.
                address replacement = _pickReplacement(jobId);
                _call(
                    jobId,
                    escrowChainId,
                    escrow,
                    ESCROW_GAS,
                    abi.encodeCall(ILoomEscrowCallbacks.timeoutStage, (address(0), jobId, st.nextStage, replacement))
                );
            } else if (st.phase == Phase.Proposed) {
                // Challenge window closed unchallenged: pay everyone.
                _call(
                    jobId,
                    escrowChainId,
                    escrow,
                    ESCROW_GAS,
                    abi.encodeCall(ILoomEscrowCallbacks.settle, (address(0), jobId))
                );
            } else if (st.phase == Phase.Disputed) {
                // Vote window closed without quorum: void the challenge.
                _call(
                    jobId,
                    escrowChainId,
                    escrow,
                    ESCROW_GAS,
                    abi.encodeCall(ILoomEscrowCallbacks.voidChallenge, (address(0), jobId))
                );
            } else if (st.phase == Phase.Assigning || st.phase == Phase.Resolving) {
                // An instruction was not confirmed yet: send it again (destinations are idempotent).
                _call(jobId, escrowChainId, escrow, ESCROW_GAS, _payloadFor(jobId, _pending[jobId]));
            }
        }
    }

    // ---------------------------------------------------------- scheduling
    function _score(ProviderState storage p) internal view returns (int256) {
        return int256(uint256(p.jobsDone)) - 10 * int256(uint256(p.faults)) - 3 * int256(uint256(p.timeouts));
    }

    function _eligible(ProviderState storage p) internal view returns (bool) {
        return !p.exiting && !p.barred && p.bond >= minBond;
    }

    /// @dev Pick up to `n` distinct eligible providers, best reputation first.
    function _select(uint8 n_) internal view returns (address[] memory chosen) {
        address[] memory picks = new address[](n_);
        uint256 found;
        uint256 len = providerList.length;
        for (uint256 k; k < n_; ++k) {
            address best;
            int256 bestScore = type(int256).min;
            for (uint256 i; i < len; ++i) {
                address a = providerList[i];
                ProviderState storage p = providerState[a];
                if (!_eligible(p) || _contains(picks, found, a)) continue;
                int256 s = _score(p);
                if (s > bestScore) {
                    best = a;
                    bestScore = s;
                }
            }
            if (best == address(0)) break;
            picks[found++] = best;
        }
        chosen = new address[](found);
        for (uint256 i; i < found; ++i) {
            chosen[i] = picks[i];
        }
    }

    /// @dev Best eligible provider not already in this job's pipeline (zero if none).
    function _pickReplacement(uint256 jobId_) internal view returns (address best) {
        address[] storage pipe = _pipeline[jobId_];
        int256 bestScore = type(int256).min;
        for (uint256 i; i < providerList.length; ++i) {
            address a = providerList[i];
            ProviderState storage p = providerState[a];
            if (!_eligible(p)) continue;
            bool inPipe;
            for (uint256 j; j < pipe.length; ++j) {
                if (pipe[j] == a) {
                    inPipe = true;
                    break;
                }
            }
            if (inPipe) continue;
            int256 s = _score(p);
            if (s > bestScore) {
                best = a;
                bestScore = s;
            }
        }
    }

    function _contains(address[] memory arr_, uint256 len_, address a_) internal pure returns (bool) {
        for (uint256 i; i < len_; ++i) {
            if (arr_[i] == a_) return true;
        }
        return false;
    }

    // ------------------------------------------------- timers + callbacks
    /// @dev Enter a timed phase. `deadline_` is measured on the destination chain's clock.
    function _arm(uint256 jobId_, JobState storage st, Phase phase_, uint64 deadline_) internal {
        st.phase = phase_;
        st.deadline = deadline_;
        st.lastAttempt = 0;
        _watchAdd(jobId_);
    }

    /// @dev Send an instruction to the escrow and keep retrying it from cron until
    /// the matching confirmation event moves the job out of `phase_`.
    function _await(uint256 jobId_, JobState storage st, Phase phase_, Action action_, address arg_) internal {
        Pending memory pd = Pending(action_, arg_);
        _pending[jobId_] = pd;
        st.phase = phase_;
        st.deadline = uint64(block.timestamp) + RETRY;
        st.lastAttempt = uint64(block.timestamp);
        _watchAdd(jobId_);
        _call(jobId_, escrowChainId, escrow, ESCROW_GAS, _payloadFor(jobId_, pd));
    }

    function _payloadFor(uint256 jobId_, Pending memory pd_) internal view returns (bytes memory) {
        if (pd_.action == Action.Assign) {
            return abi.encodeCall(ILoomEscrowCallbacks.assignProviders, (address(0), jobId_, _pipeline[jobId_]));
        }
        if (pd_.action == Action.ResolveFault) {
            return abi.encodeCall(ILoomEscrowCallbacks.resolveFault, (address(0), jobId_, pd_.arg));
        }
        if (pd_.action == Action.Reject) {
            return abi.encodeCall(ILoomEscrowCallbacks.rejectChallenge, (address(0), jobId_));
        }
        return abi.encodeCall(ILoomEscrowCallbacks.refund, (address(0), jobId_));
    }

    function _finish(uint256 jobId_, JobState storage st) internal {
        st.phase = Phase.Done;
        delete _pending[jobId_];
        _watchRemove(jobId_);
    }

    function _call(uint256 jobId_, uint256 chainId_, address target_, uint64 gas_, bytes memory payload_) internal {
        SYSTEM.requestCallbackV_1_0(
            ISystemContract.CallbackConfiguration_V_1_0({
                chainId: chainId_, recipient: target_, gasLimit: gas_, payload: payload_
            })
        );
        // forge-lint: disable-next-line(unsafe-typecast)
        emit CallbackSent(jobId_, chainId_, bytes4(payload_)); // the selector
    }

    // Cron is billed on every tick, so LOOM only listens to the clock while
    // some job actually has a timer running.
    function _watchAdd(uint256 jobId_) internal {
        if (_watchPos[jobId_] != 0) return;
        _watch.push(jobId_);
        _watchPos[jobId_] = _watch.length;
        if (!cronOn) {
            cronOn = true;
            _sub(block.chainid, CRON_SOURCE, CRON10_TOPIC_0);
            emit CronToggled(true);
        }
    }

    function _watchRemove(uint256 jobId_) internal {
        uint256 pos = _watchPos[jobId_];
        if (pos == 0) return;
        uint256 last = _watch[_watch.length - 1];
        _watch[pos - 1] = last;
        _watchPos[last] = pos;
        _watch.pop();
        delete _watchPos[jobId_];
        if (_watch.length == 0 && cronOn) {
            cronOn = false;
            SYSTEM.unsubscribe(
                block.chainid, CRON_SOURCE, CRON10_TOPIC_0, REACTIVE_IGNORE, REACTIVE_IGNORE, REACTIVE_IGNORE
            );
            emit CronToggled(false);
        }
    }

    function _sub(uint256 chainId_, address contract_, uint256 topic0_) internal {
        SYSTEM.subscribe(chainId_, contract_, topic0_, REACTIVE_IGNORE, REACTIVE_IGNORE, REACTIVE_IGNORE);
    }

    // ------------------------------------------------------------- views
    function pipelineOf(uint256 jobId_) external view returns (address[] memory) {
        return _pipeline[jobId_];
    }

    function watching() external view returns (uint256[] memory) {
        return _watch;
    }

    function providerCount() external view returns (uint256) {
        return providerList.length;
    }
}
