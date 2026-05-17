"""News fetching pipeline — SQLite backend."""
import re
import os
import hashlib
import time
import requests
import feedparser
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from services.supply_chain import save_articles

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")

# ── Company detection map ─────────────────────────────────────────────────────

COMPANY_MAP = {
    # Taiwan
    "台積電": ("2330", "半導體"),    "TSMC": ("2330", "半導體"),
    "聯發科": ("2454", "IC設計"),    "MediaTek": ("2454", "IC設計"),
    "鴻海":   ("2317", "電子製造"),  "Foxconn": ("2317", "電子製造"),
    "廣達":   ("2382", "伺服器"),    "Quanta": ("2382", "伺服器"),
    "台達電": ("2308", "電力電子"),  "Delta Electronics": ("2308", "電力電子"),
    "友達":   ("2409", "面板"),      "AUO": ("2409", "面板"),
    "群創":   ("3481", "面板"),      "Innolux": ("3481", "面板"),
    "聯電":   ("2303", "半導體"),    "UMC": ("2303", "半導體"),
    "日月光": ("3711", "封裝測試"),  "ASE": ("3711", "封裝測試"),
    "華碩":   ("2357", "消費電子"),  "ASUS": ("2357", "消費電子"),
    "宏碁":   ("2353", "消費電子"),  "Acer": ("2353", "消費電子"),
    "緯創":   ("3231", "電子製造"),  "Wistron": ("3231", "電子製造"),
    "英業達": ("2356", "伺服器"),    "Inventec": ("2356", "伺服器"),
    "和碩":   ("4938", "電子製造"),  "Pegatron": ("4938", "電子製造"),
    "瑞昱":   ("2379", "IC設計"),    "Realtek": ("2379", "IC設計"),
    "聯詠":   ("3034", "IC設計"),    "Novatek": ("3034", "IC設計"),
    "欣興":   ("3037", "PCB"),       "Unimicron": ("3037", "PCB"),
    "景碩":   ("3189", "PCB"),
    "台光電": ("2383", "CCL"),
    # US / Global
    "NVIDIA":    ("NVDA",   "IC設計"),
    "AMD":       ("AMD",    "IC設計"),
    "Apple":     ("AAPL",   "消費電子"),
    "Qualcomm":  ("QCOM",   "IC設計"),
    "Intel":     ("INTC",   "半導體"),
    "Microsoft": ("MSFT",   "雲端"),
    "Google":    ("GOOGL",  "雲端"),
    "Meta":      ("META",   "雲端"),
    "Amazon":    ("AMZN",   "雲端"),
    "ASML":      ("ASML",   "半導體設備"),
    "Samsung":   ("005930", "半導體"),
    "SK Hynix":  ("000660", "記憶體"),  "SK海力士": ("000660", "記憶體"),
    "Micron":    ("MU",     "記憶體"),
    "Dell":      ("DELL",   "伺服器"),
    "HP":        ("HPQ",    "伺服器"),
}

# ── Source queries ────────────────────────────────────────────────────────────

GOOGLE_TW_QUERIES = [
    "台積電 半導體",
    "聯發科 晶片",
    "鴻海 AI伺服器",
    "廣達 英業達 伺服器 ODM",
    "日月光 CoWoS 封裝",
    "台達電 電源模組",
    "友達 群創 面板",
    "台灣半導體 供應鏈",
    "台灣AI伺服器 供應",
    "台灣科技股 法說",
    "先進封裝 CoWoS SoIC",
    "台灣PCB 覆銅板",
    "AI晶片 台灣 供應鏈",
    "蘋果 供應商 台灣",
    "HBM 記憶體 供應",
]

GOOGLE_US_QUERIES = [
    "TSMC semiconductor supply chain",
    "NVIDIA AI chip supply Taiwan",
    "AI server ODM Taiwan Quanta Inventec",
    "semiconductor supply chain 2025",
    "Apple supplier Taiwan manufacturing",
    "HBM memory supply chain NVIDIA Samsung",
    "CoWoS advanced packaging TSMC",
    "ASML EUV semiconductor equipment",
    "Microsoft Google AI data center server",
    "AI accelerator supply chain",
]

