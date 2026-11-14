// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import {IPayable} from "@reactive/src/interfaces/IPayable.sol";
import {LoomCallbackBase} from "./LoomCallbackBase.sol";
import {ILoomBondsEvents, ILoomBondsCallbacks} from "./interfaces/ILoom.sol";

/// @title LoomBonds
/// @notice Provider-side contract (Unichain Sepolia). GPU providers bond here,
/// on a different chain from the buyers' escrow. LoomReferee reads the bond
/// set from these events to schedule jobs, and slashes or credits providers
/// here based on what happened on the buyer chain.
contract LoomBonds is LoomCallbackBase, ILoomBondsEvents, ILoomBondsCallbacks {
    struct Provider {
        uint128 bond;
        uint64 unlockAt; // 0 while active; set when the provider asks to exit
        uint32 jobsDone;
        uint32 faults;
        uint32 timeouts;
        string endpoint;
    }

    error BondTooSmall(uint256 bond, uint256 required);
    error NotExiting();
    error StillLocked(uint64 unlockAt);
    error Exiting();

    /// @notice Bonds stay slashable this long after a provider asks to leave,
    /// so nobody can run away from a dispute that is still being voted on.
    uint64 public constant EXIT_DELAY = 1 days;
    /// @notice Share of a slashed bond paid to the challenger who caught the fault (rest goes to the buyer).
    uint256 public constant BOUNTY_BPS = 5_000;

    uint256 public immutable minBond;
    uint256 public immutable timeoutPenalty;
    uint256 internal totalBonded;

    mapping(address => Provider) public providers;

    constructor(IPayable callbackProxy_, address referee_, uint256 minBond_, uint256 timeoutPenalty_)
        payable
        LoomCallbackBase(callbackProxy_, referee_)
    {
        minBond = minBond_;
        timeoutPenalty = timeoutPenalty_;
    }

    // ------------------------------------------------------------ providers
    /// @notice Bond (or top up) and advertise the endpoint where stage blobs are served.
    function register(string calldata endpoint_) external payable {
        Provider storage p = providers[msg.sender];
        if (p.unlockAt != 0) revert Exiting();
        uint256 bond = uint256(p.bond) + msg.value;
        if (bond < minBond) revert BondTooSmall(bond, minBond);
        p.bond = uint128(bond);
        p.endpoint = endpoint_;
        totalBonded += msg.value;
        emit ProviderBonded(msg.sender, bond, endpoint_);
    }

    function requestExit() external {
        Provider storage p = providers[msg.sender];
        if (p.unlockAt != 0) revert Exiting();
        p.unlockAt = uint64(block.timestamp) + EXIT_DELAY;
        emit ProviderExiting(msg.sender, p.unlockAt);
    }

    function withdraw() external {
        Provider storage p = providers[msg.sender];
        if (p.unlockAt == 0) revert NotExiting();
        if (block.timestamp < p.unlockAt) revert StillLocked(p.unlockAt);
        uint256 amount = p.bond;
        p.bond = 0;
        p.unlockAt = 0;
        totalBonded -= amount;
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        if (!ok) revert TransferFailed();
        emit ProviderWithdrawn(msg.sender, amount);
    }

    // ------------------------------------------------- referee callbacks
    /// @notice Fault proven by a verifier quorum on the buyer chain: the whole
    /// bond is slashed. Half pays the challenger, half compensates the buyer.
    function slash(address rvm_, address provider_, uint256 jobId_, address challenger_, address buyer_)
        external
        onlyReferee(rvm_)
    {
        Provider storage p = providers[provider_];
        uint256 amount = p.bond;
        p.bond = 0;
        p.faults += 1;
        totalBonded -= amount;
        uint256 bounty = (amount * BOUNTY_BPS) / 10_000;
        _send(challenger_, bounty);
        _send(buyer_, amount - bounty);
        emit ProviderSlashed(provider_, jobId_, amount, challenger_, bounty, buyer_, amount - bounty);
        emit ReputationUpdated(provider_, p.jobsDone, p.faults, p.timeouts);
    }

    /// @notice Missed deadline. Going offline is not proof of fraud, so this is a
    /// small fixed penalty paid to the buyer, not a slash.
    function recordTimeout(address rvm_, address provider_, uint256 jobId_, address buyer_) external onlyReferee(rvm_) {
        Provider storage p = providers[provider_];
        uint256 penalty = timeoutPenalty < p.bond ? timeoutPenalty : p.bond;
        p.bond -= uint128(penalty);
        p.timeouts += 1;
        totalBonded -= penalty;
        _send(buyer_, penalty);
        emit ProviderTimedOut(provider_, jobId_, penalty, p.bond);
        emit ReputationUpdated(provider_, p.jobsDone, p.faults, p.timeouts);
    }

    function recordSuccess(address rvm_, uint256, address[] calldata providers_) external onlyReferee(rvm_) {
        for (uint256 i; i < providers_.length; ++i) {
            Provider storage p = providers[providers_[i]];
            p.jobsDone += 1;
            emit ReputationUpdated(providers_[i], p.jobsDone, p.faults, p.timeouts);
        }
    }

    // ----------------------------------------------------------------- views
    function locked() public view override returns (uint256) {
        return totalBonded + totalCredits;
    }

    function isActive(address provider_) external view returns (bool) {
        Provider storage p = providers[provider_];
        return p.unlockAt == 0 && p.bond >= minBond;
    }
}
