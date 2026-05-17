import re
import json
import os
import hashlib
import requests
import feedparser
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "news.json")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")

COMPANY_MAP = {
    "台積電": ("2330", "半導體"), "TSMC": ("2330", "半導體"),
    "聯發科": ("2454", "IC設計"), "MediaTek": ("2454", "IC設計"),
    "鴻海": ("2317", "電子製造"), "Foxconn": ("2317", "電子製造"),
    "廣達": ("2382", "伺服器"), "Quanta": ("2382", "伺服器"),
    "台達電": ("2308", "電力電子"), "Delta Electronics": ("2308", "電力電子"),
    "友達": ("2409", "面板"), "AUO": ("2409", "面板"),
    "群創": ("3481", "面板"), "Innolux": ("3481", "面板"),
    "聯電": ("2303", "半導體"), "UMC": ("2303", "半導體"),
    "日月光": ("3711", "封裝測試"), "ASE": ("3711", "封裝測試"),
    "華碩": ("2357", "消費電子"), "ASUS": ("2357", "消費電子"),
    "宏碁": ("2353", "消費電子"), "Acer": ("2353", "消費電子"),
    "緯創": ("3231", "電子製造"), "Wistron": ("3231", "電子製造"),
    "英業達": ("2356", "伺服器"), "Inventec": ("2356", "伺服器"),
}

POSITIVE_WORDS = [
    "創高", "暴增", "成長", "上修", "深化", "擴建", "強勁", "突破", "大幅", "搶單",
    "滿載", "看漲", "surges", "record", "growth", "beats", "soars", "rises",
]
NEGATIVE_WORDS = [
    "下修", "疲軟", "遜預期", "承壓", "下滑", "衰退", "虧損", "下跌", "砍單", "庫存過高",
    "misses", "falls", "drops", "cuts", "warning", "weak", "decline",
]
TAG_KEYWORDS = [
    "AI", "NVIDIA", "AMD", "CoWoS", "先進封裝", "伺服器", "晶片", "半導體",
    "面板", "儲能", "雲端", "HBM", "GB200", "B200", "H100", "AI手機",
    "5G", "EV", "電動車", "Microsoft", "Google", "Apple", "Meta",
]


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
            "id": _article_id(a.get("url") or title),
            "title": title,
            "company": company or "台灣科技業",
            "ticker": ticker or "-",
            "date": _parse_date(a.get("date", "")),
            "category": category or "科技",
            "summary": _strip_html(a.get("summary", ""))[:250],
            "sentiment": _detect_sentiment(full_text),
            "tags": _extract_tags(full_text),
            "source": a.get("source", "unknown"),
            "url": a.get("url", ""),
        })
    return result


def fetch_google_news():
    queries = [
        "台積電 半導體", "聯發科 晶片", "鴻海 AI伺服器",
        "台灣科技股", "TSMC semiconductor", "Taiwan AI chip",
    ]
    articles = []
    for q in queries:
        try:
            url = (
                "https://news.google.com/rss/search"
                f"?q={requests.utils.quote(q)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            )
            for entry in feedparser.parse(url).entries[:3]:
                articles.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "date": entry.get("published", ""),
                    "url": entry.get("link", ""),
                    "source": "google_news",
                })
        except Exception:
            continue
    return articles


def fetch_yahoo_finance():
    tickers = ["TSM", "2330.TW", "2454.TW", "2317.TW", "2382.TW", "2308.TW"]
    articles = []
    for ticker in tickers:
        try:
            url = (
                f"https://feeds.finance.yahoo.com/rss/2.0/headline"
                f"?s={ticker}&region=US&lang=en-US"
            )
            for entry in feedparser.parse(url).entries[:2]:
                articles.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "date": entry.get("published", ""),
                    "url": entry.get("link", ""),
                    "source": "yahoo_finance",
                })
        except Exception:
            continue
    return articles


def fetch_newsapi():
    if not NEWSAPI_KEY:
        return []
    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": 'TSMC OR "Taiwan semiconductor" OR MediaTek OR Foxconn OR "Taiwan tech"',
                "sortBy": "publishedAt",
                "pageSize": 20,
                "apiKey": NEWSAPI_KEY,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        return [
            {
                "title": a["title"],
                "summary": a.get("description", "") or "",
                "date": a.get("publishedAt", ""),
                "url": a.get("url", ""),
                "source": "newsapi",
            }
            for a in resp.json().get("articles", [])
            if a.get("title") and a["title"] != "[Removed]"
        ]
    except Exception:
        return []


def update_news_data():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] Fetching news from all sources...")

    raw = fetch_google_news() + fetch_yahoo_finance() + fetch_newsapi()
    articles = _normalize(raw)
    articles.sort(key=lambda x: x["date"], reverse=True)
    articles = articles[:60]

    payload = {
        "articles": articles,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)

    print(f"[{now}] Saved {len(articles)} articles.")
