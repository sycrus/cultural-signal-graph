# Design hierarchy

How every page in the app is put together: the forecast stepper (`/`) and futures mode
(`/futures`). Colors, type and spacing are tokens in `static/tokens.css`; components are
in `static/ui.js` (styled by `static/ui.css`); the top bar and breadcrumb are in
`static/shell.js`. Tests in `tests/test_design_tokens.py` and `tests/test_ui_components.py`
hold the rules below.

## Levels, top to bottom

| Level | What | Style | Where it comes from |
|---|---|---|---|
| 0 | App bar | 52px, fixed, three zones: logotype (home) · the open run's question, centred · Forecast \| Futures, name, theme | `AppBar` (shell.js) |
| 1 | Page head | Breadcrumb (`--text-sm`, muted) → title (Kode Mono, `--text-lg`) with the page's actions on the right of the title row → one line of lede (`--text-base`, muted) | `Crumbs`, `PageHead` |
| 2 | Section heading | Kode Mono, `--text-md`, 24px above, 8px below | `h2` |
| 3 | Item title | Barlow 600, `--text-md`: a run's question, a claim, an edge | list rows, cards |
| 4 | Body | Barlow, `--text-base` | |
| 5 | Meta / hint | Barlow, `--text-sm`, muted: scope, dates, counts, explanations | `.hint`, `.list-row-scope` |
| 6 | Uppercase label | Kode Mono, uppercase, tracked: tabs and the drawer kind only | |

**Logotype.** A signal trace (a pulse on a flat line, in the accent hue, glowing in the
dark theme) and "cultural signal graph" in lowercase Kode Mono. The mode switch sits
apart from it, at the right, in plain sentence case, so it can't read as part of the
name. Chosen from three in a prototype (branch `prototype/app-bar`, logotype C).

Every page has a level-1 head, including the Graph tab and an exploration (whose title is
its goal). Hints say what something is or does; they are never the only place an action
lives.

## Tabs: three weights, one per level

| Weight | Where | Look |
|---|---|---|
| **Solid** (filled pill) | Only the app bar's Forecast \| Futures switch: which app you are in. Sentence case, active in the mode's hue | `AppBar` |
| **Line** (underline) | Tabs within a page: Brief \| Graph, the futures lenses (Scroll, Wheel, Cone…) | `Tabs variant="line"`: no box, `--text-sm`, active in ink with an underline in the mode's hue |
| **Soft** (tinted segment) | A choice inside a form or a toolbar: what to add, Fit / 1.5× / 2× / 3× | `Tabs variant="soft"` |

A page's tabs never look like the mode switch: switching a lens is a smaller act than
switching apps.

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

Three, all centred on the page, with the scrollbar's space always reserved so a page that
scrolls keeps the same centre:

| Layout | Pages | Content |
|---|---|---|
| **List** | Forecast runs (`/`), Futures explorations | An 880px column: page head, then a `List` of `ListRow`s |
| **Step / form** | Each forecast step (Ask, Sources, Run, Sign-off, Brief), New exploration | A 720px reading column |
| **Workspace** | The Graph tab; an exploration | The Graph tab keeps its header (breadcrumb, tabs, title) in the same 720px column as every step, so switching Brief ↔ Graph never moves it; the graph sits below, centred, at most 1080px wide. An exploration is full width: its lenses need the room. |

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
