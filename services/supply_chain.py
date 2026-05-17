import sqlite3
import os
from contextlib import contextmanager

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "supply_chain.db")

# fmt: off
_COMPANIES = [
    # (name, ticker, category, country)
    ("台積電",   "2330",   "半導體",    "TW"),
    ("聯發科",   "2454",   "IC設計",    "TW"),
    ("鴻海",     "2317",   "電子製造",  "TW"),
    ("廣達",     "2382",   "伺服器",    "TW"),
    ("台達電",   "2308",   "電力電子",  "TW"),
    ("友達",     "2409",   "面板",      "TW"),
    ("群創",     "3481",   "面板",      "TW"),
    ("聯電",     "2303",   "半導體",    "TW"),
    ("日月光",   "3711",   "封裝測試",  "TW"),
    ("華碩",     "2357",   "消費電子",  "TW"),
    ("宏碁",     "2353",   "消費電子",  "TW"),
    ("緯創",     "3231",   "電子製造",  "TW"),
    ("英業達",   "2356",   "伺服器",    "TW"),
    ("和碩",     "4938",   "電子製造",  "TW"),
    ("瑞昱",     "2379",   "IC設計",    "TW"),
    ("聯詠",     "3034",   "IC設計",    "TW"),
    ("欣興",     "3037",   "PCB",       "TW"),
    ("景碩",     "3189",   "PCB",       "TW"),
    ("台光電",   "2383",   "CCL",       "TW"),
    ("NVIDIA",   "NVDA",   "IC設計",    "US"),
    ("AMD",      "AMD",    "IC設計",    "US"),
    ("Apple",    "AAPL",   "消費電子",  "US"),
    ("Qualcomm", "QCOM",   "IC設計",    "US"),
    ("Intel",    "INTC",   "半導體",    "US"),
    ("Microsoft","MSFT",   "雲端",      "US"),
    ("Google",   "GOOGL",  "雲端",      "US"),
    ("Meta",     "META",   "雲端",      "US"),
    ("Amazon",   "AMZN",   "雲端",      "US"),
    ("ASML",     "ASML",   "半導體設備","NL"),
    ("Samsung",  "005930", "半導體",    "KR"),
    ("SK Hynix", "000660", "記憶體",    "KR"),
    ("Micron",   "MU",     "記憶體",    "US"),
    ("Dell",     "DELL",   "伺服器",    "US"),
    ("HP",       "HPQ",    "伺服器",    "US"),
]

_RELATIONSHIPS = [
    # (supplier, customer, product)
    # TSMC 上游設備
    ("ASML",    "台積電",  "EUV 極紫外光刻機"),
    # TSMC 下游客戶
    ("台積電",  "NVIDIA",  "AI GPU 晶片代工"),
    ("台積電",  "AMD",     "CPU/GPU 晶片代工"),
    ("台積電",  "Apple",   "A/M 系列晶片代工"),
    ("台積電",  "Qualcomm","手機處理器代工"),
    ("台積電",  "Intel",   "先進製程代工"),
    ("台積電",  "聯發科",  "天璣系列晶片代工"),
    # 封裝測試
    ("日月光",  "NVIDIA",  "CoWoS 先進封裝"),
    ("日月光",  "AMD",     "晶片封裝測試"),
    ("日月光",  "台積電",  "委外封裝測試"),
    # 記憶體 → NVIDIA HBM
    ("SK Hynix","NVIDIA",  "HBM3E 記憶體"),
    ("Micron",  "NVIDIA",  "HBM3 記憶體"),
    ("Samsung", "NVIDIA",  "HBM3 記憶體"),
    # 聯發科
    ("聯發科",  "Samsung", "天璣手機處理器"),
    ("聯詠",    "友達",    "面板驅動 IC"),
    ("聯詠",    "群創",    "面板驅動 IC"),
    # 組裝廠
    ("鴻海",    "Apple",   "iPhone / iPad 組裝"),
    ("鴻海",    "NVIDIA",  "GB200 AI 伺服器組裝"),
    ("和碩",    "Apple",   "iPhone 組裝"),
    ("緯創",    "Apple",   "MacBook 組裝"),
    # 伺服器 ODM
    ("廣達",    "Google",  "AI 伺服器 ODM"),
    ("廣達",    "Microsoft","AI 伺服器 ODM"),
    ("廣達",    "Meta",    "資料中心伺服器"),
    ("廣達",    "Amazon",  "雲端伺服器"),
    ("英業達",  "Microsoft","企業伺服器"),
    ("英業達",  "Amazon",  "雲端伺服器"),
    ("英業達",  "Dell",    "白牌伺服器"),
    # 電源
    ("台達電",  "廣達",    "伺服器電源供應器"),
    ("台達電",  "鴻海",    "電源模組"),
    ("台達電",  "英業達",  "電源供應器"),
    # 網通 IC
    ("瑞昱",    "華碩",    "網路 / 音效晶片"),
    # PCB / CCL
    ("欣興",    "廣達",    "高階 PCB"),
    ("欣興",    "英業達",  "高階 PCB"),
    ("台光電",  "欣興",    "CCL 覆銅板"),
    ("景碩",    "鴻海",    "IC 載板"),
    # 面板
    ("友達",    "Apple",   "筆電面板供應"),
    ("群創",    "Samsung", "TV 面板供應"),
    # 聯電
    ("ASML",    "聯電",    "光刻機"),
    ("聯電",    "瑞昱",    "成熟製程晶片代工"),
]
# fmt: on


