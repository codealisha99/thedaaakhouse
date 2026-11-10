# thedaaakhouse — design direction

## What the product is

A job-search workspace: every application is one record that carries its job
description analysis, the resume version that was sent, ATS runs, fit
evaluation, company research, interview prep, study plans, arena drills,
and approved outreach email. Its promise is **evidence over invention**:
tailoring reorders real bullets, ATS scores show their maths, and nothing
missing from the profile is made up.

*Daak* means post. The product already models applications as mail moving
through a route (Drafted → Posted → In transit → Out for delivery →
Delivered / Return to sender / Dead letter). That route is the most
product-specific idea in the codebase, so the visual identity is built on it.

## Three directions explored

| | A. Registered Post (chosen) | B. Dispatch Console | C. Night Terminal |
|---|---|---|---|
| Philosophy | Calm, editorial logistics. Every application is a tracked item with a route and a paper trail. | Dense operator tool, keyboard-first, maximum rows per screen. | The existing retro green terminal, refined. |
| Identity | Warm ivory paper, deep ink, one vermilion "post-box" accent, tracking numbers in mono, route lines with stops. | Graphite surfaces, cool white, violet accent. | Phosphor green on black, pixel display type. |
| Layout | Asymmetric editorial headers, generous margins, ledger-style tables, slips with tear lines. | Split panes, inspector drawers, tight 32px rows. | Boxed panels, hard shadows. |
| Interaction | Quiet hovers, deliberate stamps on status change, ⌘K to jump anywhere. | Everything has a shortcut; minimal motion. | Blinking cursors, press-down buttons. |
| Landing | Headline set in a display serif, a live tracking slip as the hero visual, the route as the narrative spine. | Product screenshot wall. | ASCII art hero. |
| Dashboard | "Today": what needs attention, pipeline route, activity stream. | KPI strip + giant table. | Stat cards. |
| Why / why not | Native to the product's name and data model; distinctive without being a costume. | Competent but indistinguishable from every SaaS tool. | Memorable but tiring, low legibility for long reading (JDs, resumes). |

The previous codebase mixed C with a skeuomorphic postal pass (washi tape,
emoji trucks, rotated paper). A keeps the postal idea but expresses it as
logistics, not decoration: no rotated cards, no emoji, no textures.

## Colour

Three palettes considered:

1. **Ink & Vermilion (chosen)** — ivory `#F4F1EA`, ink `#16181D`, airmail navy `#1D2B45`, vermilion `#C8401F`.
2. Graphite & Violet — `#111214`, `#F6F7F9`, `#6D4AFF`. Generic for this product.
3. Forest & Lime — `#14271E`, `#F3F0E4`, `#B6D33C`. Pleasant, but reads "sustainability brand".

| Token | Light | Dark | Use |
|---|---|---|---|
| `bg` | `#F4F1EA` | `#0F1013` | page |
| `surface` | `#FBF9F4` | `#17181C` | panels |
| `sunken` | `#ECE8DE` | `#0B0C0E` | wells, table heads |
| `line` / `line-strong` | `#DDD7CA` / `#C5BDAC` | `#26282E` / `#383B44` | borders |
| `ink` / `ink-2` / `ink-3` | `#16181D` / `#45484F` / `#64666E` | `#EEEBE3` / `#B9B6AE` / `#8E8C86` | text hierarchy (all ≥ 4.5:1 on bg) |
| `brand` | `#1D2B45` | `#A9BCE3` | secondary primary, links, selected nav |
| `accent` | `#C8401F` | `#F07150` | one primary CTA per screen, "current stop", focus ring |
| `ok` / `warn` / `bad` | `#2E7D4F` / `#9A5F0C` / `#B3261E` | `#6FCB94` / `#E3A94B` / `#FF8A7A` | semantic, always paired with text or icon |

Route stages have their own tokens (`stage-*`) so status reads the same on the
board, badges, and charts.

## Typography

Chosen: **Instrument Serif** (display only) + **Geist** (UI and body) + **Geist Mono** (tracking IDs, scores, dates, data).
Considered Inter + Geist Mono (safe, no personality) and Manrope + IBM Plex Mono
(friendly, but weaker numerals).

| Role | Style |
|---|---|
| Display | Instrument Serif 56–96px, tight leading, optional italic for one word |
| Page heading | Instrument Serif 36–44px |
| Section heading | Geist 15px semibold |
| Body | Geist 14–16px, 1.55 leading |
| Label | Geist Mono 11px uppercase, 0.08em tracking |
| Data | Geist Mono, tabular numerals |

## Motion

| Token | Value | Use |
|---|---|---|
| `--ease-out` | `cubic-bezier(.2,.8,.2,1)` | entrances, hovers |
| `--ease-in-out` | `cubic-bezier(.65,0,.35,1)` | drawers, route progress |
| `--dur-1` | 120ms | hover, press |
| `--dur-2` | 200ms | menus, tabs, toasts |
| `--dur-3` | 360ms | page entrance, drawers |

Rules: content enters once (fade + 6px rise, staggered 40ms); status changes
"stamp" once; nothing loops except loading skeletons; all motion collapses
under `prefers-reduced-motion`.

## Signature elements

- **Route**: a line with stops for the seven stages; the current stop is vermilion.
- **Tracking ID**: `DH-4F2A91` in mono on every application.
- **Tear line**: a dashed rule separating a slip's header from its details.
