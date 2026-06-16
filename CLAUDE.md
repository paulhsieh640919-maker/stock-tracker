# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Taiwan stock analyst recommendation tracker. A Python script fetches daily prices and patches them into a self-contained HTML file, which is the entire frontend. No build step, no package manager.

## Commands

**Run the price updater locally:**
```bash
pip install requests beautifulsoup4 yfinance
python3 update.py
```

**Serve the frontend locally:**
```bash
python3 -m http.server 8080
# then open http://localhost:8080/index.html
```

There are no tests, no linter, and no build process.

## Architecture

### Two-file design

- **`index.html`** — the entire frontend: HTML structure, embedded CSS, and all JavaScript in one file. All data (`PRICES` and `PICKS`) is hardcoded as JavaScript variables inside a `<script>` tag. Rendering is pure DOM manipulation; no framework.
- **`update.py`** — a standalone Python script that fetches current stock prices, regex-patches the `PRICES` object in `index.html`, then commits and pushes the change.

### How prices are updated

`update.py` targets 50 Taiwan stock codes and tries three data sources in priority order:
1. **Yahoo Finance** (`yfinance`) — `.TW` suffix for TWSE stocks, `.TWO` for OTC
2. **cnyes.com** — HTML scraping with BeautifulSoup
3. **TWSE API** — direct REST call

`fetch_all_prices()` merges results across all three; `update_html()` replaces the `PRICES = { ... }` block in `index.html` using a regex. The script performs `git pull → git add → git commit → git push` automatically.

### Data structures (inside `index.html`)

```javascript
// Current prices keyed by stock code string
PRICES = { '2317': 123.5, '2330': 890, ... }

// Analyst recommendations
PICKS = [
  { t: '2317', n: '鴻海', a: 'buy', rec: 110, ana: '葉俊敏', theme: '...' },
  ...
]
```

`a` is `'buy'`, `'sell'`, or `'hold'`. `rec` is the analyst's recommended entry price (can be `null`). Three analysts are tracked: 葉俊敏 (A1), 何基鼎 (A2), 郭哲榮 (A3).

### Tabs in the frontend

`index.html` renders six tabs:
1. **Dashboard** — summary cards and highlights
2. **個股清單** (Stock List) — all picks with current price vs. recommended price
3. **驗證更新** (Verify Updates) — raw data verification table
4. **準確率排行** (Accuracy Rankings) — per-analyst win/loss accuracy
5. **三師交叉** (Three-Analyst Cross) — stocks recommended by 2+ analysts
6. **說明** (About) — explanatory notes

### GitHub Actions

`.github/workflows/update-stocks.yml` runs `python3 update.py` on a schedule (weekdays at 06:00 UTC / 14:00 Taiwan time) and on manual dispatch. The workflow handles the git commit/push after the script updates `index.html`.

## Key conventions

- The `PRICES` block in `index.html` must remain on a single line for the regex in `update.py` to match it correctly: `PRICES = { ... }` with no newlines inside.
- Stock codes for `PICKS` must also exist in the `STOCK_CODES` list in `update.py` or they will have no price data.
- When running `update.py` in CI (env `CI=true`), the script skips interactive prompts and uses the GitHub Actions git identity.
