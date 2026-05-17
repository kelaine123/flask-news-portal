# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
python app.py          # starts Flask on port 5000, fetches news immediately, scheduler starts
```

Environment variables are loaded from `.env` (via `python-dotenv`). Required keys:

```
NEWSAPI_KEY=<newsapi.org key>
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Architecture

### Entry Point — `app.py`

- Calls `init_db()` on import to seed the supply chain SQLite DB if empty
- Starts an `APScheduler` `BackgroundScheduler` at **module level** (not inside `__main__`) so it runs under both `python app.py` and `flask run`
- Scheduler fires `update_news_data()` every 6 hours; also called once immediately in `__main__`
- Two page routes (`/` and `/supply-chain`) and two API namespaces (`/api/news/*` and `/api/supply-chain/*`)

### `services/fetcher.py` — News Pipeline

Fetches from three sources and writes to `data/news.json`:

| Source | Function | Notes |
|---|---|---|
| Google News RSS | `fetch_google_news()` | 6 keyword queries, 3 entries each |
| Yahoo Finance RSS | `fetch_yahoo_finance()` | 6 tickers, 2 entries each |
| NewsAPI.org | `fetch_newsapi()` | Requires `NEWSAPI_KEY` env var |

`_normalize()` deduplicates by title, detects company/ticker from `COMPANY_MAP`, runs keyword sentiment, and extracts tags. Article IDs are `int(md5(url)[:8], 16)` — stable across runs.

`update_news_data()` writes atomically via a `.tmp` file + `os.replace()`.

### `services/supply_chain.py` — Supply Chain DB

SQLite at `data/supply_chain.db`. Two tables: `companies` and `relationships`.

- `init_db()` creates tables and seeds from `_COMPANIES` / `_RELATIONSHIPS` lists if the DB is empty. The DB is **not committed to git** — it is recreated from seed data on every fresh startup.
- `get_graph_data()` returns `{nodes, edges}` for vis-network consumption
- `get_company(id)` returns a company dict with `upstream` and `downstream` arrays

Seed data covers 34 companies (19 TW, others US/KR/NL) and 39 hand-curated relationships. To add new seed data, edit `_COMPANIES` and `_RELATIONSHIPS` in this file.

### Frontend

Two independent pages sharing one stylesheet (`static/css/style.css`):

- **`/`** (`templates/index.html` + `static/js/main.js`) — news card grid with sentiment filter
- **`/supply-chain`** (`templates/supply_chain.html` + `static/js/supply_chain.js`) — vis-network force graph

The supply chain page sets `body { display:flex; flex-direction:column; height:100vh }` in an inline `<style>` block so `sc-layout` fills remaining viewport height without a hardcoded pixel offset. The `#sc-graph` div uses `position:absolute; inset:0` — vis-network requires a pixel-defined bounding box and does not work with `height:100%` on a flex child.

The graph uses persistent `vis.DataSet` objects (`nodesDS`, `edgesDS`). Highlighting calls `.update()` on these sets rather than `network.setData()`, which would destroy and re-register click listeners.

### Data Flow on News Update

```
update_news_data()
  ├── fetch_google_news()
  ├── fetch_yahoo_finance()
  ├── fetch_newsapi()          ← requires NEWSAPI_KEY
  ├── _normalize()             ← dedup, sentiment, company detection
  └── atomic write → data/news.json
```

Supply chain relationships are currently static (seed data only). The planned next step is an LLM-based extractor (`services/extractor.py`) that runs after each news update and calls `add_relationship_if_new(supplier, customer, product)` to persist new relationships discovered from article text.

## Key Design Decisions

- **`DATA_FILE` path in `services/`** uses `dirname(dirname(__file__))` to resolve to the project root, not the `services/` subdirectory.
- **GitHub remote** is `https://kelaine123:<token>@github.com/kelaine123/flask-news-portal.git` — token is embedded in the remote URL, not a stored credential. Do not expose in logs.
- **`.env` is gitignored** — never commit it. `supply_chain.db` is also gitignored.
- The `_company_names_cache` in any future extractor module should be invalidated if new companies are added to the DB at runtime.
