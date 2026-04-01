# High Score Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a high-water mark line to the per-episode score chart and a new cross-episode high-score progression chart to the S3 viewer.

**Architecture:** Client-side only changes in `viewer/index.html`. The episode index (`episodes/index.json`) already contains per-episode scores. We compute the running high score from this data and render it in two places: as a dashed line on the existing chart, and as a new staircase chart.

**Tech Stack:** Vanilla JS, Canvas 2D API (matching existing chart code)

---

### File Map

- **Modify:** `viewer/index.html`
  - Add global `cachedEpisodeIndex` variable (~line 644, state section)
  - Add `<canvas>` element and `<h2>` for new chart (~line 552, after existing score chart)
  - Add CSS for new chart (~line 366, after `.score-chart` styles)
  - Modify `loadEpisodeIndex()` (~line 1124) to cache the index
  - Modify `renderScoreChart()` (~line 1084) to accept and draw high-water mark
  - Add `renderHighScoreProgression()` function (~line 1121, after `renderScoreChart`)
  - Modify `renderState()` (~line 804) to pass high score and trigger progression chart

No new files. No backend changes.

---

### Task 1: Cache episode index and compute high score

Currently `loadEpisodeIndex()` fetches the index but doesn't store it. We need it available when rendering charts.

- [ ] **Step 1: Add global state variable for cached index**

In `viewer/index.html` around line 645 (after `let scoreHistory = [];`), add:

```js
let cachedEpisodeIndex = { episodes: [] };
```

- [ ] **Step 2: Cache index in `loadEpisodeIndex()`**

In `loadEpisodeIndex()` at line 1125, after `const index = await fetchEpisodeIndex();`, add:

```js
  cachedEpisodeIndex = index;
```

- [ ] **Step 3: Add `getHighScore()` helper**

After the `cachedEpisodeIndex` declaration (~line 646), add:

```js
function getHighScore(excludeEpisodeId) {
  let best = 0;
  for (const ep of cachedEpisodeIndex.episodes) {
    if (ep.episode_id !== excludeEpisodeId && (ep.score || 0) > best) {
      best = ep.score;
    }
  }
  return best;
}
```

- [ ] **Step 4: Commit**

```bash
git add viewer/index.html
git commit -m "feat(viewer): cache episode index and add getHighScore helper"
```

---

### Task 2: Draw high-water mark line on existing score chart

Modify `renderScoreChart()` to accept an optional `highScore` parameter and draw a dashed horizontal line.

- [ ] **Step 1: Update `renderScoreChart` signature and add high-water mark drawing**

Replace the existing `renderScoreChart` function (lines 1084–1121) with:

```js
// === Score Chart ===
function renderScoreChart(scores, highScore) {
  const ctx = scoreCanvas.getContext('2d');
  const w = scoreCanvas.width = scoreCanvas.offsetWidth * 2;
  const h = scoreCanvas.height = 160;
  ctx.clearRect(0, 0, w, h);

  if (!scores || scores.length < 2) return;

  const max = Math.max(...scores, highScore || 0, 1);
  const padding = 10;
  const graphW = w - padding * 2;
  const graphH = h - padding * 2;

  // High-water mark line (draw first so score line renders on top)
  if (highScore && highScore > 0) {
    const markY = h - padding - (highScore / max) * graphH;
    ctx.save();
    ctx.strokeStyle = 'rgba(212, 160, 23, 0.6)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([6, 4]);
    ctx.beginPath();
    ctx.moveTo(padding, markY);
    ctx.lineTo(padding + graphW, markY);
    ctx.stroke();
    ctx.setLineDash([]);
    // Label
    ctx.fillStyle = 'rgba(212, 160, 23, 0.8)';
    ctx.font = '16px monospace';
    ctx.textAlign = 'right';
    ctx.fillText(`Best: ${highScore}`, w - padding, markY - 4);
    ctx.restore();
  }

  // Score line
  ctx.strokeStyle = '#4fc3f7';
  ctx.lineWidth = 2;
  ctx.beginPath();

  for (let i = 0; i < scores.length; i++) {
    const x = padding + (i / (scores.length - 1)) * graphW;
    const y = h - padding - (scores[i] / max) * graphH;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // Fill under the line
  ctx.lineTo(padding + graphW, h - padding);
  ctx.lineTo(padding, h - padding);
  ctx.closePath();
  ctx.fillStyle = 'rgba(79, 195, 247, 0.1)';
  ctx.fill();

  // Score label
  ctx.fillStyle = '#ffd54f';
  ctx.font = '22px monospace';
  ctx.textAlign = 'right';
  ctx.fillText(scores[scores.length - 1], w - padding, padding + 22);
}
```

Key changes from original:
- Second parameter `highScore`
- `max` calculation includes `highScore` so the Y-axis scales to fit both
- Dashed gold line drawn at the high-score Y position before the main line
- "Best: N" label above the dashed line

- [ ] **Step 2: Update the `renderScoreChart` call site in `renderState()`**

At line 809, replace:

```js
  renderScoreChart(scoreHistory);
```

with:

```js
  const highScore = getHighScore(currentEpisodeId);
  renderScoreChart(scoreHistory, highScore);
```

- [ ] **Step 3: Commit**

```bash
git add viewer/index.html
git commit -m "feat(viewer): add high-water mark line to per-episode score chart"
```

---

### Task 3: Add cross-episode high-score progression chart

Add the HTML, CSS, and rendering function for the new staircase chart.

- [ ] **Step 1: Add CSS for the new chart**

