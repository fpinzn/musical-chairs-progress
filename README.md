# Musical Chairs progress

A conquest map of the Barknito Musical Chairs build, drawn with the
[ASCII Man](https://github.com/fpinzn) glyphs and fed from Linear.

Live: https://fpinzn.github.io/musical-chairs-progress/

## How it refreshes

`.github/workflows/refresh.yml` runs every 30 minutes, on every push and on
manual dispatch. It runs `tools/refresh.py` with the `LINEAR_API_KEY` repo
secret, writes `site/data/progress.json`, and deploys `site/` to GitHub Pages.
The JSON is never committed. The open page re-fetches it every five minutes and
whenever the tab regains focus. Worst case the page is about 35 minutes behind
Linear.

Force a refresh: `gh workflow run refresh.yml -R fpinzn/musical-chairs-progress`.

## Reading the map

- The body is the release, M0 at the feet to M7 at the head. Cells are ordered
  bottom-up by due date, then dependency depth. One task is a contiguous run of
  cells sized by its days of attention. The radiating rings are M8 and M9.
- Cyan contours are phase lines: where the front should be on each due date.
- The heavy yellow contour is where the front should be today. The white line
  is where it is, in days done.
- Done cells render at MLP quality in daylight. In-progress cells flicker.
  To-do cells drift as Markov noise at night. Blocked cells are dark.
- Red hatch: a pocket, a task due on or before today and not done.
  Cyan hatch: a salient, a task done before its due date.
- The strip above is the same data as a terminal: one row per milestone, one
  cell per tenth of a day, dates at the phase boundaries, a yellow marker at
  today's planned position and a white bar at the done boundary.
- Hover or tap a cell for the task. Tap a milestone label for its task list.
  Click a cell to open the issue in Linear.

## Preview states

- `?today=2026-10-06` renders the map as of another date.
- `?sim=5.2` marks the first 5.2 days of the plan done, for a look at the
  fill, pockets and salients without touching Linear.

## Rebuilding the assets

The glyph sheet, the night sheet, the body mask and the trimmed frames come
from the ASCII Man export:

```
python tools/trim_frames.py <ascii-man>/07-web-export-runtime/public/data/frames.bin.gz site/data/frames.bin.gz
python tools/build_assets.py <ascii-man>/07-web-export-runtime/public
```

`tools/fixture.json` is a snapshot of the Linear data for local work:
copy it to `site/data/progress.json` and serve `site/` with any static server.