NEWSAPI_QUERIES = [
    'TSMC OR MediaTek OR Foxconn semiconductor "supply chain"',
    'NVIDIA OR AMD "supply chain" Taiwan chip',
    '"AI server" OR "AI accelerator" Taiwan ODM',
    '"HBM memory" OR CoWoS OR "advanced packaging"',
    'Apple OR Microsoft OR Google "Taiwan supplier"',
]

YAHOO_TICKERS = [
    "TSM", "2330.TW", "2454.TW", "2317.TW", "2382.TW",
    "2308.TW", "3711.TW", "4938.TW", "2357.TW", "2379.TW",
    "3034.TW", "3037.TW", "2356.TW", "3231.TW",
    "NVDA", "AMD", "AAPL", "QCOM", "INTC", "MSFT", "MU", "ASML",
]

# ── Sentiment / tag keywords ──────────────────────────────────────────────────

POSITIVE_WORDS = [
    "創高", "暴增", "成長", "上修", "深化", "擴建", "強勁", "突破", "大幅", "搶單",
    "滿載", "看漲", "surges", "record", "growth", "beats", "soars", "rises",
]
NEGATIVE_WORDS = [
    "下修", "疲軟", "遜預期", "承壓", "下滑", "衰退", "虧損", "下跌", "砍單", "庫存過高",
    "misses", "falls", "drops", "cuts", "warning", "weak", "decline",
]
TAG_KEYWORDS = [
    "AI", "NVIDIA", "AMD", "CoWoS", "先進封裝", "SoIC", "伺服器", "晶片", "半導體",
    "面板", "儲能", "雲端", "HBM", "GB200", "B200", "H100", "H200", "Blackwell",
    "5G", "EV", "電動車", "Microsoft", "Google", "Apple", "Meta", "Amazon",
    "供應鏈", "法說會", "ODM", "EUV", "ASML", "3nm", "2nm",
]


# ── Helper functions ──────────────────────────────────────────────────────────

def _detect_sentiment(text):
    t = text.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w.lower() in t)
    neg = sum(1 for w in NEGATIVE_WORDS if w.lower() in t)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _extract_company(text):
    for name, (ticker, category) in COMPANY_MAP.items():
        if name in text:
            return name, ticker, category
    return None, None, None


def _extract_tags(text):
    return [kw for kw in TAG_KEYWORDS if kw in text]


def _parse_date(date_str):
    if not date_str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for parser in (
        lambda s: parsedate_to_datetime(s),
        lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")),
    ):
        try:
            return parser(date_str).strftime("%Y-%m-%d")
        except Exception:
            continue
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _article_id(url):
    return int(hashlib.md5(url.encode()).hexdigest()[:8], 16)


def _strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _normalize(raw_articles):
    seen, result = set(), []
    for a in raw_articles:
        title = _strip_html(a.get("title", "")).strip()
        if not title or title in seen or title == "[Removed]":
            continue
        seen.add(title)
        full_text = title + " " + _strip_html(a.get("summary", ""))
        company, ticker, category = _extract_company(full_text)
        result.append({
            "id":        _article_id(a.get("url") or title),
            "title":     title,
            "company":   company or "台灣科技業",
            "ticker":    ticker or "-",
            "date":      _parse_date(a.get("date", "")),
            "category":  category or "科技",
            "summary":   _strip_html(a.get("summary", ""))[:300],
            "sentiment": _detect_sentiment(full_text),
            "tags":      _extract_tags(full_text),
            "source":    a.get("source", "unknown"),
            "url":       a.get("url", ""),
        })
    return result


# ── Fetch functions ───────────────────────────────────────────────────────────

