# LOOM design

LOOM's interface is the storefront of an AI inference marketplace. Buyers rent
GPT inference, GPU owners rent out layers, and a reactive contract referees
them. The page should read as a serious verifiable-compute product, not a
crypto dashboard.

The visual direction follows a dark-to-light "verifiable AI" landing style:
- a black hero with sweeping teal light arcs and a glowing chip wired to
  surrounding nodes;
- a white sheet that slides up over it;
- deep-green type with a mint second line;
- a split card pairing a glowing green visual with a mint panel;
- a deep-green band with a vertical dot timeline.

We use the layout and mood only. The name, logo, copy and data are LOOM's own.

## Pages

The landing page is separate from the four working pages. Every page has
its own URL. The dashboard server returns the same `index.html` for each
path, and the page renders itself from the URL, so links, refresh and the
back button all work.

The inner pages follow the console patterns of KINETIC: a compact header
(breadcrumb, title, one line, and the page's main action on the right),
KPI cards, filter chips with counts, a sort menu, and cards or rows below.
The glowing arcs appear only behind the landing hero. Inner headers are a
flat dark band with a faint top glow and a hairline under the nav, so
nothing crosses the title. Content fills the window width (up to 1760px with
48px gutters, 16px on phones), and every page reaches the bottom of the
window, with the footer pinned to the end.

| Path | Header action | White sheet | Data |
|---|---|---|---|
| `/` | (full hero) | Small chip animation (520px) wired to B/U/R/G nodes, the CTA, chain tiles linked to explorers, the Split → Commit → Referee steps, then four page cards with live numbers | contracts, counts |
| `/post` | GPUs online | A two-column form, like KINETIC's Run page. Left: Model (GPT-2 listing with its three stage chips), Task (sentiment), Data (sample reviews, or paste up to 12 of your own), Rules (payment, deadlines, quorum, from the escrow), and a collapsed "Test the referee" demo control. Right: Estimate (payment split per stage by layers, typical time, Post job) and Your jobs | params, stages, jobs |
| `/marketplace` | Rent out a GPU | KPIs (available, total bonded, paid to GPUs, bonds slashed), filters (All / Available / Busy / Slashed), sort (reputation, earned, bond, jobs). Each GPU card shows earnings, a status pill, bond, reputation, jobs served, what it is doing right now, a passed/failed bar and expandable details | providers, settlements |
| `/provide` | View marketplace | Its own page, in the menu as "Rent out a GPU". KPIs (minimum bond, paid per job, paid to GPUs, stages served). Numbered steps: requirements, bond and register (CLI), serve stages (CLI), then "Good to know". Side: earnings per job by stage, "How a GPU earns" and a link to the marketplace | params, stages, settlements |
| `/jobs` | Post a job | Job tabs and the split card: glowing panel (job, status, escrow) plus mint panel (stages, verdicts, answers) | selected job |
| `/ledger` | Post a job | Job tabs and a deep-green card: the word *Refereed*, a chain legend and a vertical timeline with one dot per event, coloured by chain | timeline, tx links |
| `/agents` | agents online | KPIs (audits, challenges, votes, cheaters caught, agreement with quorum). Roster cards for the watcher and three verifiers (role, address, metrics, last action). An activity log with filters (Audits / Challenges / Votes / Faults) and tx links. Side cards: "How a check works" and "Audit policy" | agent reports, timeline, policy |

The marketplace has no behaviour switches. The only way to make a GPU
misbehave is the "Test the referee" control on `/post`, which affects one GPU
for one job (stage 1 or 2), so the catch can be shown in a demo without
changing the GPU's normal behaviour.

The nav is a three-column grid (logo, menu, actions) with the menu in the
middle column, so it sits on the page's centre line, directly above the chip
and its traces. The current page is highlighted in the menu.

## Tokens

| Token | Value | Use |
|---|---|---|
| `--black` | `#000000` | hero, steps, footer |
| `--teal` | `#2fe0a7` | hero arcs, chip glow, icon strokes |
| `--ink` | `#0a3d31` | headings and body on white |
| `--ink-2` / `--ink-3` | `#4f6f64` / `#7f998f` | secondary text, captions |
| `--mint` | `#3fe596` | accents on dark backgrounds |
| `--mint-text` | `#13a560` | accent line in headings on white (≥3:1 at heading size) |
| `--mint-bg` | `#ddf8ea` | mint panel, "available" badges |
| `--band` | `#02473a` | ledger band |
| `--paper` / `--paper-2` | `#ffffff` / `#f4f8f6` | sheet, stat chips and inner tiles |
| `--base` / `--uni` / `--lasna` | `#4f7dff` / `#e5408c` / `#12b886` | chain dots |
| `--ok` / `--bad` / `--warn` | `#12a35f` / `#e0453a` / `#c9851a` | honest / faulty / timeout |

Radii: 32px for the sheet's top corners, 24px for the split card, 18px for
cards, 10–14px for buttons and tiles, and 999px for tags and tabs.

## Type

| Role | Face | Size |
|---|---|---|
| Hero headline | Inter Tight 600, white-to-grey gradient | 44–92px, −0.035em |
| Section headline | Inter Tight 600, ink with a mint second line | 32–50px |
| Body and UI | Inter | 15px / 1.55 |
| Hashes, addresses, numbers | JetBrains Mono | 12–14px, tabular |

## Components

- **Nav.** The LOOM mark (three bars narrowing like stages) on the left. A
  glass pill menu in the centre. On the right: network and clock status, a
  GitHub button outlined in glass, and a white "Post a job" button.
- **Primary CTA.** White, 10px radius, with a green gradient square holding an
  arrow on its left side. The dark version, used on white, holds a plus sign.
- **Glass tile.** 128px wide, with a translucent gradient fill, a hairline
  border and an external-link icon, plus the chain name and contract name.
- **Tag.** Outlined pill with ink text: Marketplace, Live job, Ledger, Agents.
- **GPU card.** Name and status dot, address, a status badge (Available,
  Slashed or Exiting), a grey stats tile (bond, score, jobs, faults) and the
  behaviour selector in interactive mode.
- **Split card.** Left: black with two large mint-rimmed bubbles and white
  highlights at the top, showing the job number underlined, its status and an
  orb (pulsing while live, red while disputed). Right: mint panel with
  chevron rows per stage (a rerouted GPU is struck through, then the
  replacement), then the Caught and Settled verdicts and the answer chips.
- **Timeline.** A 1px rail with chain-coloured dots. Each row has a
  plain-English sentence plus mono metadata: time since the job started,
  chain and explorer link.
- **Dot field.** Scattered mint and sage dots above and below the agents
  heading, kept clear of the text.

## Layout and responsiveness

- Content width is 1200px with 32px gutters, dropping to 16px on phones.
- Below 980px, the menu hides, the split card stacks and the ledger band
  becomes one column.
- Below 640px: the GitHub button hides, the steps stack vertically with a
  vertical connector, GPU cards take the full width and tiles shrink to
  thirds. The page never scrolls sideways (checked at 390px).

## Motion

- Light pulses travel along the chip's traces (2.6–5s loops).
- The orb pulses while a job is running.
- The CTA lifts 1px on hover.
- Everything stops under `prefers-reduced-motion`.

## Copy rules

Plain verbs and real numbers. They are "GPUs", not nodes or miners. Each
section headline is two lines: the claim in ink, the payoff in mint.
