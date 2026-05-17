import atexit
import json
import os
from flask import Flask, render_template, jsonify, abort
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from services.fetcher import update_news_data

load_dotenv()

app = Flask(__name__)
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "news.json")

# Start scheduler at module level so it works with both `python app.py` and `flask run`
_scheduler = BackgroundScheduler()
_scheduler.add_job(update_news_data, "interval", hours=6, id="news_update")
_scheduler.start()
atexit.register(lambda: _scheduler.shutdown(wait=False))


def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/news")
def get_news():
    return jsonify(load_data())


@app.route("/api/news/<int:article_id>")
def get_article(article_id):
    data = load_data()
    article = next((a for a in data["articles"] if a["id"] == article_id), None)
    if article is None:
        abort(404)
    return jsonify(article)


@app.route("/api/refresh", methods=["POST"])
def refresh():
    update_news_data()
    return jsonify({"status": "ok", "updated_at": load_data().get("updated_at")})


if __name__ == "__main__":
    update_news_data()
    app.run(debug=False, port=5000)
