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
  Proof /proof              the testnet run: contracts, scenarios, checks, legs, every tx
Explorer
  Overview /explorer        chart, network right now, stat cards, latest jobs / txs, testnet panel
  Jobs /jobs, /jobs/:id     table; detail with overview rows, pipeline, dispute trail, txs
  GPUs /gpus                table with filters
  Agents /agents            agents table, activity with filters
  Transactions              all three chains, paginated, Local devnet / Testnet switch
Docs → GitHub README
```

Navigation is the same everywhere: a floating nav card (logo, Product ▾,
Explorer ▾, Proof, Docs) with GitHub and **Post a job** beside it. Dropdown
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
- **Hero art:** an original isometric illustration of the three stages as
  stacked slabs, with mono callouts for the blocks each stage runs. It floats
  gently and stops under `prefers-reduced-motion`.
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
`/proof` and to the Testnet view on Transactions. Both show the recorded run on
Reactive Lasna, Base Sepolia and Unichain Sepolia with every hash linked.

## Responsiveness

The content width is 1360px on marketing pages. Below 1180px, side columns
stack. Below 1040px, the nav collapses to the menu button. Below 900px, the
hero and platform panels stack. Below 640px, secondary table columns hide and
the page never scrolls sideways (checked at 390px on every page).