After the `.score-chart canvas { width: 100%; height: 80px; }` rule (line 371), add:

```css
.highscore-chart {
  padding: 0.5rem;
  background: var(--bg-card);
  border-radius: 6px;
  margin-top: 0.5rem;
}
.highscore-chart canvas { width: 100%; height: 100px; }
```

- [ ] **Step 2: Add HTML for the new chart**

After the closing `</div>` of the score-chart (line 552), add:

```html

    <h2 style="margin-top:1rem">High Score Progression</h2>
    <div class="highscore-chart">
      <canvas id="highscore-canvas" height="100"></canvas>
    </div>
```

- [ ] **Step 3: Add DOM reference**

After the `const scoreCanvas` line (line 665), add:

```js
const highscoreCanvas = document.getElementById('highscore-canvas');
```

- [ ] **Step 4: Add `renderHighScoreProgression()` function**

After the `renderScoreChart` function, add:

```js
// === High Score Progression Chart ===
function renderHighScoreProgression() {
  const ctx = highscoreCanvas.getContext('2d');
  const w = highscoreCanvas.width = highscoreCanvas.offsetWidth * 2;
  const h = highscoreCanvas.height = 200;
  ctx.clearRect(0, 0, w, h);

  const episodes = cachedEpisodeIndex.episodes;
  if (!episodes || episodes.length < 2) return;

  // Sort chronologically (index may be reverse-chronological)
  const sorted = [...episodes]
    .filter(e => e.started_at)
    .sort((a, b) => a.started_at.localeCompare(b.started_at));

  if (sorted.length < 2) return;

  // Compute running high score (staircase)
  const points = [];
  let runningMax = 0;
  for (const ep of sorted) {
    const s = ep.score || 0;
    if (s > runningMax) runningMax = s;
    points.push({ id: ep.episode_id, highScore: runningMax });
  }

  const max = Math.max(runningMax, 1);
  const padding = 10;
  const labelArea = 30;  // bottom space for episode labels
  const graphW = w - padding * 2;
  const graphH = h - padding - labelArea;

  // Staircase line
  ctx.strokeStyle = 'rgba(212, 160, 23, 0.9)';
  ctx.lineWidth = 2.5;
  ctx.beginPath();

  let prevY = null;
  for (let i = 0; i < points.length; i++) {
    const x = padding + (i / (points.length - 1)) * graphW;
    const y = padding + graphH - (points[i].highScore / max) * graphH;
    if (i === 0) {
      ctx.moveTo(x, y);
    } else {
      // Staircase: horizontal to new X, then vertical to new Y
      ctx.lineTo(x, prevY);
      ctx.lineTo(x, y);
    }
    prevY = y;
  }
  ctx.stroke();

  // Fill under the staircase
  const lastX = padding + ((points.length - 1) / (points.length - 1)) * graphW;
  ctx.lineTo(lastX, padding + graphH);
  ctx.lineTo(padding, padding + graphH);
  ctx.closePath();
  ctx.fillStyle = 'rgba(212, 160, 23, 0.08)';
  ctx.fill();

  // Current high score label
  ctx.fillStyle = '#ffd54f';
  ctx.font = '22px monospace';
  ctx.textAlign = 'right';
  ctx.fillText(runningMax, w - padding, padding + 22);

  // Episode ID labels on X-axis (show subset to avoid overlap)
  ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
  ctx.font = '14px monospace';
  ctx.textAlign = 'center';
  const maxLabels = Math.floor(graphW / 60);
  const step = Math.max(1, Math.ceil(points.length / maxLabels));
  for (let i = 0; i < points.length; i += step) {
    const x = padding + (i / (points.length - 1)) * graphW;
    ctx.fillText(points[i].id, x, h - 4);
  }
  // Always label the last one
  if ((points.length - 1) % step !== 0) {
    const x = padding + graphW;
    ctx.fillText(points[points.length - 1].id, x, h - 4);
  }
}
```

- [ ] **Step 5: Call `renderHighScoreProgression()` from `renderState()`**

At the call site where we already added `getHighScore` (after `renderScoreChart`), add:

```js
  renderHighScoreProgression();
```

So the block becomes:

```js
  const highScore = getHighScore(currentEpisodeId);
  renderScoreChart(scoreHistory, highScore);
  renderHighScoreProgression();
```

- [ ] **Step 6: Also render progression chart on episode index load**

At the end of `loadEpisodeIndex()`, after the episode selection logic (~line 1150), add:

```js
  renderHighScoreProgression();
```

This ensures the progression chart updates even when browsing episodes (since the index refreshes every 30s).

- [ ] **Step 7: Commit**

```bash
git add viewer/index.html
git commit -m "feat(viewer): add cross-episode high-score progression chart"
```

---

### Task 4: Visual verification

- [ ] **Step 1: Run local viewer server**

```bash
uv run scripts/serve_viewer_local.py
```

Open `http://localhost:8001` in a browser.

- [ ] **Step 2: Verify per-episode chart**

- Select an episode from the dropdown
- Confirm the blue score line renders as before
- If other episodes exist with scores, confirm a gold dashed "Best: N" line appears

- [ ] **Step 3: Verify high-score progression chart**

- Confirm "High Score Progression" heading appears below the per-episode score chart
- Confirm a gold staircase line is visible showing the running high score across episodes
- Confirm episode ID labels appear on the X-axis
- Confirm the chart is empty/hidden when fewer than 2 episodes exist

- [ ] **Step 4: Commit final state if any fixes were needed**

```bash
git add viewer/index.html
git commit -m "fix(viewer): high score chart visual fixes"
```
