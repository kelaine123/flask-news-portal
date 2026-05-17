import atexit
import os
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify, abort
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from services.fetcher import update_news_data, run_historical_backfill
from services.supply_chain import (
    init_db, get_all_companies, get_company, get_graph_data, get_stats,
    get_articles, get_article_by_id,
)
from services.company_seeder import run_seeder

load_dotenv()

app = Flask(__name__)

init_db()

# Scheduler at module level — works with both `python app.py` and `flask run`
_scheduler = BackgroundScheduler()
_scheduler.add_job(update_news_data, "interval", hours=6, id="news_update")
_scheduler.start()
atexit.register(lambda: _scheduler.shutdown(wait=False))


# ── News routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/news")
def get_news():
    articles = get_articles(limit=300)
    return jsonify({
        "articles": articles,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/api/news/<int:article_id>")
def get_article(article_id):
    article = get_article_by_id(article_id)
    if article is None:
        abort(404)
    return jsonify(article)


@app.route("/api/refresh", methods=["POST"])
def refresh():
    update_news_data()
    return jsonify({"status": "ok", "updated_at": datetime.now(timezone.utc).isoformat()})


@app.route("/api/news/backfill", methods=["POST"])
def news_backfill():
    count = run_historical_backfill(months=6)
    return jsonify({"status": "ok", "articles_saved": count})


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


@app.route("/api/supply-chain/seed-companies", methods=["POST"])
def seed_companies():
    result = run_seeder()
    return jsonify(result)


if __name__ == "__main__":
    update_news_data()
    app.run(debug=False, port=5000)
