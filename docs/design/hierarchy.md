# Design hierarchy

How every page in the app is put together: the forecast stepper (`/`) and futures mode
(`/futures`). Colors, type and spacing are tokens in `static/tokens.css`; components are
in `static/ui.js` (styled by `static/ui.css`); the top bar and breadcrumb are in
`static/shell.js`. Tests in `tests/test_design_tokens.py` and `tests/test_ui_components.py`
hold the rules below.

## Levels, top to bottom

| Level | What | Style | Where it comes from |
|---|---|---|---|
| 0 | App bar | 52px, fixed. Brand · Forecast \| Futures · the open run's question · name · theme | `AppBar` (shell.js) |
| 1 | Page head | Breadcrumb (`--text-sm`, muted) → title (Kode Mono, `--text-lg`) with the page's actions on the right of the title row → one line of lede (`--text-base`, muted) | `Crumbs`, `PageHead` |
| 2 | Section heading | Kode Mono, `--text-md`, 24px above, 8px below | `h2` |
| 3 | Item title | Barlow 600, `--text-md`: a run's question, a claim, an edge | list rows, cards |
| 4 | Body | Barlow, `--text-base` | |
| 5 | Meta / hint | Barlow, `--text-sm`, muted: scope, dates, counts, explanations | `.hint`, `.list-row-scope` |
| 6 | Uppercase label | Kode Mono, uppercase, tracked: the brand, mode switch, tabs, drawer kind only | |

Every page has a level-1 head, including the Graph tab and an exploration (whose title is
its goal). Hints say what something is or does; they are never the only place an action
lives.

## Type scale

`--text-mark` 9.5 · `--text-xs` 11 · `--text-sm` 12 · `--text-base` 14 · `--text-md` 15 ·
`--text-lg` 18. Stylesheets use these tokens, never pixel sizes. `--text-mark` is only for
marks inside cards (tiny chips, order badges).

Kode Mono is the display and data face (titles, headings, uppercase labels, years,
counts); Barlow is everything you read. In both themes.

## Spacing

4 · 8 · 12 · 16 · 24. Pages have 24px padding. Cards (`Panel`) have 16px padding and 12px
between them. Section headings have 24px above.

## Page layouts

Three, each starting from the page's own left edge:

| Layout | Pages | Content |
|---|---|---|
| **List** | Forecast runs (`/`), Futures explorations | A centred 880px column: page head, then a `List` of `ListRow`s |
| **Step / form** | Each forecast step (Ask, Sources, Run, Sign-off, Brief), New exploration | A 720px reading column; in the stepper it sits on the left edge beside the step rail, so moving between steps never shifts the page |
| **Workspace** | Graph tab, an exploration | Full width: page head, then the canvas |

## List rows

`ListRow` (runs, explorations): a fingerprint, the title you scan, a quiet scope line, an
outcome line, and status / date on the right. The title is the row's link and stretches
over the row (⌘-click and middle-click open a new tab); row actions sit above it.

The fingerprint (`shape_glyph.js`) is the item's graph drawn small without labels, in the
same layered grammar as the Graph tab (source | signal | entity | projections by order), so
fingerprints differ by density and width rather than random shape. An item without a graph
shows its pipeline steps instead. Chosen from a prototype of four list formats (branch
`prototype/runs-list`, variant D).

## Not on reading surfaces

Token counts, latency and eval scores are trace and operator concerns. They stay in the
API (`/api/runs/{id}/metrics`), the exports and the traces, for a later run-summary view.
