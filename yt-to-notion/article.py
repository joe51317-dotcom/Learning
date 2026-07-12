"""使用 Gemini（Free Tier）將英文逐字稿轉換為繁體中文文章。"""

import json
from google import genai
from google.genai import types

import config

client = genai.Client(api_key=config.GEMINI_API_KEY)


PROMPT_TEMPLATE = """你是一位資深的內容編輯與作家，專門將英文 YouTube 影片逐字稿改寫為高品質、完整、好閱讀的繁體中文長文。你在做的是「完整重寫」，不是「摘要」。

## 影片資訊
- 標題：{title}
- 頻道：{channel}

## 英文逐字稿（原文共 {transcript_chars} 字元）
{transcript}

## 你的任務
把上面的逐字稿改寫成一篇「讀者不看影片也能完整掌握全部內容」的繁體中文文章。

## 鐵則一：完整，絕不壓縮（最重要，違反此條即為失敗）
- 影片中每一個觀點、論述、步驟、範例、數據、故事、比喻，全部都要保留並展開說明。
- 講者花時間解釋的概念，你也要用足夠的篇幅解釋；他舉的每個具體例子，你都要完整寫出來，**不可以用「例如……」一句帶過就跳過**。
- **嚴禁把大段內容濃縮成幾個 bullet points。** 這是最常見、也最嚴重的錯誤。
- 你的正文長度「至少」要達到 {min_chars} 個中文字元（這是逐字稿的 30%）。如果寫不到這個長度，就代表你一定壓縮了內容、漏了東西——回頭把每個段落展開到夠完整為止。
- 唯一可以省略的是贊助商 / 廣告口播段落。

## 鐵則二：好讀
- 用具體、有資訊量的 ## 小標題分段（不要「前言」「總結」這種空洞標題）。
- 每段控制在 3-5 句話，避免一整段超過 8 行。
- 關鍵概念或重要結論用 **粗體** 標記；並列的重點用 - 列表。
- 開頭直接用一兩句話點出「為什麼這個主題值得讀」勾住讀者。
- 觀點轉換處自然過渡，不要生硬跳轉。

## 鐵則三：語感自然
- 口吻像一位懂行的朋友在跟你解釋，專業但不生硬。
- 避免翻譯腔（「那麼」「然而」「事實上」「值得注意的是」不要過度使用）。
- 避免 AI 寫作腔（不要用「讓我們深入探討」「總而言之」「這不僅僅是……更是……」）。
- 人名、產品名、技術名詞保留英文。
- 若原影片有比喻或幽默，保留其精神，但換成中文讀者能理解的方式表達。

## 送出前，逐項自我檢查（務必執行）
1. 逐字稿裡每一個主要段落，我的文章都有對應、而且展開說明了嗎？
2. 正文有沒有達到 {min_chars} 字元？沒達到的話，是哪個段落被我偷偷壓縮了？回去補完。
3. 有沒有出現「例如……（然後跳過）」這種偷懶？有的話補上完整例子。

確認無誤後，用以下 JSON 格式回覆：
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
    # 給模型一個具體的字數下限，比抽象的「30%」更能約束偏弱的 flash-lite 不要壓縮內容
    min_chars = int(len(transcript) * 0.3)

    prompt = PROMPT_TEMPLATE.format(
        title=video_title,
        channel=channel_name,
        transcript=transcript,
        transcript_chars=len(transcript),
        min_chars=min_chars,
    )

    response_text = ""
    try:
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.5,
                max_output_tokens=24576,
                # 強制 JSON 輸出，讓偏弱模型的回應更好解析
                response_mime_type="application/json",
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
