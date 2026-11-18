# LOOM design

LOOM is presented the way mature AI-infrastructure products present
themselves: a calm marketing site that shows the product, with a working app
behind it in the same visual language. The reference is together.ai's
structure (floating nav with dropdowns, two-tone headline, model cards, a
tabbed platform section with real screenshots and code, a research band,
metrics, a sitemap footer). The explorer pages follow network explorers like
Akash Stats and Reactscan: dense tables, every hash a link.

## Information architecture

```
Home /                      what LOOM is, live cards, platform tabs, research, proof metrics
Product
  Post a job /post          playground: input, estimate, the API call, your jobs
  Rent out a GPU /provide   CLI steps, rules, pay per stage
  Proof /proof              key numbers, the three contracts, one row per scenario with its proving tx
Explorer
  Overview /explorer        chart, network right now, stat cards, latest jobs / txs, testnet panel
  Jobs /jobs, /jobs/:id     table; detail with overview rows, pipeline, dispute trail, txs
  GPUs /gpus                table with filters
  Agents /agents            agents table, activity with filters
  Transactions              all three chains, paginated, Local devnet / Testnet switch
Docs → GitHub README
```

Navigation is the same everywhere: a full-width header bar pinned to the top
of the window (translucent, blurred, hairline bottom border). It holds the
logo, Product ▾, Explorer ▾, Proof and Docs, with GitHub and **Post a job** on
the right. Dropdown
entries carry an icon, a name and a one-line description. App pages add a
breadcrumb, a title with one line underneath, search (`/` focuses it) and an
underlined sub-nav for the explorer pages. On phones the nav collapses to a
full-screen menu. Every page has a real URL, so links, refresh and the back
button work. Old paths (`/marketplace`, `/ledger`) redirect.

## Visual language

The theme is dark.

| Token | Value | Use |
|---|---|---|
| `--bg` / `--card` | `#0b0c0f` / `#111317` | page, panels and nav |
| `--soft` / `--soft2` | `#15181d` / `#1c2026` | table headers, hovers, chips, pressed segments |
| `--line` / `--line2` | `#22262d` / `#2e333b` | borders |
| `--ink` / `--mut` / `--faint` | `#eceef1` / `#a1a7b1` / `#6f7680` | text |
| `--inv` / `--inv-ink` | `#f2f3f5` / `#0b0c0f` | primary buttons, pressed filters, toasts |
| `--link` / `--ok` | `#4ade9a` / `#34d399` | tx links, success |
| `--bad` / `--warn` | `#f87171` / `#fbbf24` | faults, timeouts |
| `--base` / `--uni` / `--lasna` | `#6f9bff` / `#ff7ab8` / `#34d399` | chain dots |
| brand | `#3b6cff` → `#7b5cff` → `#ff6a3d` | the logo's three bars (three stages), the hero slabs |
| `--navy` | `#0a0f24` | research band |

- **Type:** Geist for text, Geist Mono for buttons, tags, hashes and amounts.
  Buttons are square-cornered, mono and uppercase: the primary one is white
  with dark text, the secondary one dark grey. Headlines are two-tone: the
  claim in near-white, the qualifier in grey.
- **Hero art:** a product visual, not a diagram. It is drawn in SVG at load
  time:
  - a glossy isometric GPU die with pins and a 3×3 tile grid, its diagonal
    lit in the three stage colours (blue, purple, orange);
  - silk-like threads in the same colours weaving behind and over the die,
    which is the "loom": compute woven across GPUs;
  - three mono callouts with leader lines: Bonded GPUs, Verified layers,
    Refereed on-chain.

  Light shimmers along the threads and the lit tiles breathe. Both stop under
  `prefers-reduced-motion`. There is no announcement bar and no status line
  under the buttons: the hero is the headline, one sentence, two buttons and
  the artwork.
- **Showing, not telling:**
  - live cards for the model, GPUs and agents;
  - platform tabs that pair a short accordion with live tables and the real
    API call;
  - proof metrics taken from the recorded testnet run.

## Post a job

A two-column playground:
- **Left:** the model (with its three stage chips), the input (sample
  reviews or paste up to 12), and a collapsed fault test for demos.
- **Right, sticky:** the estimate (payment split per stage, challenge window),
  the **Post job** button, the matching `curl` / Python request (it updates as
  you type), and your recent jobs.

After posting, the job's page opens as soon as the referee assigns it.

## Proof

Every transaction hash links to its explorer when the chain has one. Local
devnet hashes have no public explorer, so they show as text, with a pointer to
`/proof` and to the Testnet view on Transactions. `/proof` is deliberately
short: four numbers, the three contracts, and a table with one row per
scenario. Each row shows the transaction that proves its outcome (the slash on
Unichain, the settlement on Base, the timeout on Base) and an "All txs" link to
the full list on the Transactions page.

## Responsiveness

Every page uses the full window width, with 40px side gutters (16px on
phones), and the header spans edge to edge. Charts are drawn at their real
pixel width, so text never stretches. Below 1180px, side columns stack. Below 1040px, the nav collapses to the menu button. Below 900px, the
hero and platform panels stack. Below 640px, secondary table columns hide and
the page never scrolls sideways (checked at 390px on every page).
