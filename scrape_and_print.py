#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
台灣上市公司資料爬蟲與資料庫儲存系統

必要依賴:
selenium, webdriver-manager, pandas, sqlalchemy, psycopg2-binary,
beautifulsoup4, lxml, html5lib, python-dotenv
"""

import os
import sys
import time
import base64
import argparse
import logging
import pandas as pd
import re
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from requests.exceptions import RequestException

# 載入環境變數
load_dotenv()

# 配置日誌
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 全域設定
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
)
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
DEFAULT_STOCK_IDS = [
    "2330",
    "2454",
    "2317",
    "2412",
    "2882",
    "2881",
    "2303",
    "1301",
    "3711",
    "0001",
]
# 重試參數
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# 建立並重用同一個 Engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def setup_chrome_options() -> Options:
    """設定 Chrome 選項"""
    chrome_options = Options()
    # 根據 Chrome 版本決定 Headless 參數
    chrome_options.add_argument("--headless")  # 普遍相容
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--lang=zh-TW")
    chrome_options.add_argument("--kiosk-printing")  # PDF 列印
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    return chrome_options


def setup_database() -> bool:
    """設置資料庫表格結構"""
    ddl_statements = [
        """
        CREATE TABLE IF NOT EXISTS company_info (
            company_id VARCHAR(10) PRIMARY KEY,
            chairman VARCHAR(100),
            ceo VARCHAR(100),
            spokesperson VARCHAR(100),
            address VARCHAR(255),
            phone VARCHAR(20),
            website VARCHAR(255),
            main_business VARCHAR(255),
            capital DECIMAL(20, 2),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS company_revenue (
            id SERIAL PRIMARY KEY,
            company_id VARCHAR(10) NOT NULL,
            year INT NOT NULL,
            month INT NOT NULL,
            revenue_type VARCHAR(20) NOT NULL,
            current_revenue DECIMAL(20, 2),
            previous_revenue DECIMAL(20, 2),
            growth_rate DECIMAL(10, 2),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT company_revenue_unique UNIQUE (company_id, year, month, revenue_type)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS balance_sheet (
            id SERIAL PRIMARY KEY,
            company_id VARCHAR(10) NOT NULL,
            year INT NOT NULL,
            total_assets DECIMAL(20, 2),
            total_liabilities DECIMAL(20, 2),
            total_equity DECIMAL(20, 2),
            net_worth_per_share DECIMAL(10, 2),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT balance_sheet_unique UNIQUE (company_id, year)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS income_statement (
            id SERIAL PRIMARY KEY,
            company_id VARCHAR(10) NOT NULL,
            year INT NOT NULL,
            operating_revenue DECIMAL(20, 2),
            operating_profit DECIMAL(20, 2),
            profit_before_tax DECIMAL(20, 2),
            earnings_per_share DECIMAL(10, 2),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT income_statement_unique UNIQUE (company_id, year)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS cash_flow (
            id SERIAL PRIMARY KEY,
            company_id VARCHAR(10) NOT NULL,
            year INT NOT NULL,
            operating_cash_flow DECIMAL(20, 2),
            investing_cash_flow DECIMAL(20, 2),
            financing_cash_flow DECIMAL(20, 2),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT cash_flow_unique UNIQUE (company_id, year)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS financial_data_combined (
            id SERIAL PRIMARY KEY,
            company_id VARCHAR(10) NOT NULL,
            year INT NOT NULL,
            total_assets DECIMAL(20, 2),
            total_liabilities DECIMAL(20, 2),
            total_equity DECIMAL(20, 2),
            net_worth_per_share DECIMAL(10, 2),
            operating_revenue DECIMAL(20, 2),
            operating_profit DECIMAL(20, 2),
            profit_before_tax DECIMAL(20, 2),
            earnings_per_share DECIMAL(10, 2),
            operating_cash_flow DECIMAL(20, 2),
            investing_cash_flow DECIMAL(20, 2),
            financing_cash_flow DECIMAL(20, 2),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT financial_data_combined_unique UNIQUE (company_id, year)
        )
        """,
    ]
    try:
        with engine.begin() as conn:
            for ddl in ddl_statements:
                conn.execute(text(ddl))
        logger.info("資料庫表格結構設置完成")
        return True
    except Exception:
        logger.exception("設置資料庫時出錯")
        return False


def validate_stock_id(company_id: str) -> bool:
    """驗證股票代碼格式是否為四位數字"""
    if not re.fullmatch(r"\d{4}", company_id):
        logger.warning(f"股票代碼 {company_id} 格式不正確")
        return False
    return True


def check_data_available(driver, company_id: str) -> bool:
    """檢查頁面是否包含有效公司資料"""
    try:
        page = driver.page_source
        for msg in ["查無所需資料", "無此代號之公司", "尚無資料", "公司代號無效"]:
            if msg in page:
                logger.error(f"{company_id} 查無資料，訊息：{msg}")
                return False
        tables = driver.find_elements(By.TAG_NAME, "table")
        if not tables:
            logger.error(f"{company_id} 無表格數據")
            return False
        return True
    except Exception:
        logger.exception("檢查資料可用性時出錯")
        return False


def get_mops_company_info_pdf(company_id: str, output_path: str = None):
    """
    使用 Selenium 從公開資訊觀測站獲取公司資料並生成 PDF
    返回: (pdf_path, list_of_dataframes) 或 (None, None)
    """
    if output_path is None:
        output_path = os.path.join(DOWNLOAD_DIR, f"mops_{company_id}.pdf")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    chrome_options = setup_chrome_options()

    driver = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), options=chrome_options
            )
            # 偽裝為非自動化
            driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            driver.get(
                f"https://mops.twse.com.tw/mops/#/web/t146sb05?companyId={company_id}"
            )

            # 明確等待：等到 table 出現或 timeout
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )

            if not check_data_available(driver, company_id):
                return None, None

            html = driver.page_source
            dfs = pd.read_html(html, flavor="html5lib")

            # 轉 PDF
            pdf = driver.execute_cdp_cmd(
                "Page.printToPDF",
                {
                    "printBackground": True,
                    "preferCSSPageSize": True,
                },
            )
            with open(output_path, "wb") as f:
                f.write(base64.b64decode(pdf["data"]))

            return os.path.abspath(output_path), dfs

        except Exception:
            logger.exception(f"第 {attempt} 次嘗試載入 {company_id} 時失敗")
            time.sleep(RETRY_DELAY)
        finally:
            if driver:
                driver.quit()

    return None, None


def process_basic_info(company_id: str, df: pd.DataFrame) -> pd.DataFrame:
    """解析並回傳公司基本資料 DataFrame，若失敗回傳空的 DataFrame"""
    try:
        df_t = df.transpose().reset_index(drop=True)
        df_t.columns = df_t.iloc[0].str.replace("：", "", regex=False)
        df_clean = df_t.iloc[1].to_frame().T
        df_clean["company_id"] = company_id
        mapping = {
            "董事長": "chairman",
            "總經理": "ceo",
            "發言人": "spokesperson",
            "地址": "address",
            "連絡電話": "phone",
            "公司網址": "website",
            "主要經營業務": "main_business",
            "實收資本額": "capital",
        }
        cols = [col for col in mapping if col in df_clean.columns]
        if not cols:
            return pd.DataFrame()
        df_out = df_clean[cols + ["company_id"]].rename(columns=mapping)
        if "capital" in df_out:
            df_out["capital"] = (
                df_out["capital"]
                .astype(str)
                .str.replace(",", "")
                .str.extract(r"(\d+)", expand=False)
                .astype(float, errors="ignore")
            )
        return df_out
    except Exception:
        logger.exception("解析基本資料失敗")
        return pd.DataFrame()


def parse_revenue_data(df: pd.DataFrame, company_id: str) -> pd.DataFrame:
    """解析營收資料，回傳結構化 DataFrame"""
    records = []
    try:
        # 找到標題列
        header_idx = None
        for i in range(min(3, len(df))):
            if any(h in str(c) for h in ["累計營收", "本月營收"] for c in df.iloc[i]):
                header_idx = i
                break
        if header_idx is not None:
            df = df.iloc[header_idx:].reset_index(drop=True)
        # 累計營收 (第1列)
        if len(df) > 1:
            ytd = df.iloc[1].astype(str).tolist()
            cr, pr, gr = (
                pd.to_numeric(ytd[0].replace(",", ""), errors="coerce"),
                pd.to_numeric(ytd[1].replace(",", ""), errors="coerce"),
                pd.to_numeric(ytd[2].replace("%", ""), errors="coerce"),
            )
            records.append(
                {
                    "company_id": company_id,
                    "year": pd.Timestamp.now().year,
                    "month": pd.Timestamp.now().month,
                    "revenue_type": "accumulated",
                    "current_revenue": cr,
                    "previous_revenue": pr,
                    "growth_rate": gr,
                }
            )
        # 月營收 (後續成對列)
        for i in range(2, len(df), 2):
            title = str(df.iloc[i, 0])
            m = re.search(r"(\d+)年(\d+)月", title)
            if not m or i + 1 >= len(df):
                continue
            y, mth = int(m.group(1)) + 1911, int(m.group(2))
            row = df.iloc[i + 1].astype(str).tolist()
            cr, pr, gr = (
                pd.to_numeric(row[0].replace(",", ""), errors="coerce"),
                pd.to_numeric(row[1].replace(",", ""), errors="coerce"),
                pd.to_numeric(row[2].replace("%", ""), errors="coerce"),
            )
            records.append(
                {
                    "company_id": company_id,
                    "year": y,
                    "month": mth,
                    "revenue_type": "monthly",
                    "current_revenue": cr,
                    "previous_revenue": pr,
                    "growth_rate": gr,
                }
            )
    except Exception:
        logger.exception("解析營收資料失敗")
    return pd.DataFrame(records)


def process_financial_statements(df: pd.DataFrame, company_id: str) -> pd.DataFrame:
    """解析財報資料，回傳 balance_sheet, income_statement, cash_flow 合併 DataFrame"""
    try:
        # 找年度欄位
        years = []
        for col in df.columns:
            m = re.search(r"(\d+)年度", str(col))
            if m:
                years.append(int(m.group(1)))
        if not years:
            return pd.DataFrame()
        bs_rows, is_rows, cf_rows = [], [], []
        for idx, col in enumerate(df.columns):
            if "年度" not in str(col):
                continue
            y = years.pop(0) + 1911
            vals = df[col].astype(str).tolist()
            # 根據索引加入
            bs_rows.append(
                {
                    "company_id": company_id,
                    "year": y,
                    "total_assets": pd.to_numeric(vals[1], errors="coerce"),
                    "total_liabilities": pd.to_numeric(vals[2], errors="coerce"),
                    "total_equity": pd.to_numeric(vals[3], errors="coerce"),
                    "net_worth_per_share": pd.to_numeric(vals[4], errors="coerce"),
                }
            )
            is_rows.append(
                {
                    "company_id": company_id,
                    "year": y,
                    "operating_revenue": pd.to_numeric(vals[6], errors="coerce"),
                    "operating_profit": pd.to_numeric(vals[7], errors="coerce"),
                    "profit_before_tax": pd.to_numeric(vals[8], errors="coerce"),
                    "earnings_per_share": pd.to_numeric(vals[9], errors="coerce"),
                }
            )
            cf_rows.append(
                {
                    "company_id": company_id,
                    "year": y,
                    "operating_cash_flow": pd.to_numeric(vals[11], errors="coerce"),
                    "investing_cash_flow": pd.to_numeric(vals[12], errors="coerce"),
                    "financing_cash_flow": pd.to_numeric(vals[13], errors="coerce"),
                }
            )
        # 合併
        df_bs = pd.DataFrame(bs_rows)
        df_is = pd.DataFrame(is_rows)
        df_cf = pd.DataFrame(cf_rows)
        df_combined = df_bs.merge(df_is, on=["company_id", "year"]).merge(
            df_cf, on=["company_id", "year"]
        )
        return df_combined
    except Exception:
        logger.exception("解析財報資料失敗")
        return pd.DataFrame()


def upsert_dataframe(
    df: pd.DataFrame, table: str, conflict_cols: list, update_cols: list
):
    """批次 upsert DataFrame 到資料庫"""
    if df.empty:
        return 0
    cols = df.columns.tolist()
    insert_cols = ", ".join(cols)
    values = ", ".join(f":{c}" for c in cols)
    updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in update_cols)
    sql = text(
        f"""
        INSERT INTO {table} ({insert_cols})
        VALUES ({values})
        ON CONFLICT ({', '.join(conflict_cols)}) DO UPDATE
          SET {updates}, updated_at = CURRENT_TIMESTAMP
    """
    )
    with engine.begin() as conn:
        result = conn.execute(sql, df.to_dict(orient="records"))
    return result.rowcount


def handle_single_stock(stock_id: str) -> None:
    """整合流程：爬取→解析→寫入"""
    logger.info(f"開始處理 {stock_id}")
    if not validate_stock_id(stock_id):
        logger.warning(f"{stock_id} 代碼格式警告，但繼續")
    pdf_path, dfs = get_mops_company_info_pdf(stock_id)
    if pdf_path is None or not dfs:
        logger.error(f"{stock_id} 爬取失敗")
        return

    # 基本資料
    df_basic = process_basic_info(stock_id, dfs[0])
    if not df_basic.empty:
        upsert_dataframe(
            df_basic,
            "company_info",
            ["company_id"],
            [c for c in df_basic.columns if c != "company_id"],
        )

    # 營收
    if len(dfs) > 2:
        df_rev = parse_revenue_data(dfs[2], stock_id)
        if not df_rev.empty:
            upsert_dataframe(
                df_rev,
                "company_revenue",
                ["company_id", "year", "month", "revenue_type"],
                ["current_revenue", "previous_revenue", "growth_rate"],
            )

    # 財報
    if len(dfs) > 3:
        df_fin = process_financial_statements(dfs[3], stock_id)
        if not df_fin.empty:
            # 分拆各表 upsert
            upsert_dataframe(
                df_fin[
                    [
                        "company_id",
                        "year",
                        "total_assets",
                        "total_liabilities",
                        "total_equity",
                        "net_worth_per_share",
                    ]
                ],
                "balance_sheet",
                ["company_id", "year"],
                [
                    "total_assets",
                    "total_liabilities",
                    "total_equity",
                    "net_worth_per_share",
                ],
            )
            upsert_dataframe(
                df_fin[
                    [
                        "company_id",
                        "year",
                        "operating_revenue",
                        "operating_profit",
                        "profit_before_tax",
                        "earnings_per_share",
                    ]
                ],
                "income_statement",
                ["company_id", "year"],
                [
                    "operating_revenue",
                    "operating_profit",
                    "profit_before_tax",
                    "earnings_per_share",
                ],
            )
            upsert_dataframe(
                df_fin[
                    [
                        "company_id",
                        "year",
                        "operating_cash_flow",
                        "investing_cash_flow",
                        "financing_cash_flow",
                    ]
                ],
                "cash_flow",
                ["company_id", "year"],
                ["operating_cash_flow", "investing_cash_flow", "financing_cash_flow"],
            )
            # 合併表
            upsert_dataframe(
                df_fin,
                "financial_data_combined",
                ["company_id", "year"],
                [c for c in df_fin.columns if c not in ["company_id", "year"]],
            )

    logger.info(f"{stock_id} 處理完成，PDF 已儲存: {pdf_path}")


def main():
    parser = argparse.ArgumentParser(description="批次爬取並儲存上市公司資料")
    parser.add_argument(
        "--stock_ids", nargs="+", default=DEFAULT_STOCK_IDS, help="要爬取的股票代碼清單"
    )
    args = parser.parse_args()

    stock_list = args.stock_ids or [
        "2330",
        "2454",
        "2317",
        "2412",
        "2882",
        "2881",
        "2303",
        "1301",
        "3711",
        "0001",
    ]

    if not setup_database():
        logger.error("資料庫初始化失敗，程式終止")
        sys.exit(1)

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    for idx, sid in enumerate(stock_list, start=1):
        logger.info(f"進度 {idx}/{len(args.stock_ids)}")
        try:
            handle_single_stock(sid)
        except Exception:
            logger.exception(f"處理 {sid} 時發生未預期錯誤")
        time.sleep(3)  # 避免過度頻繁

    logger.info("所有股票處理完成")


if __name__ == "__main__":
    main()
