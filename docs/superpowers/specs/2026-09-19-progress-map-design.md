# Musical Chairs progress map

A single public web page that shows the state of the Barknito Musical Chairs
build as a conquest map, drawn with the ASCII Man glyphs and fed from Linear.
Its two jobs, in order: aesthetic pleasure that motivates progress, and
legibility of planned versus actual progress.

## Where it lives

- Repo `fpinzn/musical-chairs-progress`, public, served by GitHub Pages at
  `https://fpinzn.github.io/musical-chairs-progress/`.
- The game repo stays private. Task titles, dates and statuses are visible to
  anyone with the URL; accepted for now.

## Refresh

- `.github/workflows/refresh.yml` runs every 30 minutes, on manual dispatch and
  on push to `main`. It runs `tools/refresh.py` with the `LINEAR_API_KEY`
  secret, writes `site/data/progress.json`, and deploys `site/` with the Pages
  deploy action. The JSON is never committed.
- The page re-fetches the JSON every five minutes and on tab focus.
- A monthly keepalive job makes an empty commit so GitHub does not pause the
  schedule after 60 days of inactivity.

## Data

`tools/refresh.py` queries the Linear GraphQL API for every issue in the
project "Barknito Musical Chairs" and writes:

```json
{
  "generatedAt": "2026-09-19T21:00:00Z",
  "project": "Barknito Musical Chairs",
  "tasks": [
    {
      "id": "MC-013", "issue": "BARK-263", "title": "Game HUD to the Figma design",
      "milestone": "M1", "milestoneName": "M1 Core loop",
      "status": "backlog | started | completed | canceled",
      "effort": 0.6, "due": "2026-09-23",
      "blockedBy": ["MC-011"], "completedAt": null, "startedAt": null
    }
  ]
}
```

- `effort` is parsed from the description line `Estimate: X days of attention`.
  Linear's estimate field is empty because it rejects fractions.
- `status` is the Linear state type, not the state name.
- `blockedBy` comes from the issue's inverse relations of type `blocks`.
- Nothing about the plan is static in the page except the body mask.

## State rules

Shared by both panels.

| Cell state | Condition | Rendering |
|:--|:--|:--|
| done | status completed | true frame, MLP quality, day layer |
| contested | status started | automata quality, half-tone flicker |
| todo | backlog, not blocked, due after today | global Markov noise, night layer |
| blocked | backlog with an unfinished blocker | dark, outline only |
| pocket | not completed and due on or before today | night layer with red hatch and the id |
| salient | completed and due after today | day layer with forward hatch |

Today is the viewer's local date. Effort done is the sum of `effort` over
completed tasks. Planned effort is the sum over tasks due on or before today.
Schedule delta is done minus planned, in days of attention.

## Panel 1: the strip

Terminal-like. One row per milestone M0 to M7, then M8 and M9 dimmed.
Within a row, tasks in due-date then dependency order, one 16 px glyph cell per
tenth of a day, so MC-013 is six cells and MC-064 is one. Issue ids under the
runs. Due dates printed at the phase boundaries inside the row, in the
conquest-map style: a tick and `SEP 24`. Today's boundary as a vertical rule
down the whole strip. Cells render by the state rules using the bitmap
glyphs from the sprite sheet.

## Panel 2: the figure

The ASCII Man human figure on its 70 by 126 grid.

- The body mask assigns rows to tasks bottom-up in due-date then dependency
  order, each task's row count proportional to its effort, so the reveal
  height and the plan agree by construction. M8 and M9 are the radiating rings
  outside the body.
- Phase lines: wherever the due date changes, a thin contour crosses the body
  with the date in the margin. Today's contour is heavier and pulses.
- The actual front is the union of done cells, jagged. A thin straight line at
  the cumulative-effort height gives the single-number summary.
- Salients and pockets render as in the state rules.
- The critical path (longest chain by effort to MC-064) is a thin trace up the
  spine.
- Callouts: leader lines from each milestone band to a monospace uppercase
  label in the margin, `M1 CORE LOOP  2.4d  4/9`. Hovering or tapping a band
  expands the label into its task list.
- Cartouche: corner box with the operation name, front as of today's date,
  days done over total, schedule delta with sign.

## Rendering

- Assets: `site/glyphs.png` (the 324-glyph sprite sheet, 16 px cells) and
  `site/data/frames.bin.gz`, trimmed from the ASCII Man export to the three
  models the page uses (global Markov, automata, MLP).
- Animation ping-pongs through the frames as the original viewer does. Each
  cell picks its model by state; the day/night compositing is per cell rather
  than a vertical split.
- One HTML file, canvas rendering, no build step, no framework.
- Works at phone width: the strip scrolls horizontally, the figure scales to
  fit.

## Out of scope

Editing tasks from the page. Auth. Sharing controls. Historical playback of
the front over time (a later idea: keep one JSON per day and scrub).

## Build order

1. `tools/refresh.py` and the workflow, verified with one manual run and a
   deployed `progress.json`.
2. The strip.
3. The figure with the conquest layer.
