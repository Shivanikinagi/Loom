// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

/// @notice Events emitted by LoomEscrow on the buyer chain (Base Sepolia).
/// LoomReferee on Reactive Lasna subscribes to these by selector.
interface ILoomEscrowEvents {
    event JobCreated(
        uint256 indexed jobId,
        address indexed buyer,
        uint256 payment,
        uint8 nStages,
        bytes32 datasetHash,
        string datasetURI
    );
    event ProvidersAssigned(uint256 indexed jobId, address[] providers, uint64 stageDeadline);
    event StageCommitted(
        uint256 indexed jobId,
        uint8 indexed stage,
        address indexed provider,
        bytes32 inHash,
        bytes32 outHash,
        string uri,
        uint64 nextDeadline
    );
    event ResultProposed(uint256 indexed jobId, bytes32 resultHash, uint64 challengeDeadline);
    event Challenged(
        uint256 indexed jobId,
        address indexed challenger,
        address indexed accused,
        uint8 stage,
        uint32 round,
        bytes32 committedOut,
        bytes32 claimedOut,
        uint64 voteDeadline
    );
    event VerdictVote(uint256 indexed jobId, address indexed verifier, uint32 round, bool faulty);
    event FaultResolved(
        uint256 indexed jobId, address indexed faulty, address indexed challenger, uint8 stage, address buyer
    );
    event StageReassigned(
        uint256 indexed jobId,
        uint8 indexed stage,
        address indexed newProvider,
        address oldProvider,
        uint64 stageDeadline
    );
    event StageTimedOut(uint256 indexed jobId, uint8 indexed stage, address indexed provider, address buyer);
    event ChallengeRejected(
        uint256 indexed jobId,
        address indexed challenger,
        address indexed accused,
        uint256 bond,
        uint64 challengeDeadline
    );
    event ChallengeVoided(uint256 indexed jobId, address indexed challenger, uint64 challengeDeadline);
    event JobSettled(uint256 indexed jobId, bytes32 resultHash, address[] providers, uint256[] amounts);
    event JobRefunded(uint256 indexed jobId, address indexed buyer, uint256 amount);
    event CallbackIgnored(uint256 indexed jobId, bytes4 indexed action, string reason);
}

/// @notice Events emitted by LoomBonds on the provider chain (Unichain Sepolia).
interface ILoomBondsEvents {
    event ProviderBonded(address indexed provider, uint256 bond, string endpoint);
    event ProviderExiting(address indexed provider, uint64 unlockAt);
    event ProviderWithdrawn(address indexed provider, uint256 amount);
    event ProviderSlashed(
        address indexed provider,
        uint256 indexed jobId,
        uint256 amount,
        address challenger,
        uint256 bounty,
        address buyer,
        uint256 compensation
    );
    event ProviderTimedOut(address indexed provider, uint256 indexed jobId, uint256 penalty, uint256 bondLeft);
    event ReputationUpdated(address indexed provider, uint32 jobsDone, uint32 faults, uint32 timeouts);
}

/// @notice Callback surface of LoomEscrow. The first argument is always the
/// reactive sender injected by the Reactive callback proxy.
interface ILoomEscrowCallbacks {
    function assignProviders(address rvm, uint256 jobId, address[] calldata providers) external;
    function settle(address rvm, uint256 jobId) external;
    function timeoutStage(address rvm, uint256 jobId, uint8 stage, address replacement) external;
    function resolveFault(address rvm, uint256 jobId, address replacement) external;
    function rejectChallenge(address rvm, uint256 jobId) external;
    function voidChallenge(address rvm, uint256 jobId) external;
    function refund(address rvm, uint256 jobId) external;
}

/// @notice Callback surface of LoomBonds.
interface ILoomBondsCallbacks {
    function slash(address rvm, address provider, uint256 jobId, address challenger, address buyer) external;
    function recordTimeout(address rvm, address provider, uint256 jobId, address buyer) external;
    function recordSuccess(address rvm, uint256 jobId, address[] calldata providers) external;
}
