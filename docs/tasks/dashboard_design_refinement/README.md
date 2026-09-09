# Handoff: Opinion Dynamics Dashboard — Refinement

## Overview
Refined visual design for the opinion-dynamics simulation monitoring dashboard (the one in the `isl-opinion-dynamics-dashboard` GitHub repo, `dashboard.html`). Goal: cleaner, tech/simple/cool visual language, less visual noise, English-only labels, light/dark theme support. This package documents that new design so it can be reimplemented in the real app.

## About the Design Files
The bundled file (`Opinion Dynamics Dashboard.dc.html`) is a **design reference built in HTML** — a prototype showing the intended look, layout, and lightweight interactions (theme toggle, pause, metric selection, seed/legend toggles, network graph switch). It is **not production code to copy in directly**. The task is to **recreate this design inside the target codebase's existing environment** — reuse `dashboard.html`'s existing structure/data plumbing (Python/JS glue, chart rendering, live data hookup) and apply the new visual design on top of it, rather than replacing the working app with this static prototype.

## Fidelity
**High-fidelity.** Colors, spacing, typography, and component styling below are final; recreate them pixel-for-pixel using the codebase's existing chart/rendering approach. The chart data itself in the prototype is randomly generated sample data for visualization purposes only — the real app must keep driving these charts from its live Python simulation output.

## Screens / Views
Single scrollable dashboard page, vertical stack, max content width unconstrained (fluid), page padding `34px 38px 48px`.

### 1. Page Header
- Layout: flex row, `justify-content: space-between`, wraps on narrow widths, gap `20px`.
- Left: `<h1>` "Opinion Dynamics — Live Monitor", 21px / weight 800 / letter-spacing -0.02em.
- Below title: small status line, 11.5px, color `--faint`, icon (activity/pulse SVG, 12×12) + text: `"running {n} · done {n} · failed {n} · updated {time}"`.
- Right: control cluster (flex row, gap 8px):
  - **Pause/Resume pill button**: 7×14px padding, full pill radius (999px), border `--line`, background `--panel`, 11.5px/600 weight, icon (pause bars / play triangle) + label.
  - **Interval select** (pill, same sizing): options "every 5s / every 10s / every 30s".
  - **Theme toggle button**: 32×32 circular icon button, border `--line`, background `--panel`; sun icon in dark mode, moon icon in light mode.

### 2. Seed Strip
- Flex row of pill chips, wraps, gap 8px, margin-top 20px.
- Each chip: flex row, gap 6px, padding `7px 14px`, pill radius, border `--line`, background `--panel`, 11.5px.
  - Colored dot (8px circle) = seed's series color.
  - Bold label `s{seed}` (11.5px/700).
  - Status label 11px/600, colored by status: done = `--good`, failed = `--bad`, running = `--warn`. Text: "✓ done" / "✕ failed" / "● running".
  - Percent label, 11px, `--faint`, tabular-nums, right-aligned in chip.
  - Click toggles that seed's visibility across all charts (dims chip to 40% opacity when hidden).

### 3. Status Line
- Single line, 11.5px, color `--sub`, top border `--line`, padding-top 10px, margin-top 10px.
- Content: `"{N} seeds · {running} running · {done} done · {failed} failed · {avg}% avg progress"`.
- Replaces what was previously 4 separate KPI cards — deliberately de-emphasized/compact per latest direction.

### 4. Metrics Section ("Trends over time")
- Eyebrow label "METRICS" (11px/700, uppercase, letter-spacing .09em, `--faint`), then heading "Trends over time" (15px/700).
- **Metric filter chips**: pill row, gap 8px. Active chip = white text on gradient (`--lapis-mid` → `--lapis`) with soft shadow; inactive = bordered `--panel` with `--sub` text. Click toggles that metric's chart on/off. Available metrics: Disagreement, Apparent Polarization, Unfollow Count, Post Count, Repost Share, Bimodality Coeff. Default visible: first 4.
- **Metric cards grid**: `repeat(auto-fit, minmax(280px,1fr))`, gap 20px. Each card: white/panel bg, 1px `--line` border, 14px radius, padding `16px 18px`, subtle shadow.
  - Header row: metric label (12.5px/600) + delta badge (11px/700, colored green/red/gray depending on whether the trend is favorable for that metric).
  - Line chart (inline SVG, viewBox 300×150): one line per visible seed, 2px stroke, seed's color; 3 horizontal gridlines with axis value labels (9px, `--faint`).

### 5. Outcome Plane + Opinion Distribution (2-column row, 1.5fr/1fr, gap 40px)
- **Outcome Plane card**: title "Outcome Plane" (14px/700) + subtitle "assortativity × bimodality — per-seed trajectory (faint→solid = early→now)" (11px, `--faint`). SVG scatter/trail: one path + endpoint dot per visible seed, seed color, path opacity 0.55, dot radius 5 with panel-colored stroke ring.
- **Opinion Distribution card**: title + seed `<select>` dropdown (pill, 11px). Subtitle: "stacked share of opinion bins over time (−1 to +1)". Stacked-area SVG chart, 5 bins, bin color ramp from blue (negative) through neutral gray to red (positive). Legend row below: 5 swatches with bin-range labels (`[-1,-0.6)` … `[0.6,1]`).

