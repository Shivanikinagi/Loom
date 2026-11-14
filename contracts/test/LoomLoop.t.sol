// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import {LoomHarness} from "./utils/LoomHarness.sol";
import {LoomEscrow} from "../src/LoomEscrow.sol";
import {LoomReferee} from "../src/LoomReferee.sol";
import {LoomCallbackBase} from "../src/LoomCallbackBase.sol";
import {ILoomEscrowCallbacks, ILoomBondsCallbacks} from "../src/interfaces/ILoom.sol";

/// @notice End-to-end LOOM scenarios through the simulated Reactive relay.
contract LoomLoopTest is LoomHarness {
    function test_providersLearnedFromOtherChain() public view {
        assertEq(referee.providerCount(), 5);
        (bool known,,, uint128 bond,,,) = referee.providerState(gpus[0]);
        assertTrue(known);
        assertEq(bond, MIN_BOND);
    }

    function test_happyPath_settlesByLayersAndRecordsReputation() public {
        uint256 jobId = postJob(0.3 ether);

        // The referee picked three distinct bonded GPUs and the escrow confirmed them.
        address[] memory provs = escrow.providersOf(jobId);
        assertEq(provs.length, 3);
        assertTrue(provs[0] != provs[1] && provs[1] != provs[2] && provs[0] != provs[2]);
        assertEq(uint8(status(jobId)), uint8(LoomEscrow.Status.Running));
        assertTrue(referee.cronOn(), "clock on while a job is live");

        commitFrom(jobId, 0, honestTrace());
        assertEq(uint8(status(jobId)), uint8(LoomEscrow.Status.Proposed));

        uint256[3] memory before;
        for (uint256 i; i < 3; ++i) {
            before[i] = provs[i].balance;
        }

        tick(CHALLENGE_WINDOW + 10); // window closes; cron settles

        assertEq(uint8(status(jobId)), uint8(LoomEscrow.Status.Settled));
        for (uint256 i; i < 3; ++i) {
            assertEq(provs[i].balance - before[i], 0.1 ether);
        }

        // Reputation is written on the provider chain, then mirrored back.
        (uint32 jobsDone,,) = repOf(provs[0]);
        assertEq(jobsDone, 1);
        (,,,, uint32 mirrored,,) = referee.providerState(provs[0]);
        assertEq(mirrored, 1);

        assertEq(uint8(phase(jobId)), uint8(LoomReferee.Phase.Done));
        assertFalse(referee.cronOn(), "clock off once nothing is live");
        assertEq(escrow.locked(), 0);
    }

    function test_cheaterCaught_slashedOnOtherChain_andRerouted() public {
        uint256 jobId = postJob(0.3 ether);
        address[] memory provs = escrow.providersOf(jobId);
        address cheater = provs[1];

        // Stage 1 skips layers: its output (and therefore stage 2's) is wrong.
        bytes32[] memory bad = honestTrace();
        bad[1] = keccak256("act1-lazy");
        bad[2] = keccak256("result-from-garbage");
        commitFrom(jobId, 0, bad);

        // The challenger recomputed the pipeline; divergence starts at stage 1.
        vm.prank(challenger);
        escrow.challenge{value: CHALLENGE_BOND}(jobId, honestTrace());
        pump();
        (,,,, uint8 nextStage, uint8 disputed,,,,,,,,,) = escrow.jobs(jobId);
        assertEq(disputed, 1);
        nextStage;

        uint256 buyerBefore = buyer.balance;
        uint256 challengerBefore = challenger.balance;

        // Two of three verifiers re-ran stage 1 and found it faulty: quorum.
        _vote(jobId, 0, true);
        assertEq(uint8(status(jobId)), uint8(LoomEscrow.Status.Disputed), "one vote is not quorum");
        _vote(jobId, 1, true);

        // Escrow wiped stage 1+ and rerouted stage 1 to a standby GPU...
        address[] memory now_ = escrow.providersOf(jobId);
        assertTrue(now_[1] != cheater);
        assertTrue(now_[1] != provs[0] && now_[1] != provs[2]);
        assertEq(uint8(status(jobId)), uint8(LoomEscrow.Status.Running));
        // ...then the referee slashed the cheater on the provider chain.
        assertEq(bondOf(cheater), 0);
        (, uint32 faults,) = repOf(cheater);
        assertEq(faults, 1);
        assertEq(challenger.balance - challengerBefore, CHALLENGE_BOND + MIN_BOND / 2, "bond back + bounty");
        assertEq(buyer.balance - buyerBefore, MIN_BOND / 2, "buyer compensated");

        // A late third vote changes nothing.
        vm.prank(verifiers[2]);
        vm.expectRevert();
        escrow.vote(jobId, 1, true);

        // The replacement recomputes stage 1, stage 2 recomputes on the good input.
        commitFrom(jobId, 1, honestTrace());
        uint256 cheaterBefore = cheater.balance;
        tick(CHALLENGE_WINDOW + 10);

        assertEq(uint8(status(jobId)), uint8(LoomEscrow.Status.Settled));
        assertEq(cheater.balance, cheaterBefore, "cheater earns nothing");
        assertEq(escrow.locked(), 0);
        // The cheater is never scheduled again.
        (,, bool barred,,,,) = referee.providerState(cheater);
        assertTrue(barred);
    }

    function test_frivolousChallenge_bondGoesToAccused() public {
        uint256 jobId = postJob(0.3 ether);
        commitFrom(jobId, 0, honestTrace());
        address accused = escrow.providersOf(jobId)[1];

        bytes32[] memory wrongClaim = honestTrace();
        wrongClaim[1] = keccak256("challenger-is-wrong");
        vm.prank(challenger);
        escrow.challenge{value: CHALLENGE_BOND}(jobId, wrongClaim);
        pump();

        uint256 accusedBefore = accused.balance;
        _vote(jobId, 0, false);
        _vote(jobId, 2, false);

        assertEq(uint8(status(jobId)), uint8(LoomEscrow.Status.Proposed));
        assertEq(accused.balance - accusedBefore, CHALLENGE_BOND);
        assertEq(bondOf(accused), MIN_BOND, "honest provider keeps its bond");

        tick(CHALLENGE_WINDOW + 10);
        assertEq(uint8(status(jobId)), uint8(LoomEscrow.Status.Settled));
    }

    function test_missedDeadline_reroutesAndPenalisesLightly() public {
        uint256 jobId = postJob(0.3 ether);
        address sleepy = escrow.providersOf(jobId)[0];
        uint256 buyerBefore = buyer.balance;

        tick(STAGE_TIMEOUT + 10); // stage 0 never committed

        address[] memory provs = escrow.providersOf(jobId);
        assertTrue(provs[0] != sleepy, "stage 0 rerouted");
        assertEq(uint8(status(jobId)), uint8(LoomEscrow.Status.Running));
        assertEq(bondOf(sleepy), MIN_BOND - TIMEOUT_PENALTY, "small penalty, not a slash");
        assertEq(buyer.balance - buyerBefore, TIMEOUT_PENALTY);
        (,, uint32 timeouts) = repOf(sleepy);
        assertEq(timeouts, 1);

        // Pipeline still completes with the replacement.
        commitFrom(jobId, 0, honestTrace());
        tick(CHALLENGE_WINDOW + 10);
        assertEq(uint8(status(jobId)), uint8(LoomEscrow.Status.Settled));
    }

    function test_noQuorum_voidsChallenge() public {
        uint256 jobId = postJob(0.3 ether);
        commitFrom(jobId, 0, honestTrace());
        bytes32[] memory claim = honestTrace();
        claim[2] = keccak256("other");
        vm.prank(challenger);
        escrow.challenge{value: CHALLENGE_BOND}(jobId, claim);
        pump();
        _vote(jobId, 0, true); // only one verifier shows up

        uint256 before = challenger.balance;
        tick(escrow.VOTE_WINDOW() + 10);
        assertEq(uint8(status(jobId)), uint8(LoomEscrow.Status.Proposed));
        assertEq(challenger.balance - before, CHALLENGE_BOND, "bond returned, nobody punished");
    }

    function test_notEnoughProviders_refundsBuyer() public {
        // Four of five GPUs leave; a 3-stage job cannot be scheduled.
        for (uint256 i; i < 4; ++i) {
            vm.prank(gpus[i]);
            bonds.requestExit();
        }
        pump();
        uint256 before = buyer.balance;
        uint256 jobId = postJob(0.3 ether);
        assertEq(uint8(status(jobId)), uint8(LoomEscrow.Status.Refunded));
        assertEq(before - buyer.balance, 0, "full refund");
        assertFalse(referee.cronOn());
    }

    function test_reputationSteersScheduling() public {
        // Run one job so its three providers gain reputation.
        uint256 j1 = postJob(0.3 ether);
        address[] memory first = escrow.providersOf(j1);
        commitFrom(j1, 0, honestTrace());
        tick(CHALLENGE_WINDOW + 10);

        // Next job goes to the same, now-proven, providers.
        uint256 j2 = postJob(0.3 ether);
        address[] memory second = escrow.providersOf(j2);
        for (uint256 i; i < 3; ++i) {
            assertEq(second[i], first[i]);
        }
    }

    function test_earlySettle_isIgnoredThenRetried() public {
        uint256 jobId = postJob(0.3 ether);
        commitFrom(jobId, 0, honestTrace());
        // Referee's clock runs ahead of the buyer chain: it fires 1s before the
        // escrow deadline (simulated by forcing a settle callback early).
        vm.prank(baseProxy);
        escrow.settle(address(referee), jobId);
        assertEq(uint8(status(jobId)), uint8(LoomEscrow.Status.Proposed), "ignored, not reverted");
        tick(CHALLENGE_WINDOW + 10);
        assertEq(uint8(status(jobId)), uint8(LoomEscrow.Status.Settled));
    }

    function test_retriesUntilConfirmed() public {
        uint256 jobId = postJob(0.3 ether);
        commitFrom(jobId, 0, honestTrace());
        tick(CHALLENGE_WINDOW + 1); // inside GRACE: nothing fires yet
        assertEq(uint8(status(jobId)), uint8(LoomEscrow.Status.Proposed));
        tick(10);
        assertEq(uint8(status(jobId)), uint8(LoomEscrow.Status.Settled));
        assertEq(countDelivered(ILoomEscrowCallbacks.settle.selector), 1);
    }

    // ------------------------------------------------------------- auth
    function test_callbacksRejectEveryoneButTheReferee() public {
        uint256 jobId = postJob(0.3 ether);

        vm.expectRevert(abi.encodeWithSelector(LoomCallbackBase.NotAuthorized.selector, address(this), baseProxy));
        escrow.settle(address(referee), jobId);

        // Right proxy, wrong reactive contract.
        vm.prank(baseProxy);
        vm.expectRevert(
            abi.encodeWithSelector(LoomCallbackBase.CallbackNotAuthorized.selector, address(this), address(referee))
        );
        escrow.settle(address(this), jobId);

        vm.expectRevert();
        bonds.slash(address(referee), gpus[0], jobId, challenger, buyer);

        vm.expectRevert(abi.encodeWithSelector(LoomReferee.NotOwner.selector));
        vm.prank(buyer);
        referee.setTargets(address(1), address(2));
    }

    function test_reactOnlyFromSystem() public {
        vm.expectRevert();
        referee.react(_emptyRecord());
    }

    function test_feesNeverSpendEscrowOrBonds() public {
        postJob(0.3 ether);
        // No operating balance: the proxy may not take escrowed funds.
        assertEq(escrow.operatingBalance(), 0);
        vm.prank(baseProxy);
        vm.expectRevert(abi.encodeWithSelector(LoomCallbackBase.InsufficientOperatingFunds.selector, 1, 0));
        escrow.pay(1);

        // Top up for fees: only that top-up is spendable.
        vm.deal(address(this), 1 ether);
        (bool ok,) = address(escrow).call{value: 0.02 ether}("");
        assertTrue(ok);
        assertEq(escrow.operatingBalance(), 0.02 ether);
        vm.prank(baseProxy);
        escrow.pay(0.02 ether);
        assertEq(address(escrow).balance, escrow.locked());

        vm.prank(uniProxy);
        vm.expectRevert();
        bonds.pay(1);
    }

    function test_subscriptions() public view {
        // 13 escrow topics + 6 bond topics; the clock is off with nothing live.
        assertEq(sys.activeCount(address(referee)), 19);
        assertFalse(referee.cronOn());
    }

    // ---------------------------------------------------------- helpers
    function _vote(uint256 jobId_, uint256 who_, bool faulty_) internal {
        (,,,,,, uint32 round,,,,,,,,) = escrow.jobs(jobId_);
        vm.prank(verifiers[who_]);
        escrow.vote(jobId_, round, faulty_);
        pump();
    }

    function _emptyRecord() internal pure returns (LoomReferee.LogRecord memory r) {
        r.chainId = BASE;
    }
}