@contextmanager
def _db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS companies (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                name    TEXT NOT NULL UNIQUE,
                ticker  TEXT,
                category TEXT,
                country TEXT DEFAULT 'TW'
            );
            CREATE TABLE IF NOT EXISTS relationships (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL REFERENCES companies(id),
                customer_id INTEGER NOT NULL REFERENCES companies(id),
                product     TEXT,
                updated_at  TEXT DEFAULT (date('now')),
                UNIQUE(supplier_id, customer_id, product)
            );
        """)
        if conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 0:
            _seed(conn)


def _seed(conn):
    for name, ticker, category, country in _COMPANIES:
        conn.execute(
            "INSERT OR IGNORE INTO companies (name, ticker, category, country) VALUES (?,?,?,?)",
            (name, ticker, category, country),
        )

    def cid(name):
        row = conn.execute("SELECT id FROM companies WHERE name=?", (name,)).fetchone()
        return row[0] if row else None

    for supplier, customer, product in _RELATIONSHIPS:
        sid, cid_ = cid(supplier), cid(customer)
        if sid and cid_:
            conn.execute(
                "INSERT OR IGNORE INTO relationships (supplier_id, customer_id, product) VALUES (?,?,?)",
                (sid, cid_, product),
            )


def get_all_companies():
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM companies ORDER BY country='TW' DESC, category, name"
        ).fetchall()
        return [dict(r) for r in rows]


def get_company(company_id):
    with _db() as conn:
        row = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
        if not row:
            return None
        company = dict(row)

        upstream = conn.execute(
            """SELECT c.id, c.name, c.ticker, c.category, c.country, r.product
               FROM relationships r JOIN companies c ON c.id = r.supplier_id
               WHERE r.customer_id = ?""",
            (company_id,),
        ).fetchall()

        downstream = conn.execute(
            """SELECT c.id, c.name, c.ticker, c.category, c.country, r.product
               FROM relationships r JOIN companies c ON c.id = r.customer_id
               WHERE r.supplier_id = ?""",
            (company_id,),
        ).fetchall()

        company["upstream"] = [dict(r) for r in upstream]
        company["downstream"] = [dict(r) for r in downstream]
        return company


def get_graph_data():
    with _db() as conn:
        companies = conn.execute("SELECT * FROM companies").fetchall()
        rels = conn.execute(
            "SELECT supplier_id, customer_id, product FROM relationships"
        ).fetchall()

        return {
            "nodes": [
                {
                    "id": c["id"],
                    "label": c["name"],
                    "category": c["category"],
                    "ticker": c["ticker"],
                    "country": c["country"],
                }
                for c in companies
            ],
            "edges": [
                {"from": r["supplier_id"], "to": r["customer_id"], "label": r["product"]}
                for r in rels
            ],
        }


def get_stats():
    with _db() as conn:
        companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        rels = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
        tw = conn.execute("SELECT COUNT(*) FROM companies WHERE country='TW'").fetchone()[0]
        return {"companies": companies, "relationships": rels, "tw_companies": tw}
