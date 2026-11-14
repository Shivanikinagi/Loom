// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import {IPayable} from "@reactive/src/interfaces/IPayable.sol";
import {IPayer} from "@reactive/src/interfaces/IPayer.sol";

/// @title LoomCallbackBase
/// @notice Callback-receiver base for LOOM's destination contracts.
/// @dev Same authentication model as reactive-lib-omni's AbstractCallback
/// (caller must be the callback proxy, injected first argument must be the
/// authorised reactive contract), with one difference that matters for a
/// contract that holds other people's money: the proxy's `pay()` can only ever
/// draw on the *operating* balance. User escrow, challenge bonds and provider
/// bonds are reported by `locked()` and are never used to pay callback fees.
abstract contract LoomCallbackBase is IPayer {
    error NotAuthorized(address sender, address expected);
    error CallbackNotAuthorized(address sender, address expected);
    error InsufficientOperatingFunds(uint256 required, uint256 available);
    error TransferFailed();

    /// @notice Reactive callback proxy on this chain; also the fee collector.
    IPayable public immutable _SERVICE_PROVIDER;
    /// @notice LoomReferee on Reactive Network, the only contract allowed to drive callbacks.
    address public immutable _CALLBACK_SENDER;

    /// @notice Funds that failed to push (e.g. recipient reverted) and can be pulled later.
    mapping(address => uint256) public credits;
    uint256 internal totalCredits;

    event Credited(address indexed account, uint256 amount);

    constructor(IPayable callbackProxy_, address referee_) {
        _SERVICE_PROVIDER = callbackProxy_;
        _CALLBACK_SENDER = referee_;
    }

    receive() external payable virtual {}

    modifier onlyReferee(address rvm_) {
        if (msg.sender != address(_SERVICE_PROVIDER)) revert NotAuthorized(msg.sender, address(_SERVICE_PROVIDER));
        if (rvm_ != _CALLBACK_SENDER) revert CallbackNotAuthorized(rvm_, _CALLBACK_SENDER);
        _;
    }

    /// @notice Wei held on behalf of users (escrow, bonds, credits). Never spent on fees.
    function locked() public view virtual returns (uint256);

    /// @notice Balance available to pay Reactive callback fees.
    function operatingBalance() public view returns (uint256) {
        uint256 bal = address(this).balance;
        uint256 l = locked();
        return bal > l ? bal - l : 0;
    }

    /// @inheritdoc IPayer
    function pay(uint256 amount_) external {
        if (msg.sender != address(_SERVICE_PROVIDER)) revert NotAuthorized(msg.sender, address(_SERVICE_PROVIDER));
        _payFee(amount_);
    }

    /// @notice Settle any outstanding callback debt from the operating balance.
    function coverDebt() external {
        _payFee(_SERVICE_PROVIDER.debt(address(this)));
    }

    function _payFee(uint256 amount_) private {
        uint256 avail = operatingBalance();
        if (amount_ > avail) revert InsufficientOperatingFunds(amount_, avail);
        if (amount_ > 0) {
            (bool ok,) = payable(address(_SERVICE_PROVIDER)).call{value: amount_}("");
            if (!ok) revert TransferFailed();
        }
    }

    /// @notice Push ETH; if the recipient refuses it, keep it as a pullable credit
    /// so a hostile recipient can never make a callback revert.
    function _send(address to_, uint256 amount_) internal {
        if (amount_ == 0) return;
        (bool ok,) = payable(to_).call{value: amount_, gas: 30_000}("");
        if (!ok) {
            credits[to_] += amount_;
            totalCredits += amount_;
            emit Credited(to_, amount_);
        }
    }

    function withdrawCredit() external {
        uint256 amount = credits[msg.sender];
        credits[msg.sender] = 0;
        totalCredits -= amount;
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        if (!ok) revert TransferFailed();
    }
}
