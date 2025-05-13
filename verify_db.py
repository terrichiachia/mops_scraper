#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
驗證資料庫中各表是否成功寫入指定股票代號的資料
"""

import os
import sys
import argparse
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# 載入 .env 中的 DATABASE_URL
load_dotenv()
# 全域設定

DB_CONFIG = {
    "dbname": os.environ.get("POSTGRES_DB", "postgres"),
    "user": os.environ.get("POSTGRES_USER", "postgres"),
    "password": os.environ.get("POSTGRES_PASSWORD", "postgres"),
    "host": os.environ.get("POSTGRES_HOST", "db"),  # Docker 內部服務名
    "port": os.environ.get("POSTGRES_PORT", "5432"),
}

default_url = (
    f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
)

DATABASE_URL = os.getenv("DATABASE_URL", default_url)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def verify_stock(stock_id: str) -> dict:
    """回傳該 stock_id 在各表中的資料筆數"""
    queries = {
        "company_info": "SELECT COUNT(*) FROM company_info WHERE company_id = :stock_id",
        "company_revenue": "SELECT COUNT(*) FROM company_revenue WHERE company_id = :stock_id",
        "balance_sheet": "SELECT COUNT(*) FROM balance_sheet WHERE company_id = :stock_id",
        "income_statement": "SELECT COUNT(*) FROM income_statement WHERE company_id = :stock_id",
        "cash_flow": "SELECT COUNT(*) FROM cash_flow WHERE company_id = :stock_id",
        "financial_data_combined": "SELECT COUNT(*) FROM financial_data_combined WHERE company_id = :stock_id",
    }
    results = {"company_id": stock_id}
    with engine.connect() as conn:
        for table, sql in queries.items():
            count = conn.execute(text(sql), {"stock_id": stock_id}).scalar()
            results[table] = int(count or 0)
    return results


def main():
    parser = argparse.ArgumentParser(
        description="驗證指定股票代號在資料庫各表中的寫入狀況"
    )
    parser.add_argument(
        "--stock_ids",
        nargs="+",
        required=True,
        help="要驗證的股票代號列表，例如：2330 2317 2454",
    )
    args = parser.parse_args()

    summary = []
    for sid in args.stock_ids:
        summary.append(verify_stock(sid))

    # 用 pandas 列印成表格
    df = pd.DataFrame(summary)
    print("\n===== 資料庫寫入檢查結果 =====\n")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()