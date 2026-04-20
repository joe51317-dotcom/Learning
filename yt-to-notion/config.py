import os
from pathlib import Path
from dotenv import load_dotenv

# 載入 .env
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# Gemini（Free Tier）
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"  # 免費額度：15 RPM / 1500 RPD

# Notion
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_CHANNELS_DB = os.getenv("NOTION_CHANNELS_DB", "")
NOTION_ARTICLES_DB = os.getenv("NOTION_ARTICLES_DB", "")

# 已處理影片紀錄
PROCESSED_FILE = BASE_DIR / "data" / "processed_videos.json"
