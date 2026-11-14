# LOOM evidence — local sample run (real GPT-2)

Generated 2026-11-14 19:55:56 India Standard Time.

> Local run on three anvil chains with the real chain IDs. Reactive's relaying is emulated by
> `loom/local_reactive.py`; on testnet the same contracts are driven by Reactive Lasna itself.

## Contracts

| Role | Chain | Address |
|---|---|---|
| LoomReferee (reactive) | lasna (5318007) | `0x5FbDB2315678afecb367f032d93F642f64180aa3` |
| LoomEscrow | base (84532) | `0x5FbDB2315678afecb367f032d93F642f64180aa3` |
| LoomBonds | unichain (1301) | `0x5FbDB2315678afecb367f032d93F642f64180aa3` |

## Job 1 — fraud caught + rerouted

**PASS** in 26.5s

- [x] watcher challenged
- [x] quorum found stage 1 faulty
- [x] stage 1 rerouted to a standby GPU
- [x] cheater slashed on Unichain
- [x] job settled
- [x] cheater paid nothing
- [x] payouts == payment

Result labels: positive, negative, positive, negative, positive, negative

Reactive transactions on Lasna: **6**, callbacks requested: **5** (3 to Base, 2 to Unichain).

| t+s | chain | event | details | tx |
|---:|---|---|---|---|
| 0 | base | JobCreated |  | `0xec5c915c…` |
| 0 | lasna | ProvidersSelected | providers=0x5278..6C2a,0x4B33..575F,0x0D93..6cA8 | `0x88f8344f…` |
| 0 | lasna | CallbackSent | -> base.assignProviders() | `0x88f8344f…` |
| 1 | base | ProvidersAssigned | providers=0x5278..6C2a,0x4B33..575F,0x0D93..6cA8 | `0x15ac26c4…` |
| 1 | base | StageCommitted | stage=0 provider=0x5278..6C2a | `0x7f2e17fa…` |
| 2 | base | StageCommitted | stage=1 provider=0x4B33..575F | `0xfd24d941…` |
| 3 | base | StageCommitted | stage=2 provider=0x0D93..6cA8 | `0x2cc9c6be…` |
| 3 | base | ResultProposed |  | `0x2cc9c6be…` |
| 5 | base | Challenged | stage=1 round=1 accused=0x4B33..575F | `0x3b13376c…` |
| 7 | lasna | VoteCounted | round=1 faulty=True votesFaulty=1 votesHonest=0 | `0xffcb568b…` |
| 7 | base | VerdictVote | round=1 faulty=True | `0xb8de0b13…` |
| 7 | base | VerdictVote | round=1 faulty=True | `0x69a80652…` |
| 7 | base | VerdictVote | round=1 faulty=True | `0xc3417e98…` |
| 7 | lasna | VoteCounted | round=1 faulty=True votesFaulty=2 votesHonest=0 | `0x13f819ee…` |
| 7 | lasna | QuorumReached | round=1 faulty=True accused=0x4B33..575F replacement=0x7565..A60E | `0x13f819ee…` |
| 7 | lasna | CallbackSent | -> base.resolveFault() | `0x13f819ee…` |
| 7 | base | FaultResolved | stage=1 faulty=0x4B33..575F | `0x42dd5b5e…` |
| 7 | base | StageReassigned | stage=1 newProvider=0x7565..A60E | `0x42dd5b5e…` |
| 8 | lasna | CallbackSent | -> unichain.slash() | `0x796f20cd…` |
| 8 | unichain | ProviderSlashed | provider=0x4B33..575F amount=0.05 ETH bounty=0.025 ETH | `0xf4f829f0…` |
| 8 | base | StageCommitted | stage=1 provider=0x7565..A60E | `0xab440186…` |
| 10 | base | StageCommitted | stage=2 provider=0x0D93..6cA8 | `0xf4c09706…` |
| 10 | base | ResultProposed |  | `0xf4c09706…` |
| 26 | lasna | TimerFired | phase=Proposed expired | `0x66d83aa7…` |
| 26 | lasna | CallbackSent | -> base.settle() | `0x66d83aa7…` |
| 26 | base | JobSettled |  | `0xaea758ad…` |
| 27 | unichain | ReputationUpdated | provider=0x5278..6C2a | `0x8ff2370f…` |
| 27 | unichain | ReputationUpdated | provider=0x7565..A60E | `0x8ff2370f…` |
| 27 | unichain | ReputationUpdated | provider=0x0D93..6cA8 | `0x8ff2370f…` |
| 27 | lasna | CallbackSent | -> unichain.recordSuccess() | `0xac1e8839…` |

| loop leg | seconds |
|---|---:|
| schedule: job posted -> providers assigned | 1 |
| challenge -> Reactive counts quorum | 2 |
| quorum vote -> fault resolved on Base | 0 |
| fault resolved on Base -> slashed on Unichain | 1 |
| window closed -> settled | 23 |
| settled -> reputation on Unichain | 1 |

## Job 2 — honest job settles

**PASS** in 18.5s

- [x] no challenge
- [x] settled by Reactive's clock
- [x] slashed GPU not scheduled

Result labels: positive, negative, positive, negative, positive, negative

Reactive transactions on Lasna: **3**, callbacks requested: **3** (2 to Base, 1 to Unichain).

