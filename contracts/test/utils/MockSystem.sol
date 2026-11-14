// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import {ISystemContract} from "@reactive/src/interfaces/ISystemContract.sol";

/// @notice Stand-in for Reactive's system contract (0x8888...8888), etched at that
/// address in tests. Records subscriptions and callback requests exactly as the
/// Omni system contract receives them, so the harness can replay them.
contract MockSystem {
    struct Sub {
        address subscriber;
        uint256 chainId;
        address contract_;
        uint256 topic0;
        bool active;
    }

    Sub[] public subs;

    /// @dev Mirrors the real system contract: callback requests are announced as
    /// events (which the network relays), not kept in storage.
    event CallbackRequest(
        uint256 indexed chainId, address indexed sender, address indexed recipient, uint64 gasLimit, bytes payload
    );

    function subscribe(uint256 chainId_, address contract_, uint256 topic0_, uint256, uint256, uint256) external {
        subs.push(Sub(msg.sender, chainId_, contract_, topic0_, true));
    }

    function unsubscribe(uint256 chainId_, address contract_, uint256 topic0_, uint256, uint256, uint256) external {
        for (uint256 i; i < subs.length; ++i) {
            Sub storage s = subs[i];
            if (
                s.active && s.subscriber == msg.sender && s.chainId == chainId_ && s.contract_ == contract_
                    && s.topic0 == topic0_
            ) {
                s.active = false;
            }
        }
    }

    function requestCallbackV_1_0(ISystemContract.CallbackConfiguration_V_1_0 memory config_) external {
        require(config_.gasLimit >= 100_000, "below Reactive minimum callback gas");
        emit CallbackRequest(config_.chainId, msg.sender, config_.recipient, config_.gasLimit, config_.payload);
    }

    function debt(address) external pure returns (uint256) {
        return 0;
    }

    function isSubscribed(address subscriber_, uint256 chainId_, address contract_, uint256 topic0_)
        external
        view
        returns (bool)
    {
        for (uint256 i; i < subs.length; ++i) {
            Sub storage s = subs[i];
            if (
                s.active && s.subscriber == subscriber_ && s.chainId == chainId_ && s.contract_ == contract_
                    && s.topic0 == topic0_
            ) {
                return true;
            }
        }
        return false;
    }

    function activeCount(address subscriber_) external view returns (uint256 n) {
        for (uint256 i; i < subs.length; ++i) {
            if (subs[i].active && subs[i].subscriber == subscriber_) ++n;
        }
    }

    receive() external payable {}
}
