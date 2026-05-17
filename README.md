# 台灣科技股新聞分析平台

一個以 Flask 建構的台灣科技股新聞聚合與分析平台，提供 REST API 與響應式前端介面。

## 功能特色

- 科技股新聞瀏覽（半導體、IC 設計、電子製造等）
- 情緒標註（正面 / 中性 / 負面）
- 個股標籤與分類篩選
- REST API 供前端或第三方呼叫

## 技術棧

| 層次 | 技術 |
|------|------|
| 後端 | Python 3 / Flask |
| 前端 | HTML / CSS / JavaScript |
| 資料 | JSON 靜態資料集 |

## 安裝與執行

```bash
# 建立虛擬環境
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # macOS / Linux

# 安裝依賴
pip install -r requirements.txt

# 啟動伺服器
python app.py
```

開啟瀏覽器前往 `http://localhost:5000`

## API 端點

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/news` | 取得所有新聞文章 |
| GET | `/api/news/<id>` | 取得單篇文章詳情 |

### 回傳範例

```json
{
  "articles": [
    {
      "id": 1,
      "title": "台積電 AI 晶片訂單暴增，CoWoS 封裝產能仍吃緊",
      "company": "台積電",
      "ticker": "2330",
      "date": "2026-05-16",
      "category": "半導體",
      "sentiment": "positive",
      "tags": ["AI", "CoWoS", "先進封裝", "NVIDIA"]
    }
  ]
}
```

## 專案結構

```
flask-news-portal/
├── app.py              # Flask 主程式與路由
├── requirements.txt    # Python 套件依賴
├── data/
│   └── news.json       # 新聞資料集
├── static/
│   ├── css/style.css   # 樣式表
│   └── js/main.js      # 前端互動邏輯
└── templates/
    └── index.html      # 主頁面模板
```
