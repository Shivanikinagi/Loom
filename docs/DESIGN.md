# LOOM design

LOOM's interface is a network explorer, modelled on how decentralized
networks present themselves to people who want proof rather than a pitch:
[Akash Network Stats](https://stats.akash.network/) (one dashboard, a big
chart, a "network right now" panel, stat cards with sparklines, latest
tables) and [Reactscan](https://lasna.reactscan.net/) (search by tx or
address, latest transactions, every hash a link). There is no marketing hero
and almost no prose: labels, numbers, tables, and links to transactions.

## Structure

One top bar: the LOOM mark and an `EXPLORER` tag, five tabs, a search box
(job number, tx hash, address or name; `/` focuses it), a live indicator
and the **Post job** button.

| Path | What it shows |
|---|---|
| `/` Overview | A cumulative chart (paid to GPUs / jobs / transactions). "The network, right now" (bonded, busy, running, disputes, total bonded, slashed, Reactive clock). Four stat cards with sparklines. Latest jobs and latest transactions. "Verified on testnet": the three contracts and the three recorded scenarios, all linked |
| `/jobs` | Jobs table with status filters: id, status, stage squares, GPUs, payment, duration, posted tx, age |
| `/jobs/:id` | Explorer-style detail: overview key/value rows (status, buyer, payment, posted and settled tx, payouts, slash, result), the pipeline table (layers, GPU, output hash, commit tx, state), the dispute trail (challenge, each vote, quorum, slash, each with its tx), and every transaction for the job |
| `/gpus` | Stat cards and the GPU table with filters: status, bond, reputation, jobs, faults, earned, right now. "Rent out a GPU" opens `/provide` |
| `/provide` | The two CLI steps, the rules, pay per stage and network numbers |
| `/agents` | Stat cards, the agents table (role, address, checks, flagged, last action) and the activity table with filters. Each row opens its job |
| `/transactions` | Every event across the three chains, paginated, filterable by chain. A **Local devnet / Testnet** switch: the testnet view is the recorded run from `evidence/testnet-run.json`, every hash linked to Reactscan, Basescan or Uniscan |

**Post job** is a dialog, not a page: the model, sample or pasted reviews,
the estimate split per stage, and a collapsed fault test for demos (one GPU
misbehaves on that one job). After posting, the new job's page opens as soon
as the referee assigns it. Old paths (`/marketplace`, `/ledger`, `/proof`,
`/post`) redirect.

## Visual language

| Token | Value | Use |
|---|---|---|
| `--bg` / `--card` / `--card2` | `#0a0b0b` / `#111312` / `#171a19` | page, panels, hover |
| `--line` / `--line2` | `#222725` / `#2f3633` | borders |
| `--ink` / `--mut` / `--faint` | `#edf2ef` / `#9ba6a1` / `#6b7570` | text |
| `--mint` | `#3fe596` | links, the chart, positive states, primary button |
| `--red` / `--amber` | `#ff6b61` / `#f2b45a` | faults / timeouts |
| `--base` / `--uni` / `--lasna` | `#6f9bff` / `#ff7ab8` / `#3fe596` | chain dots |

- Inter for text and numbers. JetBrains Mono for labels (11px, uppercase,
  tracked), hashes, addresses and amounts.
- Panels: 12px radius, 1px borders, no shadows. Headers are a mono label or
  a short title, with a `View all ›` link where there is more.
- Event names appear as monospace pills, like method names on an explorer
  (red for Challenged, QuorumReached and ProviderSlashed, green for
  JobSettled).
- Status is a coloured dot plus a word. Live states pulse (disabled under
  `prefers-reduced-motion`).
- Dark only, like the explorers it follows.

## Proof

Every transaction hash is a link when the chain has a public explorer. The
local devnet has none, so local hashes are plain text with a note pointing to
the testnet run. The Overview's "Verified on testnet" panel and the testnet
switch on Transactions put the real Lasna, Base Sepolia and Unichain Sepolia
transactions one click away.

## Responsiveness

Content fills the window (up to 1760px). Below 1180px the side panels stack.
Below 980px the tabs move to their own row and the detail rows stack. Below
640px, secondary table columns hide, search takes the full width and the page
never scrolls sideways (checked at 390px).
