"""使用 Gemini（Free Tier）將英文逐字稿轉換為繁體中文文章。"""

import json
from google import genai
from google.genai import types

import config

client = genai.Client(api_key=config.GEMINI_API_KEY)


PROMPT_TEMPLATE = """你是一位資深的內容編輯與作家，專門將英文 YouTube 影片逐字稿改寫為高品質、好閱讀的繁體中文文章。你的目標是產出一篇讀者會想從頭讀到尾的文章，而不是翻譯稿。

## 影片資訊
- 標題：{title}
- 頻道：{channel}

## 英文逐字稿
{transcript}

## 任務
將逐字稿改寫為一篇結構清晰、閱讀體驗良好的繁體中文文章。

## 寫作原則

### 內容完整性（最重要，違反此規則等同失敗）
- 這篇文章的目的是讓讀者「不需要看影片也能獲得完整資訊」
- 影片中的每個觀點、論述、範例、數據、故事、比喻都必須保留
- 每個論點都要展開說明——如果講者花了 2 分鐘解釋一個概念，你至少要寫 2-3 個完整段落
- ⚠️ 你最常犯的錯誤是「過度壓縮」：把 10 分鐘的內容壓成 3 個 bullet points。不要這樣做。
- 如果講者舉了一個具體例子，你必須完整描述那個例子，不能只說「例如...」然後跳過
- 贊助商廣告段落可以省略
- 最終文章的中文字數應該至少是英文逐字稿字數的 30%。如果逐字稿有 20000 字元，文章正文至少要 6000 字元

### 文章結構（這是關鍵）
- 用清楚的 ## 小標題將文章分成邏輯段落，每個小標題要具體、有資訊量（不要用「前言」「總結」這種空洞標題）
- 每段控制在 3-5 句話，避免一整段超過 8 行
- 善用 **粗體** 標記關鍵概念或重要結論
- 條列重點時用 - 列表，讓資訊一目了然
- 在觀點轉換處自然過渡，不要生硬跳轉

### 語言風格
- 寫作口吻像是一位懂行的朋友在跟你解釋，自然但專業
- 避免翻譯腔（「那麼」「然而」「事實上」「值得注意的是」不要過度使用）
- 避免 AI 寫作腔（不要用「讓我們深入探討」「總而言之」「這不僅僅是...更是...」）
- 句子簡潔有力，一句話傳達一個意思
- 專有名詞保留英文（人名、產品名、技術名詞）

### 可讀性優化
- 開頭直接切入重點，用一兩句話勾住讀者（為什麼這個主題重要？）
- 抽象概念搭配具體例子說明
- 如果原影片有比喻或幽默，保留其精神但用中文讀者能理解的方式表達

**請以以下 JSON 格式回覆（不要加 ```json 標記）：**
{{
  "title": "吸引人的繁體中文標題（具體、有資訊量，不要太長）",
  "summary": "2-3 句話的文章摘要，讓讀者快速判斷是否要讀全文",
  "body": "Markdown 格式的完整文章正文",
  "tags": ["標籤1", "標籤2", "標籤3"]
}}"""


def _parse_response(text: str) -> dict | None:
    """嘗試多種方式從 Gemini 回應中解析出文章 JSON。"""
    import re

    # 清除 markdown code block 包裹
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    # 嘗試 1: 直接 JSON parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 嘗試 2: 找到第一個 { 和最後一個 } 之間的內容
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(cleaned[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    # 嘗試 3: 用 regex 提取各欄位
    title_m = re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
    summary_m = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
    body_m = re.search(r'"body"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
    tags_m = re.search(r'"tags"\s*:\s*\[(.*?)\]', cleaned, re.DOTALL)

    if body_m:
        tags = []
        if tags_m:
            tags = re.findall(r'"([^"]*)"', tags_m.group(1))
        return {
            "title": title_m.group(1) if title_m else "",
            "summary": summary_m.group(1) if summary_m else "",
            "body": body_m.group(1).replace("\\n", "\n").replace('\\"', '"'),
            "tags": tags,
        }

    return None


def generate_article(
    transcript: str,
    video_title: str,
    channel_name: str,
) -> dict | None:
    """用 Gemini 將逐字稿轉為繁體中文文章。

    回傳 dict: {title, summary, body, tags} 或 None。
    """
    prompt = PROMPT_TEMPLATE.format(
        title=video_title,
        channel=channel_name,
        transcript=transcript,
    )

    response_text = ""
    try:
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.5,
                max_output_tokens=16384,
            ),
        )

        response_text = response.text.strip()
        article = _parse_response(response_text)
        if article:
            return article

        # 所有解析都失敗，將整段回應當作純文字正文
        return {
            "title": f"[整理] {video_title}",
            "summary": "",
            "body": response_text,
            "tags": [],
        }
    except Exception as e:
        print(f"  ✗ Gemini 生成失敗: {e}")
        return None
