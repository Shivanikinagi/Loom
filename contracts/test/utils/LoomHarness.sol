// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import {Test, Vm} from "forge-std/Test.sol";
import {IPayable} from "@reactive/src/interfaces/IPayable.sol";
import {IReactive} from "@reactive/src/interfaces/IReactive.sol";
import {LoomEscrow} from "../../src/LoomEscrow.sol";
import {LoomBonds} from "../../src/LoomBonds.sol";
import {LoomReferee} from "../../src/LoomReferee.sol";
import {MockSystem} from "./MockSystem.sol";

/// @notice Runs the whole LOOM loop inside one EVM: logs emitted by the escrow
/// ("Base Sepolia") and bonds ("Unichain Sepolia") are delivered to the
/// referee's react() as the system contract would, and every callback the
/// referee requests is executed through that chain's callback proxy with the
/// referee's address injected as the first argument.
abstract contract LoomHarness is Test {
    address internal constant SYSTEM = 0x8888888888888888888888888888888888888888;
    address internal constant CRON_SOURCE = 0x0000000000000000000000000000000000fffFfF;
    uint256 internal constant CRON10 = 0x04463f7c1651e6b9774d7f85c85bb94654e3c46ca79b0c16fb16d4183307b687;

    uint256 internal constant BASE = 84532;
    uint256 internal constant UNICHAIN = 1301;

    uint256 internal constant MIN_BOND = 0.05 ether;
    uint256 internal constant TIMEOUT_PENALTY = 0.005 ether;
    uint256 internal constant CHALLENGE_BOND = 0.01 ether;
    uint32 internal constant STAGE_TIMEOUT = 300;
    uint32 internal constant CHALLENGE_WINDOW = 180;

    MockSystem internal sys;
    LoomReferee internal referee;
    LoomEscrow internal escrow;
    LoomBonds internal bonds;
    address internal baseProxy = makeAddr("baseCallbackProxy");
    address internal uniProxy = makeAddr("unichainCallbackProxy");

    address internal buyer = makeAddr("buyer");
    address internal challenger = makeAddr("challenger");
    address[] internal gpus; // provider accounts
    address[] internal verifiers;

    struct Delivered {
        uint256 chainId;
        bytes4 selector;
        bool ok;
    }

    Delivered[] internal delivered; // every callback executed, in order
    uint256 internal maxReactTopic;
    uint256 internal maxReactGas; // worst react() seen; Reactive caps reactive txs at 900k
    bool internal allowFailedCallbacks;

    /// @dev Gas the real callback proxy withholds for its own accounting and fee
    /// settlement (`_extraGas` + `_maxChargeGas`); assumed generously here.
    uint256 internal constant PROXY_OVERHEAD = 150_000;

    function setUp() public virtual {
        vm.warp(1_800_000_000);
        vm.etch(SYSTEM, address(new MockSystem()).code);
        sys = MockSystem(payable(SYSTEM));

        referee = new LoomReferee(BASE, UNICHAIN, MIN_BOND, 2);
        escrow = new LoomEscrow(IPayable(payable(baseProxy)), address(referee), CHALLENGE_BOND);
        bonds = new LoomBonds(IPayable(payable(uniProxy)), address(referee), MIN_BOND, TIMEOUT_PENALTY);
        referee.setTargets(address(escrow), address(bonds));

        for (uint256 i; i < 3; ++i) {
            address v = makeAddr(string.concat("verifier", vm.toString(i)));
            verifiers.push(v);
            escrow.setVerifier(v, true);
        }

        vm.recordLogs();
        // Five GPUs bond on the provider chain. Bigger index = joined later.
        for (uint256 i; i < 5; ++i) {
            address g = makeAddr(string.concat("gpu", vm.toString(i)));
            gpus.push(g);
            vm.deal(g, 1 ether);
            vm.prank(g);
            bonds.register{value: MIN_BOND}(string.concat("http://gpu", vm.toString(i)));
        }
        vm.deal(buyer, 10 ether);
        vm.deal(challenger, 1 ether);
        pump();
    }

    // ------------------------------------------------------------ relay
    function chainOf(address emitter_) internal view returns (uint256) {
        if (emitter_ == address(escrow)) return BASE;
        if (emitter_ == address(bonds)) return UNICHAIN;
        return 0;
    }

    /// @notice Deliver every pending log and callback until the system is quiet.
    /// Logs are handled in emission order: origin-chain logs go to react(),
    /// CallbackRequest logs from the system contract are executed on the destination.
    function pump() internal {
        for (uint256 guard; guard < 50; ++guard) {
            Vm.Log[] memory logs = vm.getRecordedLogs();
            uint256 handled;
            for (uint256 i; i < logs.length; ++i) {
                if (logs[i].emitter == SYSTEM && logs[i].topics[0] == MockSystem.CallbackRequest.selector) {
                    _execute(logs[i]);
                    ++handled;
                    continue;
                }
                uint256 cid = chainOf(logs[i].emitter);
                if (cid == 0) continue;
                _react(_record(cid, logs[i]));
                ++handled;
            }
            if (handled == 0) return;
        }
        revert("relay did not settle");
    }

    /// @notice Advance time and deliver one Cron10 tick.
    function tick(uint256 secs_) internal {
        vm.warp(block.timestamp + secs_);
        vm.roll(block.number + 10);
        IReactive.LogRecord memory rec;
        rec.chainId = 5318007;
        rec.contractAddress = CRON_SOURCE;
        rec.topic0 = CRON10;
        rec.data = abi.encode(block.number);
        rec.opCode = 1;
        _react(rec);
        pump();
    }

    function _record(uint256 chainId_, Vm.Log memory l_) internal pure returns (IReactive.LogRecord memory rec) {
        rec.chainId = chainId_;
        rec.contractAddress = l_.emitter;
        rec.opCode = l_.topics.length;
        if (l_.topics.length > 0) rec.topic0 = uint256(l_.topics[0]);
        if (l_.topics.length > 1) rec.topic1 = uint256(l_.topics[1]);
        if (l_.topics.length > 2) rec.topic2 = uint256(l_.topics[2]);
        if (l_.topics.length > 3) rec.topic3 = uint256(l_.topics[3]);
        rec.data = l_.data;
    }

    function _react(IReactive.LogRecord memory rec_) internal {
        // Only deliver what the referee actually subscribed to, like the real network.
        if (!sys.isSubscribed(address(referee), rec_.chainId, rec_.contractAddress, rec_.topic0)) {
            if (!(rec_.contractAddress == CRON_SOURCE
                        && sys.isSubscribed(address(referee), block.chainid, CRON_SOURCE, CRON10))) {
                return;
            }
        }
        vm.prank(SYSTEM);
        uint256 g = gasleft();
        referee.react(rec_);
        uint256 used = g - gasleft();
        if (used > maxReactGas) {
            maxReactGas = used;
            maxReactTopic = rec_.topic0;
        }
    }

    function _execute(Vm.Log memory l_) internal {
        uint256 chainId = uint256(l_.topics[1]);
        address sender = address(uint160(uint256(l_.topics[2])));
        address recipient = address(uint160(uint256(l_.topics[3])));
        (uint64 gasLimit, bytes memory payload) = abi.decode(l_.data, (uint64, bytes));
        // Reactive overwrites the first argument with the requesting reactive contract.
        assembly {
            mstore(add(payload, 36), sender)
        }
        address proxy = chainId == BASE ? baseProxy : uniProxy;
        vm.prank(proxy);
        (bool ok,) = recipient.call{gas: gasLimit - PROXY_OVERHEAD}(payload);
        delivered.push(Delivered(chainId, bytes4(payload), ok));
        if (!allowFailedCallbacks) assertTrue(ok, "callback failed on destination");
    }

    // ---------------------------------------------------------- helpers
    function layers3() internal pure returns (uint8[] memory l) {
        l = new uint8[](3);
        l[0] = 4;
        l[1] = 4;
        l[2] = 4;
    }

    function postJob(uint256 payment_) internal returns (uint256 jobId) {
        vm.prank(buyer);
        jobId = escrow.createJob{value: payment_}(
            keccak256("dataset"), "ipfs://dataset", layers3(), STAGE_TIMEOUT, CHALLENGE_WINDOW
        );
        pump();
    }

    /// @dev Commit all stages from `from_` using the given output hashes.
    function commitFrom(uint256 jobId_, uint8 from_, bytes32[] memory outs_) internal {
        address[] memory provs = escrow.providersOf(jobId_);
        for (uint8 s = from_; s < outs_.length; ++s) {
            bytes32 inHash = s == 0 ? keccak256("dataset") : outs_[s - 1];
            vm.prank(provs[s]);
            escrow.commitStage(jobId_, s, inHash, outs_[s], "http://blob");
            pump();
        }
    }

    function honestTrace() internal pure returns (bytes32[] memory t) {
        t = new bytes32[](3);
        t[0] = keccak256("act0");
        t[1] = keccak256("act1");
        t[2] = keccak256("result");
    }

    function status(uint256 jobId_) internal view returns (LoomEscrow.Status s) {
        (,, s,,,,,,,,,,,,) = escrow.jobs(jobId_);
    }

    function phase(uint256 jobId_) internal view returns (LoomReferee.Phase p) {
        (p,,,,,,,,,,,) = referee.jobState(jobId_);
    }

    function bondOf(address p_) internal view returns (uint256 b) {
        (b,,,,,) = bonds.providers(p_);
    }

    function repOf(address p_) internal view returns (uint32 jobsDone, uint32 faults, uint32 timeouts) {
        (,, jobsDone, faults, timeouts,) = bonds.providers(p_);
    }

    function countDelivered(bytes4 sel_) internal view returns (uint256 n) {
        for (uint256 i; i < delivered.length; ++i) {
            if (delivered[i].selector == sel_ && delivered[i].ok) ++n;
        }
    }
}
