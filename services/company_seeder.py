"""
Fetch all Taiwan (TWSE) and US (NASDAQ) listed tech stocks
and upsert them into the supply_chain companies table.
"""

import re
import requests
from html.parser import HTMLParser
from services.supply_chain import _db

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# TWSE industry name → our category label
TW_INDUSTRY_CATEGORY = {
    "半導體業":        "半導體",
    "電腦及周邊設備業": "消費電子",
    "光電業":          "光電",
    "通信網路業":      "通信網路",
    "電子零組件業":    "電子零組件",
    "電子通路業":      "電子通路",
    "資訊服務業":      "資訊服務",
    "其他電子業":      "其他電子",
}

# US industry keyword → category
US_INDUSTRY_CATEGORY = [
    ("semiconductor",  "半導體"),
    ("memory",         "記憶體"),
    ("storage",        "記憶體"),
    ("equipment",      "半導體設備"),
    ("cloud",          "雲端"),
    ("internet",       "雲端"),
    ("software",       "雲端"),
    ("saas",           "雲端"),
    ("data",           "雲端"),
    ("network",        "通信網路"),
    ("communication",  "通信網路"),
    ("hardware",       "消費電子"),
    ("computer",       "消費電子"),
    ("consumer",       "消費電子"),
    ("electronic",     "電子零組件"),
    ("service",        "資訊服務"),
]


# ── HTML table parser (no extra deps) ────────────────────────────────────────

class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self._row, self._cell, self._in_td = [], [], "", False

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            self._in_td, self._cell = True, ""

    def handle_endtag(self, tag):
        if tag == "td" and self._in_td:
            self._row.append(self._cell.strip())
            self._in_td = False
        elif tag == "tr":
            if self._row:
                self.rows.append(self._row[:])
            self._row.clear()

    def handle_data(self, data):
        if self._in_td:
            self._cell += data


# ── Taiwan (TWSE) ─────────────────────────────────────────────────────────────

def fetch_tw_tech_stocks():
    """Scrape TWSE ISIN page → filter tech industries."""
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=25)
        resp.encoding = "big5"
        parser = _TableParser()
        parser.feed(resp.text)

        results = []
        for row in parser.rows:
            if len(row) < 5:
                continue
            industry = row[4].strip()
            if industry not in TW_INDUSTRY_CATEGORY:
                continue
            # Cell 0 format: "2330　台積電" (full-width space 　)
            m = re.match(r"(\d{4,6})[　\s]+(.+)", row[0])
            if not m:
                continue
            ticker = m.group(1).strip()
            name   = m.group(2).strip()
            if ticker and name:
                results.append({
                    "ticker":   ticker,
                    "name":     name,
                    "category": TW_INDUSTRY_CATEGORY[industry],
                    "country":  "TW",
                })
        print(f"[Seeder] TWSE → {len(results)} tech stocks")
        return results
    except Exception as e:
        print(f"[Seeder] TWSE error: {e}")
        return []


# ── United States (NASDAQ screener) ──────────────────────────────────────────

def _us_category(industry_str):
    s = (industry_str or "").lower()
    for kw, cat in US_INDUSTRY_CATEGORY:
        if kw in s:
            return cat
    return "其他科技"


def fetch_us_tech_stocks():
    """Fetch US tech stocks from NASDAQ screener API."""
    url = "https://api.nasdaq.com/api/screener/stocks"
    params = {"tableonly": "true", "limit": 5000, "download": "true"}
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=25)
        rows = resp.json().get("data", {}).get("rows", [])
        results = [
            {
                "ticker":   row["symbol"],
                "name":     row.get("name", ""),
                "category": _us_category(row.get("industry", "")),
                "country":  "US",
            }
            for row in rows
            if row.get("sector", "").lower() == "technology" and row.get("symbol")
        ]
        print(f"[Seeder] NASDAQ → {len(results)} US tech stocks")
        return results
    except Exception as e:
        print(f"[Seeder] NASDAQ error: {e}")
        return []


# ── DB upsert ─────────────────────────────────────────────────────────────────

def upsert_companies(companies):
    """Insert new companies (skip existing tickers)."""
    added = 0
    with _db() as conn:
        for c in companies:
            if not c.get("ticker") or not c.get("name"):
                continue
            exists = conn.execute(
                "SELECT 1 FROM companies WHERE ticker = ?", (c["ticker"],)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO companies (name, ticker, category, country) VALUES (?,?,?,?)",
                    (c["name"], c["ticker"], c.get("category", "其他科技"), c.get("country", "TW")),
                )
                added += 1
    return added


def run_seeder():
    tw = fetch_tw_tech_stocks()
    us = fetch_us_tech_stocks()
    added = upsert_companies(tw + us)
    print(f"[Seeder] Done — {added} new companies added (scanned {len(tw)+len(us)} total)")
    return {"tw_found": len(tw), "us_found": len(us), "added": added}