def fetch_google_news():
    articles = []

    for q in GOOGLE_TW_QUERIES:
        try:
            url = (
                "https://news.google.com/rss/search"
                f"?q={requests.utils.quote(q)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            )
            for entry in feedparser.parse(url).entries[:5]:
                articles.append({
                    "title":   entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "date":    entry.get("published", ""),
                    "url":     entry.get("link", ""),
                    "source":  "google_news",
                })
        except Exception:
            continue

    for q in GOOGLE_US_QUERIES:
        try:
            url = (
                "https://news.google.com/rss/search"
                f"?q={requests.utils.quote(q)}&hl=en&gl=US&ceid=US:en"
            )
            for entry in feedparser.parse(url).entries[:5]:
                articles.append({
                    "title":   entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "date":    entry.get("published", ""),
                    "url":     entry.get("link", ""),
                    "source":  "google_news",
                })
        except Exception:
            continue

    return articles


def fetch_yahoo_finance():
    articles = []
    for ticker in YAHOO_TICKERS:
        try:
            url = (
                f"https://feeds.finance.yahoo.com/rss/2.0/headline"
                f"?s={ticker}&region=US&lang=en-US"
            )
            for entry in feedparser.parse(url).entries[:3]:
                articles.append({
                    "title":   entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "date":    entry.get("published", ""),
                    "url":     entry.get("link", ""),
                    "source":  "yahoo_finance",
                })
        except Exception:
            continue
    return articles


def fetch_newsapi(from_date=None, to_date=None):
    if not NEWSAPI_KEY:
        return []
    results = []
    for query in NEWSAPI_QUERIES:
        params = {
            "q":        query,
            "sortBy":   "publishedAt",
            "pageSize": 100,
            "apiKey":   NEWSAPI_KEY,
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        try:
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params=params,
                timeout=15,
            )
            if resp.status_code != 200:
                continue
            for a in resp.json().get("articles", []):
                if a.get("title") and a["title"] != "[Removed]":
                    results.append({
                        "title":   a["title"],
                        "summary": a.get("description", "") or "",
                        "date":    a.get("publishedAt", ""),
                        "url":     a.get("url", ""),
                        "source":  "newsapi",
                    })
        except Exception:
            continue
    return results


def fetch_newsapi_historical(months=6):
    """Fetch news month by month going back `months` months.
    Free NewsAPI plan allows ~1 month; paid allows up to 1 year."""
    if not NEWSAPI_KEY:
        return []
    all_results = []
    now = datetime.now()
    for m in range(months):
        from_date = (now - timedelta(days=30 * (m + 1))).strftime("%Y-%m-%d")
        to_date   = (now - timedelta(days=30 * m)).strftime("%Y-%m-%d")
        batch = fetch_newsapi(from_date=from_date, to_date=to_date)
        if not batch and m > 0:
            # API returned nothing — likely hit plan limit, stop early
            print(f"[Fetcher] NewsAPI historical stopped at {from_date} (plan limit or no results)")
            break
        all_results.extend(batch)
        print(f"[Fetcher] NewsAPI {from_date} → {to_date}: {len(batch)} articles")
        time.sleep(0.5)
    return all_results


# ── Main entry points ─────────────────────────────────────────────────────────

def update_news_data():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] Fetching news from all sources...")

    raw = fetch_google_news() + fetch_yahoo_finance() + fetch_newsapi()
    articles = _normalize(raw)
    articles.sort(key=lambda x: x["date"], reverse=True)

    save_articles(articles)
    print(f"[{now}] Saved {len(articles)} articles.")

    try:
        from services.extractor import extract_and_update
        extract_and_update(articles)
    except Exception as e:
        print(f"[Extractor] Failed: {e}")


def run_historical_backfill(months=6):
    """Pull up to `months` months of news and run the extractor on all unprocessed articles."""
    print(f"[Fetcher] Starting {months}-month historical backfill...")

    raw = fetch_newsapi_historical(months) + fetch_google_news() + fetch_yahoo_finance()
    articles = _normalize(raw)
    articles.sort(key=lambda x: x["date"], reverse=True)

    save_articles(articles)
    print(f"[Fetcher] Backfill saved {len(articles)} unique articles.")

    # Run extractor on every unprocessed article in the DB (not just current batch)
    try:
        from services.extractor import extract_and_update
        from services.supply_chain import get_unprocessed_articles
        unprocessed = get_unprocessed_articles()
        print(f"[Fetcher] Running extractor on {len(unprocessed)} unprocessed articles...")
        extract_and_update(unprocessed)
    except Exception as e:
        print(f"[Extractor] Backfill extraction failed: {e}")

    return len(articles)
