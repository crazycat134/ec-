"""SQLite 初始化与连接：data/app.db，photos 与 products 两张表。"""
import sqlite3
from pathlib import Path

from .config import PROJECT_ROOT

DB_PATH = PROJECT_ROOT / "data" / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    local_path  TEXT NOT NULL,
    file_hash   TEXT NOT NULL UNIQUE,
    product_id  INTEGER,
    product_no  INTEGER,
    photo_no    INTEGER,
    created_at  TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    price       INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'CLEAN',
    description TEXT DEFAULT '',
    mercari_id  TEXT,
    product_no  INTEGER,
    is_draft    INTEGER NOT NULL DEFAULT 0,
    categories  TEXT,
    created_at  TEXT DEFAULT (datetime('now', 'localtime'))
);
"""


def get_db():
    """返回可像字典访问的 SQLite 连接（sqlite3.Row）。调用方负责关闭。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库文件与表结构，重复调用安全；旧库自动补列。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()


def _migrate(conn):
    """为旧库补充新列与索引（SQLite 的 ADD COLUMN 需逐个判断）。"""
    photo_cols = {r["name"] for r in conn.execute("PRAGMA table_info(photos)")}
    if "product_no" not in photo_cols:
        conn.execute("ALTER TABLE photos ADD COLUMN product_no INTEGER")
    if "photo_no" not in photo_cols:
        conn.execute("ALTER TABLE photos ADD COLUMN photo_no INTEGER")
    prod_cols = {r["name"] for r in conn.execute("PRAGMA table_info(products)")}
    if "product_no" not in prod_cols:
        conn.execute("ALTER TABLE products ADD COLUMN product_no INTEGER")
    if "is_draft" not in prod_cols:
        conn.execute("ALTER TABLE products ADD COLUMN is_draft INTEGER NOT NULL DEFAULT 0")
    if "categories" not in prod_cols:
        conn.execute("ALTER TABLE products ADD COLUMN categories TEXT")
    if "confirmed" not in prod_cols:
        conn.execute("ALTER TABLE products ADD COLUMN confirmed INTEGER NOT NULL DEFAULT 0")
    if "works_confirmed" not in prod_cols:
        conn.execute("ALTER TABLE products ADD COLUMN works_confirmed INTEGER NOT NULL DEFAULT 0")
    if "accessories" not in prod_cols:
        conn.execute("ALTER TABLE products ADD COLUMN accessories TEXT")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_products_product_no ON products(product_no)")
