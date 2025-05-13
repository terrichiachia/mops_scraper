# 公開資訊觀測站 台灣上市公司資料爬蟲

一支使用 Selenium + Pandas 抓取「公開資訊觀測站」（MOPS）公司基本資料、營收與財報，並儲存到 PostgreSQL 的自動化爬蟲。

---

## 功能
- 批次爬取多個股票代號 (透過CLI 或在程式中指定)
- 解析公司基本資料、營收（累計＋月報）與財報（資產負債表、損益表、現金流量表），並下載PDF檔案
- 將資料寫入 PostgreSQL，並提供簡易驗證工具 `verify_db.py`

---

## 目錄結構

```
.
├── docker-compose.yml    # Docker Compose 配置
├── README.md
├── requirements.txt      # Python 依賴套件
├── scrape_and_print.py   # 主程式
└── verify_db.py          # 驗證資料庫的輔助程式
```

## 安裝前置需求
* Docker & Docker Compose（推薦，用於容器化）
* 或者 Python 3.11+ 加上 Chrome 瀏覽器（本機運行）

## 使用方式

### 方法 1：使用 Docker Compose（推薦）

Docker Compose 提供最簡單的設置方式，會自動處理資料庫、Chrome 等環境設置。

1. **複製專案**
   ```bash
   git clone https://github.com/terrichiachia/mops_scraper.git
   cd mops_scraper
   ```

2. **啟動服務**
   ```bash
   docker-compose up -d
   ```

3. **查看爬蟲進度**
   ```bash
   docker-compose logs -f crawler
   ```

4. **驗證資料庫**
   ```bash
   docker-compose run --rm crawler python3 verify_db.py --stock_ids 2330 2454
   ```

5. **使用指定股票代碼**
   ```bash
   # 停止默認爬蟲
   docker-compose stop crawler
   
   # 運行爬蟲，指定股票代碼
   docker-compose run --rm crawler python3 scrape_and_print.py --stock_ids 2330 2317 2454
   ```

### 方法 2：本機運行

如果您想在本機運行，需要安裝 Chrome 和相關依賴。

1. **複製專案**
   ```bash
   git clone https://github.com/terrichiachia/mops_scraper.git
   cd mops_scraper
   ```

2. **建立虛擬環境並安裝**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows 使用 .venv\Scripts\activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **設定環境變數**
   建立 `.env` 檔案:
   ```
   DATABASE_URL=postgresql://user:password@host:port/dbname
   DOWNLOAD_DIR=downloads
   ```

4. **運行爬蟲**
   ```bash
   # 爬取預設 10 個代碼
   python scrape_and_print.py
   
   # 或指定要爬的列表
   python scrape_and_print.py --stock_ids 2330 2317 2454
   ```

## 資料庫驗證

執行以下命令可檢查資料是否成功寫入各個表格：

```bash
python verify_db.py --stock_ids 2330 2317 2454
```

這將顯示每個股票代碼在各個表中的資料筆數，格式如下：

```
===== 資料庫寫入檢查結果 =====

company_id  company_info  company_revenue  balance_sheet  income_statement  cash_flow  financial_data_combined
      2330            1               12              4                 4          4                       4
      2317            1               10              3                 3          3                       3
      2454            1                9              3                 3          3                       3
```

## 資料庫結構

系統會建立以下表格：

- `company_info`：公司基本資料
- `company_revenue`：公司營收數據（月報和累計）
- `balance_sheet`：資產負債表
- `income_statement`：損益表
- `cash_flow`：現金流量表
- `financial_data_combined`：財務資料合併表

## 技術說明

### 系統架構

- **前端爬蟲**：使用 Selenium 控制 Chrome 瀏覽器，抓取公開資訊觀測站的資料
- **資料解析**：使用 Pandas 解析 HTML 表格資料
- **資料儲存**：使用 SQLAlchemy 將資料儲存到 PostgreSQL 資料庫
- **容器化**：使用 Docker 與 Docker Compose 實現容器化部署

### Selenium 與 Chrome 版本匹配

由於 Selenium 要求 ChromeDriver 和 Chrome 版本必須匹配，我們使用 Selenium 官方提供的 Docker 映像 `selenium/standalone-chrome:114.0`，確保兩者版本完全匹配，避免版本不匹配導致的問題。

## 進階配置

### 自訂股票清單

如要修改預設股票清單，可以編輯 `scrape_and_print.py` 中的 `DEFAULT_STOCK_IDS` 變數：

```python
DEFAULT_STOCK_IDS = [
    "2330", "2454", "2317", "2412", "2882", "2881", "2303", "1301", "3711", "0001",
]
```
