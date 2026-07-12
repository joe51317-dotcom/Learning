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
                    transcript.py（youtube-transcript-api → yt-dlp 備援，皆含 60 秒逾時）
                          ↓
                    article.py（Gemini gemini-2.5-flash-lite → 繁中文章 JSON）
                          ↓
                    notion_writer.py（Markdown → Notion blocks → 寫入「影片文章」DB）
```

- **config.py**: 從 .env 載入所有設定
- **data/processed_videos.json**: 已處理影片紀錄，防重複（僅成功處理的影片會記入，失敗的下輪自動重試）

## 排程

- Windows 工作排程器工作 `YT-to-Notion-Daily`，每天 12:00 執行 `run.bat`（`C:\Python314\python.exe main.py`，輸出寫入 `data/cron.log`）
- `main.py --only "頻道名1,頻道名2"`：只處理名稱含關鍵字的頻道（逗號分隔、不分大小寫），用於優先清特定頻道積壓

## 關鍵限制

- **notion-client 必須 <2.3.0**：2.3+ 移除了 `databases.query()` 和 `create(properties=...)`，會導致所有 Notion 操作失壞
- **Gemini 模型**：現用 `gemini-2.5-flash-lite`。⚠️ `gemini-2.0-flash` 已於 2026 停用（API 回 404 NOT_FOUND），**別再改回去**
- **Gemini 方案是 PAID（付費）**：金鑰名稱 `Default Gemini API Key`、專案 `gen-lang-client-0269586328`（billing enabled）。速率上限高、額度不是瓶頸；main.py 每支影片間隔 45 秒主要是避免 YouTube 逐字稿限流，不是 Gemini 限額
- **YouTube 逐字稿會被限流**：批次連續請求時底層會卡住不回應（非乾脆報錯），故 transcript.py 對每次請求包 60 秒逾時，並有 yt-dlp 備援走不同請求路徑
- **Notion block 上限**: 單一 block 2000 字元，單次 API 最多 100 children blocks
- 文章必須**完整呈現影片內容**，不可刪減（article.py 的 prompt 注入「逐字稿 30% 的實際字元數」當下限來約束 flash-lite 不壓縮）

## Notion 設定

- Workspace: 江哲維's（個人，非 DACE 工作用）
- Integration: YT-Article-Bot
- 父頁面「YouTube 學習」下有兩個 DB
- 追蹤頻道 DB 欄位: Name (title), Channel ID (rich_text), Tags (multi_select), Active (checkbox)
- 影片文章 DB 欄位: Title (title), Channel (select), URL (url), Published (date), Tags (multi_select), Summary (rich_text)，正文在 page content
