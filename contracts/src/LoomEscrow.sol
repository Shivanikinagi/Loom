// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import {IPayable} from "@reactive/src/interfaces/IPayable.sol";
import {LoomCallbackBase} from "./LoomCallbackBase.sol";
import {ILoomEscrowEvents, ILoomEscrowCallbacks} from "./interfaces/ILoom.sol";

/// @title LoomEscrow
/// @notice Buyer-side contract (Base Sepolia). Holds payment for a pipelined
/// inference job, records each stage's input/output commitment, accepts
/// challenges and verifier votes, and executes whatever LoomReferee decides.
///
/// Nothing here decides *who* runs a stage, *when* a timer expired, or *whether*
/// a quorum was reached: that logic lives in the reactive contract. This
/// contract only checks that each instruction is still valid on this chain
/// (status, deadlines measured by this chain's clock) and moves the money.
contract LoomEscrow is LoomCallbackBase, ILoomEscrowEvents, ILoomEscrowCallbacks {
    enum Status {
        None,
        Open, // waiting for the referee to assign providers
        Running, // stages are being executed and committed
        Proposed, // final result committed, challenge window open
        Disputed, // a challenge is being voted on
        Settled,
        Refunded
    }

    struct Job {
        address buyer;
        uint96 payment;
        Status status;
        uint8 nStages;
        uint8 nextStage;
        uint8 disputedStage;
        uint32 round;
        uint32 stageTimeout;
        uint32 challengeWindow;
        uint64 stageDeadline;
        uint64 challengeDeadline;
        uint64 voteDeadline;
        address challenger;
        uint96 challengeBond;
        bytes32 datasetHash;
    }

    struct Commit {
        bytes32 inHash;
        bytes32 outHash;
    }

    error NotOwner();
    error BadJob();
    error BadStatus(Status status);
    error NotAssignedProvider(address caller, address expected);
    error WrongStage(uint8 got, uint8 expected);
    error BrokenChain(bytes32 inHash, bytes32 expected);
    error ChallengeClosed();
    error BondTooSmall(uint256 sent, uint256 required);
    error NothingToDispute();
    error NotVerifier();
    error AlreadyVoted();
    error VotingClosed();

    uint8 public constant MAX_STAGES = 8;
    uint32 public constant VOTE_WINDOW = 120;

    address public owner;
    uint256 public minChallengeBond;
    uint256 public nextJobId = 1;
    uint256 internal lockedFunds; // payments + challenge bonds currently held

    mapping(uint256 => Job) public jobs;
    mapping(uint256 => address[]) internal _providers;
    mapping(uint256 => uint8[]) internal _layers;
    mapping(uint256 => mapping(uint8 => Commit)) public commits;
    mapping(address => bool) public isVerifier;
    mapping(uint256 => mapping(uint32 => mapping(address => bool))) public voted;

    event VerifierSet(address indexed verifier, bool enabled);

    constructor(IPayable callbackProxy_, address referee_, uint256 minChallengeBond_)
        payable
        LoomCallbackBase(callbackProxy_, referee_)
    {
        owner = msg.sender;
        minChallengeBond = minChallengeBond_;
    }

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    // ---------------------------------------------------------------- admin
    function setVerifier(address verifier_, bool enabled_) external onlyOwner {
        isVerifier[verifier_] = enabled_;
        emit VerifierSet(verifier_, enabled_);
    }

    function transferOwnership(address owner_) external onlyOwner {
        owner = owner_;
    }

    // ---------------------------------------------------------------- buyer
    /// @notice Post a job. `layers[i]` is how many model layers stage i runs;
    /// stage i is paid `payment * layers[i] / sum(layers)`.
    function createJob(
        bytes32 datasetHash_,
        string calldata datasetURI_,
        uint8[] calldata layers_,
        uint32 stageTimeout_,
        uint32 challengeWindow_
    ) external payable returns (uint256 jobId) {
        uint256 n = layers_.length;
        if (msg.value == 0 || msg.value > type(uint96).max || n == 0 || n > MAX_STAGES) revert BadJob();
        if (stageTimeout_ == 0 || challengeWindow_ == 0) revert BadJob();
        for (uint256 i; i < n; ++i) {
            if (layers_[i] == 0) revert BadJob();
        }

        jobId = nextJobId++;
        Job storage j = jobs[jobId];
        j.buyer = msg.sender;
        j.payment = uint96(msg.value);
        j.status = Status.Open;
        j.nStages = uint8(n);
        j.stageTimeout = stageTimeout_;
        j.challengeWindow = challengeWindow_;
        j.datasetHash = datasetHash_;
        _layers[jobId] = layers_;
        lockedFunds += msg.value;

        emit JobCreated(jobId, msg.sender, msg.value, uint8(n), datasetHash_, datasetURI_);
    }

    // ------------------------------------------------------------ providers
    /// @notice Commit stage output. The input must be the previous stage's output
    /// (or the dataset for stage 0), so the commitments form an unbroken chain.
    function commitStage(uint256 jobId_, uint8 stage_, bytes32 inHash_, bytes32 outHash_, string calldata uri_)
        external
    {
        Job storage j = jobs[jobId_];
        if (j.status != Status.Running) revert BadStatus(j.status);
        if (stage_ != j.nextStage) revert WrongStage(stage_, j.nextStage);
        address expected = _providers[jobId_][stage_];
        if (msg.sender != expected) revert NotAssignedProvider(msg.sender, expected);
        bytes32 expectedIn = stage_ == 0 ? j.datasetHash : commits[jobId_][stage_ - 1].outHash;
        if (inHash_ != expectedIn) revert BrokenChain(inHash_, expectedIn);

        commits[jobId_][stage_] = Commit(inHash_, outHash_);
        j.nextStage = stage_ + 1;

        if (j.nextStage == j.nStages) {
            j.status = Status.Proposed;
            j.challengeDeadline = uint64(block.timestamp) + j.challengeWindow;
            emit StageCommitted(jobId_, stage_, msg.sender, inHash_, outHash_, uri_, 0);
            emit ResultProposed(jobId_, outHash_, j.challengeDeadline);
        } else {
            j.stageDeadline = uint64(block.timestamp) + j.stageTimeout;
            emit StageCommitted(jobId_, stage_, msg.sender, inHash_, outHash_, uri_, j.stageDeadline);
        }
    }

    // ----------------------------------------------------------- challengers
    /// @notice Dispute a proposed result by submitting your own recomputed output
    /// hash for every stage. The first stage where your trace diverges from the
    /// committed one is the disputed stage: its input is agreed by both sides, so
    /// verifiers only need to re-run that single stage.
    function challenge(uint256 jobId_, bytes32[] calldata claimedOut_) external payable {
        Job storage j = jobs[jobId_];
        if (j.status != Status.Proposed) revert BadStatus(j.status);
        if (block.timestamp >= j.challengeDeadline) revert ChallengeClosed();
        if (msg.value < minChallengeBond || msg.value > type(uint96).max) {
            revert BondTooSmall(msg.value, minChallengeBond);
        }
        if (claimedOut_.length != j.nStages) revert BadJob();

        uint8 d = type(uint8).max;
        for (uint8 i; i < j.nStages; ++i) {
            if (claimedOut_[i] != commits[jobId_][i].outHash) {
                d = i;
                break;
            }
        }
        if (d == type(uint8).max) revert NothingToDispute();

        j.status = Status.Disputed;
        j.disputedStage = d;
        j.round += 1;
        j.challenger = msg.sender;
        j.challengeBond = uint96(msg.value);
        j.voteDeadline = uint64(block.timestamp) + VOTE_WINDOW;
        lockedFunds += msg.value;

        emit Challenged(
            jobId_,
            msg.sender,
            _providers[jobId_][d],
            d,
            j.round,
            commits[jobId_][d].outHash,
            claimedOut_[d],
            j.voteDeadline
        );
    }

    // ------------------------------------------------------------- verifiers
    /// @notice A verifier re-ran the disputed stage and reports whether the
    /// provider's committed output is wrong. Votes are only recorded here;
    /// LoomReferee counts them and decides.
    function vote(uint256 jobId_, uint32 round_, bool faulty_) external {
        if (!isVerifier[msg.sender]) revert NotVerifier();
        Job storage j = jobs[jobId_];
        if (j.status != Status.Disputed || round_ != j.round) revert BadStatus(j.status);
        if (block.timestamp >= j.voteDeadline) revert VotingClosed();
        if (voted[jobId_][round_][msg.sender]) revert AlreadyVoted();
        voted[jobId_][round_][msg.sender] = true;
        emit VerdictVote(jobId_, msg.sender, round_, faulty_);
    }

    // ------------------------------------------------- referee callbacks
    // Each callback re-checks its preconditions against this chain's state and
    // clock. A stale or duplicate instruction is ignored with an event instead
    // of reverting, so it never wastes a failed callback.

    function assignProviders(address rvm_, uint256 jobId_, address[] calldata providers_) external onlyReferee(rvm_) {
        Job storage j = jobs[jobId_];
        if (j.status != Status.Open) return _ignore(jobId_, "not open");
        if (providers_.length != j.nStages) return _ignore(jobId_, "stage count");
        _providers[jobId_] = providers_;
        j.status = Status.Running;
        j.nextStage = 0;
        j.stageDeadline = uint64(block.timestamp) + j.stageTimeout;
        emit ProvidersAssigned(jobId_, providers_, j.stageDeadline);
    }

    function settle(address rvm_, uint256 jobId_) external onlyReferee(rvm_) {
        Job storage j = jobs[jobId_];
        if (j.status != Status.Proposed) return _ignore(jobId_, "not proposed");
        if (block.timestamp < j.challengeDeadline) return _ignore(jobId_, "window open");

        j.status = Status.Settled;
        uint256 payment = j.payment;
        lockedFunds -= payment;

        uint8[] storage layers = _layers[jobId_];
        uint256 total;
        for (uint256 i; i < layers.length; ++i) {
            total += layers[i];
        }
        address[] memory provs = _providers[jobId_];
        uint256[] memory amounts = new uint256[](provs.length);
        uint256 paid;
        for (uint256 i; i < provs.length; ++i) {
            amounts[i] = i == provs.length - 1 ? payment - paid : (payment * layers[i]) / total;
            paid += amounts[i];
            _send(provs[i], amounts[i]);
        }
        emit JobSettled(jobId_, commits[jobId_][j.nStages - 1].outHash, provs, amounts);
    }

    function timeoutStage(address rvm_, uint256 jobId_, uint8 stage_, address replacement_) external onlyReferee(rvm_) {
        Job storage j = jobs[jobId_];
        if (j.status != Status.Running || j.nextStage != stage_) return _ignore(jobId_, "stage moved on");
        if (block.timestamp < j.stageDeadline) return _ignore(jobId_, "not expired");

        address old = _providers[jobId_][stage_];
        emit StageTimedOut(jobId_, stage_, old, j.buyer);
        _reassign(jobId_, j, stage_, old, replacement_);
    }

    function resolveFault(address rvm_, uint256 jobId_, address replacement_) external onlyReferee(rvm_) {
        Job storage j = jobs[jobId_];
        if (j.status != Status.Disputed) return _ignore(jobId_, "not disputed");

        uint8 d = j.disputedStage;
        address faulty = _providers[jobId_][d];
        address challenger = j.challenger;
        uint256 bond = j.challengeBond;
        _clearChallenge(j);
        _send(challenger, bond); // the challenger was right: bond back (bounty is paid from the slash)

        emit FaultResolved(jobId_, faulty, challenger, d, j.buyer);
        // Wipe the faulty stage and everything computed on top of it.
        for (uint8 i = d; i < j.nStages; ++i) {
            delete commits[jobId_][i];
        }
        j.status = Status.Running;
        _reassign(jobId_, j, d, faulty, replacement_);
    }

    function rejectChallenge(address rvm_, uint256 jobId_) external onlyReferee(rvm_) {
        Job storage j = jobs[jobId_];
        if (j.status != Status.Disputed) return _ignore(jobId_, "not disputed");
        address accused = _providers[jobId_][j.disputedStage];
        address challenger = j.challenger;
        uint256 bond = j.challengeBond;
        _clearChallenge(j);
        j.status = Status.Proposed;
        _send(accused, bond); // frivolous challenge: the falsely accused provider keeps the bond
        emit ChallengeRejected(jobId_, challenger, accused, bond, j.challengeDeadline);
    }

    function voidChallenge(address rvm_, uint256 jobId_) external onlyReferee(rvm_) {
        Job storage j = jobs[jobId_];
        if (j.status != Status.Disputed) return _ignore(jobId_, "not disputed");
        if (block.timestamp < j.voteDeadline) return _ignore(jobId_, "voting open");
        address challenger = j.challenger;
        uint256 bond = j.challengeBond;
        _clearChallenge(j);
        j.status = Status.Proposed;
        _send(challenger, bond); // no quorum: nobody is punished
        emit ChallengeVoided(jobId_, challenger, j.challengeDeadline);
    }

    function refund(address rvm_, uint256 jobId_) external onlyReferee(rvm_) {
        Job storage j = jobs[jobId_];
        if (j.status != Status.Open) return _ignore(jobId_, "not open");
        _refund(jobId_, j);
    }

    // ------------------------------------------------------------ internals
    function _reassign(uint256 jobId_, Job storage j, uint8 stage_, address old_, address replacement_) private {
        if (replacement_ == address(0)) {
            // No standby provider left: the buyer gets everything back.
            _refund(jobId_, j);
            return;
        }
        _providers[jobId_][stage_] = replacement_;
        j.nextStage = stage_;
        j.stageDeadline = uint64(block.timestamp) + j.stageTimeout;
        emit StageReassigned(jobId_, stage_, replacement_, old_, j.stageDeadline);
    }

    function _refund(uint256 jobId_, Job storage j) private {
        j.status = Status.Refunded;
        uint256 amount = j.payment;
        lockedFunds -= amount;
        _send(j.buyer, amount);
        emit JobRefunded(jobId_, j.buyer, amount);
    }

    function _clearChallenge(Job storage j) private {
        lockedFunds -= j.challengeBond;
        j.challenger = address(0);
        j.challengeBond = 0;
    }

    function _ignore(uint256 jobId_, string memory reason_) private {
        emit CallbackIgnored(jobId_, msg.sig, reason_);
    }

    // ----------------------------------------------------------------- views
    function locked() public view override returns (uint256) {
        return lockedFunds + totalCredits;
    }

    function providersOf(uint256 jobId_) external view returns (address[] memory) {
        return _providers[jobId_];
    }

    function layersOf(uint256 jobId_) external view returns (uint8[] memory) {
        return _layers[jobId_];
    }
}
