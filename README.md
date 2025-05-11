# 公開資訊觀測站 台灣上市公司資料爬蟲

一支使用 Selenium + Pandas 抓取「公開資訊觀測站」（MOPS）公司基本資料、營收與財報，並儲存到 PostgreSQL 的自動化爬蟲。

---

## 功能
- 批次爬取多個股票代號 (透過CLI 或在 程式中指定)
- 解析公司基本資料、營收（累計＋月報）與財報（資產負債表、損益表、現金流量表），並下載PDF檔案。
- 將資料寫入 PostgreSQL，並提供簡易驗證工具`verify_db.py`

---

## 目錄結構

.
├── Dockerfile
├── README.md
├── requirements.txt
├── scrape.ipynb        # 開發測試用 Notebook（已忽略於 Git）
├── scrape_and_print.py # 主程式
└── verify_db.py        # 驗證資料庫的輔助程式

## 安裝前置需求
* Python 3.11+
* Docker & Docker Compose（可選，用於容器化）
* PostgreSQL 伺服器
### 1.Clone Repository
```
git clone https://github.com/terrichiachia/mops_scraper.git
cd mops_scraper
```
### 2.建立虛擬環境並安裝
```
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```
### 3.設定環境變數
建立`.env`:
```
DATABASE_URL=postgresql://user:password@host:port/dbname
DOWNLOAD_DIR=downloads
```
## 使用方式
### 透過Command Line
```
# 爬取預設 10 個代碼（含測試代碼 0001）
python scrape_and_print.py

# 或指定要爬的列表
python scrape_and_print.py --stock_ids 2330 2317 2454
```
## 驗證資料庫
執行:
```
python verify_db.py --stock_ids 2330 2317 2454
```
會顯示每個代碼在各個表的筆數，確認是否成功寫入。

## Docker 化部署
### 1.建置容器映像
在專案根目錄執行:
```
docker build -t mops-crawler:latest .
```
### 2.執行容器
透過下列指令啟動容器，並將本機 `downloads/` 與容器內的 `/app/downloads` 做資料夾映射
```
# 設定 DATABASE_URL 環境變數，並與 downloads 目錄綁定
docker run --rm \
  -e DATABASE_URL="${DATABASE_URL}" \
  -e DOWNLOAD_DIR="/app/downloads" \
  -v "$(pwd)/downloads:/app/downloads" \
  mops-crawler:latest \
  --stock_ids 2330 2317 2454
```
* `--rm`:容器執行完畢後自動移除。
* `-e`:傳遞環境變數給容器。
* `-v`:掛載本機資料夾。
* 最後的參數是要傳給`scrape_and_print.py`的`--stock_ids`
執行後，可在本機 `downloads/` 看到產生的 PDF，資料也會寫入指定的 PostgreSQL。