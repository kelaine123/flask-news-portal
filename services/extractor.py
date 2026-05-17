"""
LLM-based supply chain relationship extractor using Google Gemini 1.5 Flash.
Runs after each news fetch cycle; only sends articles not yet processed.
"""

import os
import json
import google.generativeai as genai
from services.supply_chain import (
    get_all_companies,
    add_relationship_if_new,
    get_processed_ids,
    mark_processed,
)

_model = None

_PROMPT = """\
你是台灣科技產業供應鏈分析師。請分析以下新聞，找出其中明確提及的公司間供應關係。

已知公司清單（回傳時優先使用這些名稱）：
{companies}

新聞：
{articles}

回傳純 JSON，格式如下：
{{
  "relationships": [
    {{
      "supplier": "供應商名稱",
      "customer": "客戶名稱",
      "product": "供應的產品或服務（25 字以內）"
    }}
  ]
}}

規則：
1. 只抽取新聞中明確陳述的供應關係，不做推斷
2. supplier 或 customer 至少一方必須出現在已知公司清單
3. 沒有供應關係時回傳 {{"relationships": []}}
"""


def _get_model():
    global _model
    if _model is None:
        key = os.getenv("GEMINI_API_KEY", "")
        if not key:
            print("[Extractor] GEMINI_API_KEY not set, skipping extraction.")
            return None
        genai.configure(api_key=key)
        _model = genai.GenerativeModel(
            "gemini-flash-lite-latest",
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0,
            ),
        )
    return _model


def _extract_batch(articles, company_names):
    model = _get_model()
    if not model:
        return [], False

    articles_text = "\n\n".join(
        f"[{i + 1}] 標題: {a.get('title', '')}\n"
        f"摘要: {(a.get('summary') or '')[:300]}"
        for i, a in enumerate(articles)
    )

    prompt = _PROMPT.format(
        companies="、".join(company_names),
        articles=articles_text,
    )

    try:
        response = model.generate_content(prompt)
        data = json.loads(response.text)
        return data.get("relationships", []), True
    except Exception as e:
        print(f"[Extractor] Gemini error: {e}")
        return [], False


def extract_and_update(articles):
    """
    Filter out already-processed articles, send new ones to Gemini in batches of 5,
    and persist discovered relationships to the supply chain DB.
    """
    company_names = [c["name"] for c in get_all_companies()]
    processed = get_processed_ids()

    new_articles = [a for a in articles if str(a.get("id", "")) not in processed]
    if not new_articles:
        print("[Extractor] No new articles to process.")
        return 0

    print(f"[Extractor] Analysing {len(new_articles)} new articles with Gemini...")
    added = 0
    batch_size = 5

    for i in range(0, len(new_articles), batch_size):
        batch = new_articles[i : i + batch_size]
        rels, success = _extract_batch(batch, company_names)

        for r in rels:
            supplier = (r.get("supplier") or "").strip()
            customer = (r.get("customer") or "").strip()
            product  = (r.get("product")  or "").strip()[:100]
            if supplier and customer and product:
                if add_relationship_if_new(supplier, customer, product):
                    added += 1
                    print(f"[Extractor] + {supplier} → {customer} ({product})")

        # Only mark processed on success; on API error, retry next cycle
        if success:
            mark_processed([str(a["id"]) for a in batch])

    print(f"[Extractor] Done. {added} new relationship(s) added.")
    return added
