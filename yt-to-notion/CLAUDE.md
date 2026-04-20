# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案簡介

YouTube 頻道監控系統：自動追蹤 YouTube 頻道新影片 → 擷取英文逐字稿 → Gemini 翻譯整理為繁體中文完整文章 → 寫入 Notion Database。

## 執行

```bash
python main.py --verbose        # 完整執行
python main.py --dry-run        # 只偵測不寫入
```

## 架構

```
Notion「追蹤頻道」DB → monitor.py（RSS 偵測新影片）
                          ↓
                    transcript.py（youtube-transcript-api 取英文字幕）
                          ↓
                    article.py（Gemini gemini-2.0-flash → 繁中文章 JSON）
                          ↓
                    notion_writer.py（Markdown → Notion blocks → 寫入「影片文章」DB）
```

- **config.py**: 從 .env 載入所有設定
- **data/processed_videos.json**: 已處理影片紀錄，防重複

## 關鍵限制

- **notion-client 必須 <2.3.0**：2.3+ 移除了 `databases.query()` 和 `create(properties=...)`，會導致所有 Notion 操作失壞
- **Gemini Free Tier**: 15 RPM / 1500 RPD，main.py 每支影片間隔 5 秒
- **Notion block 上限**: 單一 block 2000 字元，單次 API 最多 100 children blocks
- 文章必須**完整呈現影片內容**，不可刪減

## Notion 設定

- Workspace: 江哲維's（個人，非 DACE 工作用）
- Integration: YT-Article-Bot
- 父頁面「YouTube 學習」下有兩個 DB
- 追蹤頻道 DB 欄位: Name (title), Channel ID (rich_text), Tags (multi_select), Active (checkbox)
- 影片文章 DB 欄位: Title (title), Channel (select), URL (url), Published (date), Tags (multi_select), Summary (rich_text)，正文在 page content
