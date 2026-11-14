# LOOM evidence (testnet)

Generated 2026-11-15 00:07:02 India Standard Time.

## Contracts

| Role | Chain | Address |
|---|---|---|
| LoomReferee (reactive) | lasna (5318007) | [`0x5907e30b9470A38173949547a480804e296d2497`](https://lasna.reactscan.net/address/0x5907e30b9470A38173949547a480804e296d2497) |
| LoomEscrow | base (84532) | [`0xE90B525c5f1527275C8D581BfED17e1d2580B65A`](https://sepolia.basescan.org/address/0xE90B525c5f1527275C8D581BfED17e1d2580B65A) |
| LoomBonds | unichain (1301) | [`0x5907e30b9470A38173949547a480804e296d2497`](https://sepolia.uniscan.xyz/address/0x5907e30b9470A38173949547a480804e296d2497) |

## Job 1

Reactive transactions on Lasna: **6**, callbacks requested: **5** (3 to Base, 2 to Unichain).

| t+s | chain | event | details | tx |
|---:|---|---|---|---|
| 0 | base | JobCreated |  | [`0x3daff573…`](https://sepolia.basescan.org/tx/0x3daff5730bc9e1ad52dca938309ee66541233411bd7ec0d232a1bb736d045dc0) |
| 0 | lasna | ProvidersSelected | providers=0x6fF5..39b6,0xfb77..b931,0x998b..B28D | [`0x4632be25…`](https://lasna.reactscan.net/tx/0x4632be25986baeac10b5437fac2c08809e544f148726f21ae82b1e6ddcab925e) |
| 0 | lasna | CallbackSent | -> base.assignProviders() | [`0x4632be25…`](https://lasna.reactscan.net/tx/0x4632be25986baeac10b5437fac2c08809e544f148726f21ae82b1e6ddcab925e) |
| 2 | base | ProvidersAssigned | providers=0x6fF5..39b6,0xfb77..b931,0x998b..B28D | [`0x6ed2ab45…`](https://sepolia.basescan.org/tx/0x6ed2ab4557b2618c357eafbf947088d87ec8f8765763e00f6d48bbcb8e22785b) |
| 8 | base | StageCommitted | stage=0 provider=0x6fF5..39b6 | [`0x250c501a…`](https://sepolia.basescan.org/tx/0x250c501a60e1919889410c2375b3f827300015094b72d897ef3537369bd810be) |
| 14 | base | StageCommitted | stage=1 provider=0xfb77..b931 | [`0x9489bb20…`](https://sepolia.basescan.org/tx/0x9489bb2058d433946a60ba828a57050590f5eb562055d5d933ea082d41936967) |
| 19 | base | StageCommitted | stage=2 provider=0x998b..B28D | [`0x9b838e22…`](https://sepolia.basescan.org/tx/0x9b838e2234edbae9913b608fd5bc4f9a5de9b066cb079824914e446c61d877b6) |
| 19 | base | ResultProposed |  | [`0x9b838e22…`](https://sepolia.basescan.org/tx/0x9b838e2234edbae9913b608fd5bc4f9a5de9b066cb079824914e446c61d877b6) |
| 25 | base | Challenged | stage=1 round=1 accused=0xfb77..b931 | [`0x4b8fadae…`](https://sepolia.basescan.org/tx/0x4b8fadae6ad5b98e1c9a76b22dddfb124632abe432717c3e2149f0b37ad9496e) |
| 32 | lasna | VoteCounted | round=1 faulty=True votesFaulty=1 votesHonest=0 | [`0x2bac25dc…`](https://lasna.reactscan.net/tx/0x2bac25dc4d29db6115e56d142b82577983a0f9df08fb96e7173a7b1b7ea49cad) |
| 32 | lasna | VoteCounted | round=1 faulty=True votesFaulty=2 votesHonest=0 | [`0xacfd7f8c…`](https://lasna.reactscan.net/tx/0xacfd7f8cef2cf60a0589084ce4e2ab6b85a046ead797f56a985d4fcf9ed31003) |
| 32 | lasna | QuorumReached | round=1 faulty=True accused=0xfb77..b931 replacement=0x8281..cDeF | [`0xacfd7f8c…`](https://lasna.reactscan.net/tx/0xacfd7f8cef2cf60a0589084ce4e2ab6b85a046ead797f56a985d4fcf9ed31003) |
| 32 | lasna | CallbackSent | -> base.resolveFault() | [`0xacfd7f8c…`](https://lasna.reactscan.net/tx/0xacfd7f8cef2cf60a0589084ce4e2ab6b85a046ead797f56a985d4fcf9ed31003) |
| 33 | base | VerdictVote | round=1 faulty=True | [`0xd2180732…`](https://sepolia.basescan.org/tx/0xd2180732ea53f72ca9540522becf2c94b6ab6f5b32a6b34f53ab1cc1803506a5) |
| 33 | base | VerdictVote | round=1 faulty=True | [`0x95c02ed5…`](https://sepolia.basescan.org/tx/0x95c02ed5087483c46a2b029707fd2e0b540f761de0da53a54f4846f8f5646329) |
| 33 | base | VerdictVote | round=1 faulty=True | [`0x096efe5f…`](https://sepolia.basescan.org/tx/0x096efe5f5dfb05105408ed3ce4f240abb1f33386f7bc28802f35261beea6fba2) |
| 33 | lasna | CallbackSent | -> unichain.slash() | [`0x7043d983…`](https://lasna.reactscan.net/tx/0x7043d983d90a0d66306a2f464a441917f73fd1983f3b8ae170e6cd5b1bc971ed) |
| 34 | base | FaultResolved | stage=1 faulty=0xfb77..b931 | [`0x6426e74c…`](https://sepolia.basescan.org/tx/0x6426e74cc928032a367a82a17fea090767a6d27a4a0e1430dce6a14efb15431e) |
| 34 | base | StageReassigned | stage=1 newProvider=0x8281..cDeF | [`0x6426e74c…`](https://sepolia.basescan.org/tx/0x6426e74cc928032a367a82a17fea090767a6d27a4a0e1430dce6a14efb15431e) |
| 36 | unichain | ProviderSlashed | provider=0xfb77..b931 amount=0.001 ETH bounty=0.0005 ETH | [`0xb945b2ed…`](https://sepolia.uniscan.xyz/tx/0xb945b2ed1fb01cd1d6d82f8654ec20d55ee05755f6429435674fc28747bb604c) |
| 40 | base | StageCommitted | stage=1 provider=0x8281..cDeF | [`0x82f3679b…`](https://sepolia.basescan.org/tx/0x82f3679bb9a2475fb89041f77caa490a0dcbd3f0233f3143b56fc83c61266ada) |
| 44 | base | StageCommitted | stage=2 provider=0x998b..B28D | [`0xed6c06ee…`](https://sepolia.basescan.org/tx/0xed6c06ee758dc3c513f20864c5051ff50fa6003d382a65068be60f7a6e19e3b3) |
| 44 | base | ResultProposed |  | [`0xed6c06ee…`](https://sepolia.basescan.org/tx/0xed6c06ee758dc3c513f20864c5051ff50fa6003d382a65068be60f7a6e19e3b3) |
| 142 | lasna | TimerFired | phase=Proposed expired | [`0x3a89910e…`](https://lasna.reactscan.net/tx/0x3a89910e63e4c0a141b5c1b01f1dda0984f9510f55a14bbd7d4f5350df933a2d) |
| 142 | lasna | CallbackSent | -> base.settle() | [`0x3a89910e…`](https://lasna.reactscan.net/tx/0x3a89910e63e4c0a141b5c1b01f1dda0984f9510f55a14bbd7d4f5350df933a2d) |
| 144 | base | JobSettled |  | [`0x4345b828…`](https://sepolia.basescan.org/tx/0x4345b82887eba0e243b00053c6651e4be1a4701df63fe7d8b74927fa094ca247) |
| 145 | lasna | CallbackSent | -> unichain.recordSuccess() | [`0xc0f72e15…`](https://lasna.reactscan.net/tx/0xc0f72e15537a43ac5f267afe9285ba048e2f86672de16288fc88f0bce835c124) |
| 148 | unichain | ReputationUpdated | provider=0x6fF5..39b6 | [`0x91b85fe9…`](https://sepolia.uniscan.xyz/tx/0x91b85fe92868e858d04e8a42f7d29501abe68b079266b1e68769ff02c824e28f) |
| 148 | unichain | ReputationUpdated | provider=0x8281..cDeF | [`0x91b85fe9…`](https://sepolia.uniscan.xyz/tx/0x91b85fe92868e858d04e8a42f7d29501abe68b079266b1e68769ff02c824e28f) |
| 148 | unichain | ReputationUpdated | provider=0x998b..B28D | [`0x91b85fe9…`](https://sepolia.uniscan.xyz/tx/0x91b85fe92868e858d04e8a42f7d29501abe68b079266b1e68769ff02c824e28f) |

| loop leg | seconds |
|---|---:|
| schedule: job posted -> providers assigned | 2 |
| challenge -> Reactive counts quorum | 7 |
| quorum vote -> fault resolved on Base | 1 |
| fault resolved on Base -> slashed on Unichain | 2 |
| window closed -> settled | 125 |
| settled -> reputation on Unichain | 4 |

## Job 2

Reactive transactions on Lasna: **3**, callbacks requested: **3** (2 to Base, 1 to Unichain).

| t+s | chain | event | details | tx |
|---:|---|---|---|---|
| 0 | base | JobCreated |  | [`0xdb740cff…`](https://sepolia.basescan.org/tx/0xdb740cff3d8b7dca71fb37f0296117ef5d2780c70a6836d9b43026d2b07cae88) |
| 0 | lasna | ProvidersSelected | providers=0x6fF5..39b6,0x998b..B28D,0x8281..cDeF | [`0x7262b776…`](https://lasna.reactscan.net/tx/0x7262b7763120ff3a01d88c41a665312782bbe02bed372747ece3a8157ddcdca2) |
| 0 | lasna | CallbackSent | -> base.assignProviders() | [`0x7262b776…`](https://lasna.reactscan.net/tx/0x7262b7763120ff3a01d88c41a665312782bbe02bed372747ece3a8157ddcdca2) |
| 1 | base | ProvidersAssigned | providers=0x6fF5..39b6,0x998b..B28D,0x8281..cDeF | [`0x3ea5d41b…`](https://sepolia.basescan.org/tx/0x3ea5d41ba15df11844747536abe6debf89c25d46a8ccb794a02f13d864ce1d5b) |
| 5 | base | StageCommitted | stage=0 provider=0x6fF5..39b6 | [`0x53cdfb73…`](https://sepolia.basescan.org/tx/0x53cdfb735447bc7bd038d1f90c2db3d21778ccf6477e9a23996c73c206d99976) |
| 8 | base | StageCommitted | stage=1 provider=0x998b..B28D | [`0x64d88182…`](https://sepolia.basescan.org/tx/0x64d88182b3e8a836870e15a819fcdcdc86f4328003dae90d882f8f932cdbac6e) |
| 10 | base | StageCommitted | stage=2 provider=0x8281..cDeF | [`0xb5977c14…`](https://sepolia.basescan.org/tx/0xb5977c1408cf4f7dca13461e4114a342ddc3c33939ac7b765c87cff0ca0cfd31) |
| 10 | base | ResultProposed |  | [`0xb5977c14…`](https://sepolia.basescan.org/tx/0xb5977c1408cf4f7dca13461e4114a342ddc3c33939ac7b765c87cff0ca0cfd31) |
| 108 | lasna | TimerFired | phase=Proposed expired | [`0x02ef4778…`](https://lasna.reactscan.net/tx/0x02ef47788b17b3306d634eb9f2c47bbfe956f259962ba2e64c2e9b4e412e61cb) |
| 108 | lasna | CallbackSent | -> base.settle() | [`0x02ef4778…`](https://lasna.reactscan.net/tx/0x02ef47788b17b3306d634eb9f2c47bbfe956f259962ba2e64c2e9b4e412e61cb) |
| 110 | base | JobSettled |  | [`0xcceebdf4…`](https://sepolia.basescan.org/tx/0xcceebdf427625efb9fe9644a26c1b24a48e0e1eeb15bb9641151b5d2bd9216ec) |
| 110 | lasna | CallbackSent | -> unichain.recordSuccess() | [`0x000e04b2…`](https://lasna.reactscan.net/tx/0x000e04b2ce4e1aabf9822cbe5fb932807b13e52e01fcf7ca695db264fd1c0101) |
| 113 | unichain | ReputationUpdated | provider=0x6fF5..39b6 | [`0x094eb955…`](https://sepolia.uniscan.xyz/tx/0x094eb955c9d2a2e51e2baa9ab23095d2533125154fd43e58dfc1f07ac9fc3882) |
| 113 | unichain | ReputationUpdated | provider=0x998b..B28D | [`0x094eb955…`](https://sepolia.uniscan.xyz/tx/0x094eb955c9d2a2e51e2baa9ab23095d2533125154fd43e58dfc1f07ac9fc3882) |
| 113 | unichain | ReputationUpdated | provider=0x8281..cDeF | [`0x094eb955…`](https://sepolia.uniscan.xyz/tx/0x094eb955c9d2a2e51e2baa9ab23095d2533125154fd43e58dfc1f07ac9fc3882) |

| loop leg | seconds |
|---|---:|
| schedule: job posted -> providers assigned | 1 |
| window closed -> settled | 100 |
| settled -> reputation on Unichain | 3 |

## Job 3

Reactive transactions on Lasna: **5**, callbacks requested: **5** (3 to Base, 2 to Unichain).

| t+s | chain | event | details | tx |
|---:|---|---|---|---|
| 0 | lasna | ProvidersSelected | providers=0x6fF5..39b6,0x998b..B28D,0x8281..cDeF | [`0xc17c8d45…`](https://lasna.reactscan.net/tx/0xc17c8d45f02c51298f78c4af1d67e4c1a1ea1dcde34bca4ba18bd698ba9a81fd) |
| 0 | lasna | CallbackSent | -> base.assignProviders() | [`0xc17c8d45…`](https://lasna.reactscan.net/tx/0xc17c8d45f02c51298f78c4af1d67e4c1a1ea1dcde34bca4ba18bd698ba9a81fd) |
| 1 | base | JobCreated |  | [`0x85c6b61d…`](https://sepolia.basescan.org/tx/0x85c6b61d17362880f847898757bf4760781697b6c11c1f70df2cc91ba7f46068) |
| 2 | base | ProvidersAssigned | providers=0x6fF5..39b6,0x998b..B28D,0x8281..cDeF | [`0xb13be7e7…`](https://sepolia.basescan.org/tx/0xb13be7e70ade115c00c2c425831c0a477ecf3c349f3f06e58fb9fbd48bb0e64d) |
| 6 | base | StageCommitted | stage=0 provider=0x6fF5..39b6 | [`0x36a2f48b…`](https://sepolia.basescan.org/tx/0x36a2f48ba8c9f9b6b1c85600d0f010b12783b1bf652aaa4a3b1cc12a9a899ab9) |
| 197 | lasna | TimerFired | phase=Running expired | [`0xa66eff21…`](https://lasna.reactscan.net/tx/0xa66eff21ccb47ed14147d8cd96f175f951beabb65afb9138868a30acecda1382) |
| 197 | lasna | CallbackSent | -> base.timeoutStage() | [`0xa66eff21…`](https://lasna.reactscan.net/tx/0xa66eff21ccb47ed14147d8cd96f175f951beabb65afb9138868a30acecda1382) |
| 198 | lasna | CallbackSent | -> unichain.recordTimeout() | [`0x72f99006…`](https://lasna.reactscan.net/tx/0x72f99006a907fd36bc6d8a5d8e6f859427f8115ae1ebc568c7a842e91c01b013) |
| 199 | base | StageTimedOut | stage=1 provider=0x998b..B28D | [`0x07346ed4…`](https://sepolia.basescan.org/tx/0x07346ed4c5d223162a69768ab5d7937ce573feed847d70321ec6ca943a5d113f) |
| 199 | base | StageReassigned | stage=1 newProvider=0x17d2..87fC | [`0x07346ed4…`](https://sepolia.basescan.org/tx/0x07346ed4c5d223162a69768ab5d7937ce573feed847d70321ec6ca943a5d113f) |
| 201 | unichain | ProviderTimedOut | provider=0x998b..B28D | [`0x9553c4d2…`](https://sepolia.uniscan.xyz/tx/0x9553c4d2b5a98a6578a9ed7e7c9bd4ba2494f978453c173211cc0c73afd71e18) |
| 204 | base | StageCommitted | stage=1 provider=0x17d2..87fC | [`0xa5f3a95c…`](https://sepolia.basescan.org/tx/0xa5f3a95c085e8de18a638162638c569902d20558699b040e56974e25af2b6fb5) |
| 209 | base | StageCommitted | stage=2 provider=0x8281..cDeF | [`0x51ac7d86…`](https://sepolia.basescan.org/tx/0x51ac7d866c8faef541cd6e0166a4d5049de86e33712e2e478b849b488a31e642) |
| 209 | base | ResultProposed |  | [`0x51ac7d86…`](https://sepolia.basescan.org/tx/0x51ac7d866c8faef541cd6e0166a4d5049de86e33712e2e478b849b488a31e642) |
| 313 | lasna | TimerFired | phase=Proposed expired | [`0x38cdb558…`](https://lasna.reactscan.net/tx/0x38cdb558b0e136a54616cea448024a22b7a7876d2b0f8ea2a4b2fc13bcc2d51c) |
| 313 | lasna | CallbackSent | -> base.settle() | [`0x38cdb558…`](https://lasna.reactscan.net/tx/0x38cdb558b0e136a54616cea448024a22b7a7876d2b0f8ea2a4b2fc13bcc2d51c) |
| 314 | lasna | CallbackSent | -> unichain.recordSuccess() | [`0xec3274e7…`](https://lasna.reactscan.net/tx/0xec3274e7e20b02d65210d34a0d8a175c1ebeeca0ad5561d6d8d8a7398da9d66c) |
| 315 | base | JobSettled |  | [`0x44bc75d3…`](https://sepolia.basescan.org/tx/0x44bc75d3c83bba1f537b9c6f764bb22b4f36a8e1b71f0535d35a4be010f28312) |
| 317 | unichain | ReputationUpdated | provider=0x6fF5..39b6 | [`0x09a61880…`](https://sepolia.uniscan.xyz/tx/0x09a618802dd331323b99a6846a53e85c1f12604b8aa9d59f16234d9b5e83675d) |
| 317 | unichain | ReputationUpdated | provider=0x17d2..87fC | [`0x09a61880…`](https://sepolia.uniscan.xyz/tx/0x09a618802dd331323b99a6846a53e85c1f12604b8aa9d59f16234d9b5e83675d) |
| 317 | unichain | ReputationUpdated | provider=0x8281..cDeF | [`0x09a61880…`](https://sepolia.uniscan.xyz/tx/0x09a618802dd331323b99a6846a53e85c1f12604b8aa9d59f16234d9b5e83675d) |

| loop leg | seconds |
|---|---:|
| schedule: job posted -> providers assigned | 1 |
| deadline missed -> stage rerouted | 2 |
| window closed -> settled | 106 |
| settled -> reputation on Unichain | 2 |
