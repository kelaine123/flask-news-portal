import atexit
import json
import os
from flask import Flask, render_template, jsonify, abort
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from services.fetcher import update_news_data
from services.supply_chain import init_db, get_all_companies, get_company, get_graph_data, get_stats

load_dotenv()

app = Flask(__name__)
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "news.json")

# Init supply chain DB on startup
init_db()

# Scheduler at module level — works with both `python app.py` and `flask run`
_scheduler = BackgroundScheduler()
_scheduler.add_job(update_news_data, "interval", hours=6, id="news_update")
_scheduler.start()
atexit.register(lambda: _scheduler.shutdown(wait=False))


def load_news():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ── News routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/news")
def get_news():
    return jsonify(load_news())


@app.route("/api/news/<int:article_id>")
def get_article(article_id):
    data = load_news()
    article = next((a for a in data["articles"] if a["id"] == article_id), None)
    if article is None:
        abort(404)
    return jsonify(article)


@app.route("/api/refresh", methods=["POST"])
def refresh():
    update_news_data()
    return jsonify({"status": "ok", "updated_at": load_news().get("updated_at")})


# ── Supply chain routes ───────────────────────────────────────────────────────

@app.route("/supply-chain")
def supply_chain_page():
    return render_template("supply_chain.html")


@app.route("/api/supply-chain/graph")
def supply_chain_graph():
    return jsonify(get_graph_data())


@app.route("/api/supply-chain/companies")
def supply_chain_companies():
    return jsonify(get_all_companies())


@app.route("/api/supply-chain/company/<int:company_id>")
def supply_chain_company(company_id):
    company = get_company(company_id)
    if company is None:
        abort(404)
    return jsonify(company)


@app.route("/api/supply-chain/stats")
def supply_chain_stats():
    return jsonify(get_stats())


if __name__ == "__main__":
    update_news_data()
    app.run(debug=False, port=5000)
