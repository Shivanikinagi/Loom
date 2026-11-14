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

## Story, top to bottom

| Section | Background | What it says | Data |
|---|---|---|---|
| Hero | black, teal arcs | "Inference you can verify". A chip labelled LOOM (the referee) is wired to nodes B (Base), U (Unichain), R (Reactive) and G (GPUs); light pulses travel along the traces. | network, Reactive clock state |
| Chain tiles | glass on black | The three contracts, each tile linking to its explorer | contract addresses |
| Steps | black | Split → Commit → Referee, three glowing icons joined by diamonds | none |
| Marketplace | white sheet | "Rent GPUs / backed by bonds". Stat chips, then one card per GPU | providers, stats |
| Live job | white | "One model / three GPUs". Job tabs and a split card: glowing panel (job, status, escrow) plus mint panel (stages, verdicts, answers) | selected job |
| Ledger | deep green band | "Every step / on three chains" and the word *Refereed*. A vertical timeline with one dot per event, coloured by chain | timeline, tx links |
| Agents | white with dot field | "Who checked / the work". The watcher and verifier feed | agent reports |

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
