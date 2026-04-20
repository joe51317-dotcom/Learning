"""將生成的文章寫入 Notion Database。"""

import re
from notion_client import Client as NotionClient

import config

BLOCK_CHAR_LIMIT = 2000  # Notion 單一 block 的字元上限


def _parse_rich_text(text: str) -> list[dict]:
    """將含有 **粗體** 的文字解析成 Notion rich_text 陣列。"""
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    rich_text = []
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            rich_text.append({
                "type": "text",
                "text": {"content": part[2:-2]},
                "annotations": {"bold": True},
            })
        else:
            rich_text.append({
                "type": "text",
                "text": {"content": part},
            })
    return rich_text


def _split_text(text: str, limit: int = BLOCK_CHAR_LIMIT) -> list[str]:
    """將長文字切分為不超過 limit 的段落。"""
    if len(text) <= limit:
        return [text]

    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # 在 limit 範圍內找最後一個換行符切分
        cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")

    return chunks


def _markdown_to_blocks(markdown: str) -> list[dict]:
    """將 Markdown 文字轉為 Notion block 列表。"""
    blocks = []
    lines = markdown.split("\n")
    paragraph_buffer = []

    def flush_paragraph():
        if paragraph_buffer:
            text = "\n".join(paragraph_buffer)
            for chunk in _split_text(text):
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": _parse_rich_text(chunk)
                    },
                })
            paragraph_buffer.clear()

    for line in lines:
        stripped = line.strip()

        # 空行 → flush paragraph
        if not stripped:
            flush_paragraph()
            continue

        # ## 標題
        h2_match = re.match(r"^##\s+(.+)$", stripped)
        if h2_match:
            flush_paragraph()
            title = h2_match.group(1)[:BLOCK_CHAR_LIMIT]
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": _parse_rich_text(title)
                },
            })
            continue

        # ### 標題
        h3_match = re.match(r"^###\s+(.+)$", stripped)
        if h3_match:
            flush_paragraph()
            title = h3_match.group(1)[:BLOCK_CHAR_LIMIT]
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": _parse_rich_text(title)
                },
            })
            continue

        # - 或 * 列表項目
        list_match = re.match(r"^[-*]\s+(.+)$", stripped)
        if list_match:
            flush_paragraph()
            item = list_match.group(1)[:BLOCK_CHAR_LIMIT]
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": _parse_rich_text(item)
                },
            })
            continue

        # 數字列表
        num_match = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if num_match:
            flush_paragraph()
            item = num_match.group(1)[:BLOCK_CHAR_LIMIT]
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {
                    "rich_text": _parse_rich_text(item)
                },
            })
            continue

        # 一般文字 → 累積到 paragraph buffer
        paragraph_buffer.append(stripped)

    flush_paragraph()
    return blocks


def write_to_notion(
    article: dict,
    video_url: str,
    channel_name: str,
    published: str,
    tags: list[str],
) -> str | None:
    """寫入文章到 Notion，回傳 page ID。"""
    notion = NotionClient(auth=config.NOTION_API_KEY)

    # 合併文章自帶的 tags 和頻道 tags
    all_tags = list(set(tags + article.get("tags", [])))

    # Database properties
    properties = {
        "Title": {
            "title": [{"text": {"content": article["title"]}}]
        },
        "Channel": {
            "select": {"name": channel_name}
        },
        "URL": {
            "url": video_url
        },
        "Tags": {
            "multi_select": [{"name": t} for t in all_tags]
        },
    }

    # Published date（如果有的話）
    if published:
        # 截取日期部分 2024-01-15T00:00:00+00:00 → 2024-01-15
        date_str = published[:10] if len(published) >= 10 else published
        properties["Published"] = {"date": {"start": date_str}}

    # Summary
    if article.get("summary"):
        properties["Summary"] = {
            "rich_text": [{"text": {"content": article["summary"][:2000]}}]
        }

    # 將文章正文轉為 Notion blocks
    body_blocks = _markdown_to_blocks(article.get("body", ""))

    # Notion API 一次最多 100 個 children blocks
    children = body_blocks[:100]

    try:
        page = notion.pages.create(
            parent={"database_id": config.NOTION_ARTICLES_DB},
            properties=properties,
            children=children,
        )

        page_id = page["id"]

        # 如果還有超過 100 的 blocks，分批 append
        remaining = body_blocks[100:]
        while remaining:
            batch = remaining[:100]
            remaining = remaining[100:]
            notion.blocks.children.append(block_id=page_id, children=batch)

        return page_id

    except Exception as e:
        print(f"  ✗ Notion 寫入失敗: {e}")
        return None
