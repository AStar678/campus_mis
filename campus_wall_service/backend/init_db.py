from pathlib import Path
import os
from urllib.parse import unquote

import pymysql


BASE_DIR = Path(__file__).resolve().parent
SCHEMA_FILE = BASE_DIR / "schema.sql"

DB_HOST = os.environ.get("DB_HOST", "47.93.226.110")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASS = os.environ.get("DB_PASS", "MySQL%402026")
DB_PASS_RAW = os.environ.get("DB_PASS_RAW", unquote(DB_PASS))
WALL_DB_NAME = os.environ.get("WALL_DB_NAME", "campus_wall_database")


def split_sql_statements(sql_text):
    statements = []
    current = []
    quote = None
    escaped = False

    for char in sql_text:
        current.append(char)
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
        elif char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement[:-1].strip())
            current = []

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def connect_mysql():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS_RAW,
        charset="utf8mb4",
        autocommit=True,
    )


def init_database():
    sql_text = SCHEMA_FILE.read_text(encoding="utf-8")
    statements = split_sql_statements(sql_text)
    with connect_mysql() as conn:
        with conn.cursor() as cursor:
            for statement in statements:
                if statement:
                    cursor.execute(statement)
            ensure_schema_updates(cursor)
    print(f"{SCHEMA_FILE.name}: executed {len(statements)} statements.")


def ensure_schema_updates(cursor):
    if not column_exists(cursor, "wall_posts", "image_paths"):
        cursor.execute(f"ALTER TABLE `{WALL_DB_NAME}`.`wall_posts` ADD COLUMN image_paths TEXT AFTER matched_keywords")

    if not column_exists(cursor, "wall_alerts", "alert_type"):
        cursor.execute(
            f"""
            ALTER TABLE `{WALL_DB_NAME}`.`wall_alerts`
            ADD COLUMN alert_type VARCHAR(30) NOT NULL DEFAULT 'post_keyword' AFTER post_id
            """
        )
    if not column_exists(cursor, "wall_alerts", "handled_by"):
        cursor.execute(f"ALTER TABLE `{WALL_DB_NAME}`.`wall_alerts` ADD COLUMN handled_by VARCHAR(20) AFTER created_at")
    if not column_exists(cursor, "wall_alerts", "handled_at"):
        cursor.execute(f"ALTER TABLE `{WALL_DB_NAME}`.`wall_alerts` ADD COLUMN handled_at DATETIME AFTER handled_by")

    if not index_exists(cursor, "wall_alerts", "idx_wall_alerts_status_created"):
        cursor.execute(
            f"ALTER TABLE `{WALL_DB_NAME}`.`wall_alerts` ADD INDEX idx_wall_alerts_status_created (status, created_at)"
        )
    if not index_exists(cursor, "wall_alerts", "idx_wall_alerts_level"):
        cursor.execute(f"ALTER TABLE `{WALL_DB_NAME}`.`wall_alerts` ADD INDEX idx_wall_alerts_level (alert_level)")


def column_exists(cursor, table_name, column_name):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        (WALL_DB_NAME, table_name, column_name),
    )
    return cursor.fetchone()[0] > 0


def index_exists(cursor, table_name, index_name):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
          AND INDEX_NAME = %s
        """,
        (WALL_DB_NAME, table_name, index_name),
    )
    return cursor.fetchone()[0] > 0


if __name__ == "__main__":
    init_database()