### 6. Network Snapshot (full width card)
- Title "Network Snapshot" + subtitle "node radius ∝ √followers, color = opinion (blue −1 to red +1)".
- Toggle pair top-right: "follow graph" / "repost graph" pills, active = gradient fill like metric chips.
- SVG force-layout-style snapshot (640×340 viewBox) on a `--panel-soft` rounded background: edges as thin `--line` strokes, nodes as circles sized by degree, colored via a blue→neutral→red gradient by opinion value, two visible clusters (left/right).
- Bottom gradient legend bar (160×12, rounded), labeled `−1` … `+1`.

### 7. Network Structure Section
- Eyebrow "STRUCTURE" + heading "Network Structure".
- 3-column grid (1.2fr/1fr/1fr, gap 22px):
  1. **Degree Distribution (CCDF)** card: in/out/total toggle (small text pills, active = `--lapis-100` bg + `--lapis` text), log-scale CCDF curve (solid `--lapis`) + power-law fit overlay (dashed `--warn`), 3 gridlines with labels.
  2. **Structure Stats** card: label/value row list — clustering coeff., betweenness (giant, mean), giant component fraction, λ₂ algebraic connectivity. Label 11.5px `--sub`, value 14px/600 tabular-nums, right-aligned.
  3. **Q_sign / E-I index** card: dual-line chart (Q_sign in `--lapis`, E-I index in `--gold`/cyan), legend swatches below.

### 8. Agent Behavior & Attributes Section
- Eyebrow "BEHAVIOR" + heading "Agent Behavior & Attributes".
- 2×2 grid, gap 20px, same card chrome as above:
  - **Mean Repost Depth** — single line chart, `--lapis` stroke.
  - **Repost Share of Content** — single line chart, `--gold` stroke.
  - **Bounded Confidence Distribution** — bar histogram, `--lapis-mid` fill.
  - **Post Probability Distribution** — bar histogram, `--gold` fill.

## Interactions & Behavior
- **Theme toggle**: swaps `data-theme` between `light`/`dark`; every color is a CSS custom property so both themes reuse the same markup.
- **Pause/Resume**: toggles paused state (button icon/label swap); wire to whatever mechanism stops live data polling in the real app.
- **Seed chip click**: toggles that seed out of/into all seed-aware charts (metric lines, outcome-plane trails), dims the chip when hidden.
- **Metric chip click**: toggles that metric's card in/out of the Metrics grid.
- **Network follow/repost toggle**: swaps which edge set the Network Snapshot renders.
- **Degree distribution in/out/total toggle**: swaps which degree definition drives the CCDF chart and fit line.
- No modals, no page navigation — everything is in-place state on one view.

## State Management
- `theme`: "light" | "dark"
- `paused`: boolean
- `hidden`: Set of seed ids currently hidden
- `metrics`: array of currently-visible metric ids (order-preserving)
- `netType`: "follow" | "repost"
- `degreeMode`: "in" | "out" | "total"
- All chart data in the prototype is deterministically generated from seeded PRNGs for stable-looking placeholder charts — replace with real simulation output keyed the same way (per seed, per metric, per timestep).

## Design Tokens
Colors (light / dark):
- `--bg`: #f6f7f9 / #0a0d12
- `--panel`: #ffffff / #12161f
- `--panel-soft`: #f0f2f5 / #171c26
- `--ink`: #0b0f19 / #f2f4f8
- `--sub`: #5b6472 / #9aa4b2
- `--faint`: #98a2b3 / #5b6472
- `--line`: #e4e7ec / #1f2530
- `--lapis` (primary): #2563eb / #3b82f6
- `--lapis-mid`: #3b82f6 / #60a5fa
- `--lapis-100`: #dbeafe / #16283f
- `--lapis-50`: #eff6ff / #101c2c
- `--good`: #16a34a / #22c55e
- `--warn`: #d97706 / #f59e0b
- `--bad`: #dc2626 / #ef4444
- `--gold` (secondary accent, actually cyan): #0891b2 / #22d3ee
- Series palette (5 seeds, light): #2563eb, #0891b2, #16a34a, #d97706, #dc2626
- Series palette (5 seeds, dark): #3b82f6, #22d3ee, #22c55e, #f59e0b, #ef4444
- Opinion-bin ramp (light): #2563eb → #93b8f0 → #c9ccd3 → #f0a99a → #dc2626

Typography: **Inter**, weights 400/500/600/700/800. Base body ~11.5–15px, section headings 15px/700, page title 21px/800, eyebrow labels 11px/700 uppercase with 0.09em tracking.

Spacing/shape: card radius 14px, card padding `16-20px / 18-22px`, pill radius 999px, card border 1px `--line`, card shadow `0 1px 2px rgba(11,15,25,.05)` (light) / `0 1px 2px rgba(0,0,0,.4)` (dark). Section vertical rhythm ~30px between major sections.

## Assets
No external image/icon assets — all icons are inline SVG (activity, play/pause, sun/moon), stroke-based, 2px stroke width, 12–14px size.

## Files
- `Opinion Dynamics Dashboard.dc.html` — full design reference (HTML/inline-JS prototype) implementing everything above, including sample-data generation logic for reference on what data shape each chart expects.
