"""
Shared MySQL connection configuration for seed_data.py and app.py.

Reads credentials from environment variables (falls back to sane local
defaults). A `.env` file in the project root is picked up automatically
via python-dotenv -- copy `.env.example` to `.env` and edit it.
"""

import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "cloud_kitchen")

# Used by seed_data.py (raw pymysql connection)
PYMYSQL_KWARGS = dict(
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME,
    charset="utf8mb4",
    autocommit=False,
)

# Used by app.py (SQLAlchemy engine, works nicely with pandas.read_sql_query)
SQLALCHEMY_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    f"?charset=utf8mb4"
)