/// @notice Money is conserved and gas stays inside Reactive's limits.
contract LoomEconomicsTest is LoomHarness {
    function testFuzz_settlementPaysExactlyThePayment(uint96 payment_, uint8 a_, uint8 b_, uint8 c_) public {
        payment_ = uint96(bound(payment_, 1, 5 ether));
        uint8[] memory l = new uint8[](3);
        l[0] = uint8(bound(a_, 1, 40));
        l[1] = uint8(bound(b_, 1, 40));
        l[2] = uint8(bound(c_, 1, 40));

        vm.prank(buyer);
        uint256 jobId = escrow.createJob{value: payment_}(keccak256("dataset"), "x", l, STAGE_TIMEOUT, CHALLENGE_WINDOW);
        pump();
        address[] memory provs = escrow.providersOf(jobId);
        uint256 sumBefore;
        for (uint256 i; i < 3; ++i) {
            sumBefore += provs[i].balance;
        }

        commitFrom(jobId, 0, honestTrace());
        tick(CHALLENGE_WINDOW + 10);

        uint256 sumAfter;
        for (uint256 i; i < 3; ++i) {
            sumAfter += provs[i].balance;
        }
        assertEq(sumAfter - sumBefore, payment_, "every wei of payment reaches providers");
        assertEq(address(escrow).balance, escrow.locked(), "escrow holds exactly what it owes");
    }

    function test_conservationThroughFraudAndTimeout() public {
        uint256 total = address(escrow).balance + address(bonds).balance;
        uint256 j = postJob(0.3 ether);
        tick(STAGE_TIMEOUT + 10); // timeout + reroute
        bytes32[] memory bad = honestTrace();
        bad[0] = keccak256("noise");
        bad[1] = keccak256("x");
        bad[2] = keccak256("y");
        commitFrom(j, 0, bad);
        vm.prank(challenger);
        escrow.challenge{value: CHALLENGE_BOND}(j, honestTrace());
        pump();
        (,,,,,, uint32 round,,,,,,,,) = escrow.jobs(j);
        for (uint256 v; v < 2; ++v) {
            vm.prank(verifiers[v]);
            escrow.vote(j, round, true);
            pump();
        }
        commitFrom(j, 0, honestTrace());
        tick(CHALLENGE_WINDOW + 10);

        assertEq(uint8(status(j)), uint8(LoomEscrow.Status.Settled));
        // Everything left in the contracts is still owed to someone.
        assertEq(address(escrow).balance, escrow.locked());
        assertEq(address(bonds).balance, bonds.locked());
        assertLe(address(escrow).balance + address(bonds).balance, total + 0.3 ether + CHALLENGE_BOND);

        emit log_named_uint("worst react() gas", maxReactGas);
        assertLt(maxReactGas, 900_000, "react() within the 900k reactive gas cap");
        emit log_named_bytes32("worst react() topic", bytes32(maxReactTopic));
    }
}
