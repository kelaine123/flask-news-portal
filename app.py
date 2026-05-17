import json
import os
from flask import Flask, render_template, jsonify, abort

app = Flask(__name__)

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "news.json")


def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/news")
def get_news():
    data = load_data()
    return jsonify(data)


@app.route("/api/news/<int:article_id>")
def get_article(article_id):
    data = load_data()
    article = next((a for a in data["articles"] if a["id"] == article_id), None)
    if article is None:
        abort(404)
    return jsonify(article)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
