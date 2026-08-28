"""從 Notion 讀取追蹤頻道，透過 YouTube RSS 偵測新影片。"""

import json
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from urllib.request import urlopen, Request

from notion_client import Client as NotionClient

import config

YOUTUBE_RSS = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


@dataclass
class VideoInfo:
    video_id: str
    title: str
    channel_name: str
    channel_id: str
    published: str  # ISO format
    url: str
    tags: list[str]


def load_processed() -> dict:
    """讀取已處理影片紀錄。"""
    if config.PROCESSED_FILE.exists():
        with open(config.PROCESSED_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_processed(data: dict):
    """儲存已處理影片紀錄。"""
    with open(config.PROCESSED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_channels_from_notion() -> list[dict]:
    """從 Notion「追蹤頻道」DB 讀取 Active 的頻道。"""
    notion = NotionClient(auth=config.NOTION_API_KEY)

    results = notion.databases.query(
        database_id=config.NOTION_CHANNELS_DB,
        filter={"property": "Active", "checkbox": {"equals": True}},
    )

    channels = []
    for page in results["results"]:
        props = page["properties"]

        # Title（頻道名稱）
        name_parts = props.get("Name", {}).get("title", [])
        name = name_parts[0]["plain_text"] if name_parts else "Unknown"

        # Channel ID
        cid_parts = props.get("Channel ID", {}).get("rich_text", [])
        channel_id = cid_parts[0]["plain_text"].strip() if cid_parts else ""

        # Tags
        tag_options = props.get("Tags", {}).get("multi_select", [])
        tags = [t["name"] for t in tag_options]

        if channel_id:
            channels.append({
                "id": channel_id,
                "name": name,
                "tags": tags,
            })

    return channels


def fetch_rss_videos(channel_id: str, attempts: int = 10) -> list[dict]:
    """從 YouTube RSS 取得頻道最新影片（最多 15 支）。

    2026-08-28：這個端點會對「完全正確」的 channel_id 隨機回 404 或 500——
    同一個網址連打六次可以拿到 200/404/500 混合的結果，成功率隨時間在
    兩成到五成之間浮動。404 特別會騙人（看起來像頻道被刪了），但幾秒後
    同一支就回 200，而且頻道頁 /channel/<id> 從頭到尾都是 200。
    換 User-Agent 沒有用，不是我們被擋，是端點自己不穩。

    所以這裡一定要重試，而且 sleep 要拉長：好壞是一個時間窗一個時間窗來的，
    連著快打只是在同一個壞窗裡多撞幾次。單次失敗不代表頻道不見了。
    """
    url = YOUTUBE_RSS.format(channel_id)
    xml_data = None
    last_err = None

    for i in range(attempts):
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urlopen(req, timeout=15) as resp:
                xml_data = resp.read()
            break
        except Exception as e:
            last_err = e
            if i < attempts - 1:
                time.sleep(min(5 * (i + 1), 25))

    if xml_data is None:
        print(f"  ✗ RSS 取得失敗（重試 {attempts} 次都不成，"
              f"多半是 YouTube 端點當下整段不穩、不是頻道消失）: {last_err}")
        return []

    root = ET.fromstring(xml_data)
    videos = []

    for entry in root.findall("atom:entry", NS):
        vid = entry.find("yt:videoId", NS)
        title = entry.find("atom:title", NS)
        published = entry.find("atom:published", NS)

        if vid is not None and title is not None:
            videos.append({
                "video_id": vid.text,
                "title": title.text,
                "published": published.text if published is not None else "",
            })

    return videos


def check_new_videos(channel: dict, processed: dict) -> list[VideoInfo]:
    """比對 RSS 與已處理紀錄，回傳新影片列表。"""
    rss_videos = fetch_rss_videos(channel["id"])
    new_videos = []

    for v in rss_videos:
        if v["video_id"] not in processed:
            new_videos.append(VideoInfo(
                video_id=v["video_id"],
                title=v["title"],
                channel_name=channel["name"],
                channel_id=channel["id"],
                published=v["published"],
                url=f"https://www.youtube.com/watch?v={v['video_id']}",
                tags=channel.get("tags", []),
            ))

    return new_videos
