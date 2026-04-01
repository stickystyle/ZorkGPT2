# High Score Visualization — Design Spec

## Summary

Add two visual features to the S3 viewer (`viewer/index.html`) to track system improvement across episodes:

1. A high-water mark line on the existing per-episode score chart
2. A new cross-episode high-score progression chart

No backend changes. Data source is `episodes/index.json`, already loaded by the viewer.

## Change 1: High-Water Mark on Per-Episode Score Chart

**What:** A dashed horizontal line on the existing per-episode canvas score chart showing the best final score achieved by any other episode in the index.

**Behavior:**
- Compute `Math.max(...episodes.map(e => e.score || 0))` from the episode index, excluding the currently viewed episode
- Draw a dashed horizontal line at that Y value across the full chart width
- Label on the right edge: "Best: {score}"
- Gold/amber color (`#D4A017` or similar), semi-transparent
- Only drawn when: high score > 0 AND at least one other episode has a score

**Purpose:** Shows the current episode's "goal to beat" — the best prior performance.

## Change 2: Cross-Episode High-Score Progression Chart

**What:** A new canvas chart below the existing per-episode score chart showing how the running high score has increased over time.

**Behavior:**
- Sort episodes from `index.json` chronologically (by `started_at`)
- Walk the sorted array computing the running maximum of `episode.score`
- Plot as a staircase line: X-axis is episode index (labeled with episode IDs), Y-axis is score
- Monotonically increasing — line only goes up or stays flat
- Area fill under the line, same visual style as the existing score chart
- Chart title: "High Score Progression"

**Visual details:**
- Same canvas dimensions and styling as existing score chart
- Gold/amber line color to match the high-water mark
- X-axis labels: episode IDs (rotated if needed for space)
- Y-axis: score from 0 to max_score (350 for Zork)
- Only rendered when there are 2+ episodes in the index

**Placement:** Below the existing per-episode score chart in the viewer layout.

## Files Modified

- `viewer/index.html` — all changes in this single file

## Out of Scope

- No changes to `s3_hook.py`, `state_export.py`, or any backend code
- No new S3 files or data formats
- No changes to `serve_viewer_local.py` (it already serves the same index format)
