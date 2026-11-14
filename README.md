# LOOM

**Trustless pooled-GPU inference, refereed by Reactive Network.**

One model is split across several community GPUs. Each GPU commits a hash of
what it produced. If anyone challenges the answer, a reactive contract on
Reactive Lasna referees the dispute across chains: it finds the GPU that
cheated, slashes its bond, pays whoever caught it, pays the honest GPUs, and
reroutes the cheater's layers to a standby GPU. No keeper, no backend, no
human in the loop.

Built for the Reactive Omni Buildathon (Reactive Meets AI track).

> Work in progress — see the commit history for the build phases.