| t+s | chain | event | details | tx |
|---:|---|---|---|---|
| 0 | base | JobCreated |  | `0xb7f0fa24…` |
| 0 | lasna | ProvidersSelected | providers=0x5278..6C2a,0x0D93..6cA8,0x7565..A60E | `0x9342b158…` |
| 0 | lasna | CallbackSent | -> base.assignProviders() | `0x9342b158…` |
| 1 | base | ProvidersAssigned | providers=0x5278..6C2a,0x0D93..6cA8,0x7565..A60E | `0xdfcaecd1…` |
| 1 | base | StageCommitted | stage=0 provider=0x5278..6C2a | `0x67a9327b…` |
| 2 | base | StageCommitted | stage=1 provider=0x0D93..6cA8 | `0x8ae28c97…` |
| 2 | base | StageCommitted | stage=2 provider=0x7565..A60E | `0xa6d18f24…` |
| 2 | base | ResultProposed |  | `0xa6d18f24…` |
| 18 | lasna | TimerFired | phase=Proposed expired | `0x7877d2d1…` |
| 18 | lasna | CallbackSent | -> base.settle() | `0x7877d2d1…` |
| 18 | base | JobSettled |  | `0x51963192…` |
| 18 | lasna | CallbackSent | -> unichain.recordSuccess() | `0xfb5b8422…` |
| 19 | unichain | ReputationUpdated | provider=0x5278..6C2a | `0x8edc6398…` |
| 19 | unichain | ReputationUpdated | provider=0x0D93..6cA8 | `0x8edc6398…` |
| 19 | unichain | ReputationUpdated | provider=0x7565..A60E | `0x8edc6398…` |

| loop leg | seconds |
|---|---:|
| schedule: job posted -> providers assigned | 1 |
| window closed -> settled | 16 |
| settled -> reputation on Unichain | 1 |

## Job 3 — offline GPU rerouted

**PASS** in 55.1s

- [x] stage timed out
- [x] rerouted away from offline GPU
- [x] timeout penalty on Unichain
- [x] job still settled

Reactive transactions on Lasna: **5**, callbacks requested: **5** (3 to Base, 2 to Unichain).

| t+s | chain | event | details | tx |
|---:|---|---|---|---|
| 0 | base | JobCreated |  | `0xfc408b80…` |
| 0 | lasna | ProvidersSelected | providers=0x5278..6C2a,0x0D93..6cA8,0x7565..A60E | `0xbec2acde…` |
| 0 | lasna | CallbackSent | -> base.assignProviders() | `0xbec2acde…` |
| 1 | base | ProvidersAssigned | providers=0x5278..6C2a,0x0D93..6cA8,0x7565..A60E | `0xd61c6dd4…` |
| 1 | base | StageCommitted | stage=0 provider=0x5278..6C2a | `0x9d4d3689…` |
| 36 | lasna | TimerFired | phase=Running expired | `0x6ecc0d99…` |
| 36 | lasna | CallbackSent | -> base.timeoutStage() | `0x6ecc0d99…` |
| 36 | base | StageTimedOut | stage=1 provider=0x0D93..6cA8 | `0xc6158144…` |
| 36 | base | StageReassigned | stage=1 newProvider=0x20E0..EE16 | `0xc6158144…` |
| 37 | lasna | CallbackSent | -> unichain.recordTimeout() | `0x39fe4305…` |
| 37 | base | StageCommitted | stage=1 provider=0x20E0..EE16 | `0xc295a582…` |
| 37 | unichain | ProviderTimedOut | provider=0x0D93..6cA8 | `0x49a18bca…` |
| 38 | base | StageCommitted | stage=2 provider=0x7565..A60E | `0x6c2dbc21…` |
| 38 | base | ResultProposed |  | `0x6c2dbc21…` |
| 55 | lasna | TimerFired | phase=Proposed expired | `0xdc4cba0a…` |
| 55 | lasna | CallbackSent | -> base.settle() | `0xdc4cba0a…` |
| 55 | base | JobSettled |  | `0xa93cc8ae…` |
| 55 | lasna | CallbackSent | -> unichain.recordSuccess() | `0x9372bc3d…` |
| 55 | unichain | ReputationUpdated | provider=0x5278..6C2a | `0x1e4df64d…` |
| 55 | unichain | ReputationUpdated | provider=0x20E0..EE16 | `0x1e4df64d…` |
| 55 | unichain | ReputationUpdated | provider=0x7565..A60E | `0x1e4df64d…` |

| loop leg | seconds |
|---|---:|
| schedule: job posted -> providers assigned | 1 |
| deadline missed -> stage rerouted | 0 |
| window closed -> settled | 17 |
| settled -> reputation on Unichain | 0 |

## What the agents saw

| role | job | action | detail |
|---|---|---|---|
| gpu0 | 1 | commit | stage 0 in 0.228s |
| gpu1 | 1 | commit | stage 1 in 0.147s (cheat: skip) |
| gpu2 | 1 | commit | stage 2 in 0.427s |
| watcher | 1 | challenge | 3 unproven provider(s) in pipeline |
| verifier0 | 1 | vote FAULTY | max |delta| = 92.16 |
| verifier1 | 1 | vote FAULTY | max |delta| = 92.16 |
| verifier2 | 1 | vote FAULTY | max |delta| = 92.16 |
| gpu3 | 1 | commit | stage 1 in 0.396s |
| gpu2 | 1 | commit | stage 2 in 0.444s |
| watcher | 1 | audit passed | 3 unproven provider(s) in pipeline |
| gpu0 | 2 | commit | stage 0 in 0.315s |
| gpu2 | 2 | commit | stage 1 in 0.319s |
| gpu3 | 2 | commit | stage 2 in 0.39s |
| watcher | 2 | audit passed | 3 unproven provider(s) in pipeline |
| gpu0 | 3 | commit | stage 0 in 0.229s |
| gpu2 | 3 | went offline |  |
| gpu4 | 3 | commit | stage 1 in 0.205s |
| gpu3 | 3 | commit | stage 2 in 0.313s |
| watcher | 3 | audit passed | 3 unproven provider(s) in pipeline |

## Local relay

`{'reacts': 102, 'callbacks': 13, 'callback_failures': 0, 'cron': 49}`
