#!/usr/bin/env python3
"""
校园MIS 数据库重置脚本
======================
功能：
  1. 导出所有数据库的当前数据为 JSON 备份
  2. 清除非固定数据（保留校园建筑、教室、时间段、管理员等基础设施数据）
  3. 支持 --restore <备份目录> 从备份恢复

用法：
  python3 reset_db.py              # 导出备份 + 清除非固定数据
  python3 reset_db.py --dry-run    # 仅预览要清理的内容，不实际执行
  python3 reset_db.py --restore backups/reset_20260617_120000  # 从备份恢复

连接信息：
  主机: 47.93.226.110:3306
  用户: root
"""

import json
import os
import sys
import argparse
from datetime import datetime

import pymysql

# ─── 数据库连接配置 ───────────────────────────────────────────────
DB_HOST = "47.93.226.110"
DB_PORT = 3306
DB_USER = "root"
DB_PASS = ""

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_ROOT = os.path.join(SCRIPT_DIR, "backups")

# ─── 数据库与表的清理策略 ─────────────────────────────────────────
# 每个数据库 -> { "keep": [保留的表名列表], "clear": [需要清空的表名列表] }
# "keep" 中的表不会被清空
# "clear" 中的表会被清空（DELETE FROM）
# 不在任一列表中的表会被导出但不会被清空

CLEANUP_PLAN = {
    "main_database": {
        "keep": ["buildings", "building_adjacency", "classrooms", "sub_services"],
        "clear": ["active_sessions", "course_enrollments", "course_grades"],
    },
    "users_database": {
        "keep": ["admins"],
        "clear": ["students", "teachers"],
    },
    "course_schedule_database": {
        "keep": ["cs_time_slots"],
        "clear": [
            "cs_courses",
            "cs_selection_batches",
            "cs_course_sections",
            "cs_course_requests",
            "cs_schedule_runs",
            "cs_schedule_results",
        ],
    },
    "classroom_database": {
        "keep": [],
        "clear": [
            "courses",
            "announcements",
            "homeworks",
            "submissions",
            "grades",
            "course_students",
            "ddl_items",
        ],
    },
    "campus_wall_database": {
        "keep": [],
        "clear": ["wall_posts", "wall_alerts", "wall_moderation_logs"],
    },
    "secondhand_book": {
        "keep": [],
        "clear": [],  # secondhand_book 与本项目无关，不主动清空
    },
}


def get_connection():
    """建立 MySQL 连接。"""
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def get_all_tables(conn, db_name):
    """获取指定数据库中的所有表名。"""
    conn.select_db(db_name)
    with conn.cursor() as cur:
        cur.execute("SHOW TABLES")
        key = f"Tables_in_{db_name}"
        return [row[key] for row in cur.fetchall()]


def export_table_to_json(conn, db_name, table_name):
    """导出单个表的所有数据为 JSON 可序列化的列表。"""
    conn.select_db(db_name)
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM `{table_name}`")
        rows = cur.fetchall()
    # 序列化 datetime / Decimal / bytes 等类型
    serialized = []
    for row in rows:
        record = {}
        for key, value in row.items():
            record[key] = serialize_value(value)
        serialized.append(record)
    return serialized


def serialize_value(value):
    """将数据库返回值转换为 JSON 兼容类型。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    # float/int/str: 直接返回
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def export_all(conn, backup_dir):
    """导出所有数据库的所有表为 JSON 文件。"""
    print("\n📦 正在导出备份...")
    os.makedirs(backup_dir, exist_ok=True)

    all_db_names = list(CLEANUP_PLAN.keys())
    total_tables = 0
    total_rows = 0

    for db_name in all_db_names:
        db_path = os.path.join(backup_dir, db_name)
        os.makedirs(db_path, exist_ok=True)

        tables = get_all_tables(conn, db_name)
        for table_name in tables:
            rows = export_table_to_json(conn, db_name, table_name)
            filepath = os.path.join(db_path, f"{table_name}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2, default=str)

            total_tables += 1
            total_rows += len(rows)
            print(f"  ✓ {db_name}.{table_name} → {len(rows)} 行")

    print(f"\n✅ 备份完成: {total_tables} 张表, {total_rows} 行 → {backup_dir}")
    return total_tables, total_rows


def clear_table(conn, db_name, table_name):
    """清空指定表的所有数据。"""
    conn.select_db(db_name)
    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM `{table_name}`")
    conn.commit()


def get_row_count(conn, db_name, table_name):
    """获取表的行数。"""
    conn.select_db(db_name)
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS cnt FROM `{table_name}`")
        return cur.fetchone()["cnt"]


def clear_all(conn, dry_run=False):
    """按照 CLEANUP_PLAN 清除非固定数据。"""
    print("\n🧹 开始清理非固定数据...")

    # 临时禁用外键检查，避免跨库外键约束阻止删除
    if not dry_run:
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS=0")

    total_deleted = 0
    report = []

    try:
        for db_name, plan in CLEANUP_PLAN.items():
            keep_tables = plan.get("keep", [])
            clear_tables = plan.get("clear", [])

            if not clear_tables:
                continue

            all_tables = get_all_tables(conn, db_name)

            for table_name in clear_tables:
                if table_name not in all_tables:
                    print(f"  ⚠ {db_name}.{table_name} 表不存在，跳过")
                    continue

                before_count = get_row_count(conn, db_name, table_name)
                if before_count == 0:
                    print(f"  - {db_name}.{table_name}: 已为空")
                    continue

                if dry_run:
                    print(f"  [DRY-RUN] 将清空 {db_name}.{table_name}: {before_count} 行")
                    report.append(f"  [预览] {db_name}.{table_name}: {before_count} 行")
                    total_deleted += before_count
                else:
                    clear_table(conn, db_name, table_name)
                    print(f"  ✓ 清空 {db_name}.{table_name}: {before_count} 行")
                    report.append(f"  {db_name}.{table_name}: {before_count} 行")
                    total_deleted += before_count
    finally:
        # 恢复外键检查
        if not dry_run:
            with conn.cursor() as cur:
                cur.execute("SET FOREIGN_KEY_CHECKS=1")

    print(f"\n{'[DRY-RUN] ' if dry_run else ''}✅ 清理完成: 共 {total_deleted} 行")
    return report


def show_keep_summary(conn):
    """显示保留（固定）数据的概况。"""
    print("\n📌 保留的固定数据:")
    for db_name, plan in CLEANUP_PLAN.items():
        for table_name in plan.get("keep", []):
            try:
                count = get_row_count(conn, db_name, table_name)
                print(f"  ✓ {db_name}.{table_name}: {count} 行")
            except Exception:
                print(f"  ⚠ {db_name}.{table_name}: 表不存在")


# ─── 恢复功能 ───────────────────────────────────────────────────

def restore_from_backup(backup_dir):
    """从 JSON 备份恢复数据。"""
    if not os.path.isdir(backup_dir):
        print(f"❌ 备份目录不存在: {backup_dir}")
        sys.exit(1)

    print(f"\n🔄 从备份恢复: {backup_dir}")

    conn = get_connection()
    conn.cursor().execute("SET FOREIGN_KEY_CHECKS=0")

    total_tables = 0
    total_rows = 0

    for db_name in sorted(os.listdir(backup_dir)):
        db_path = os.path.join(backup_dir, db_name)
        if not os.path.isdir(db_path):
            continue

        # 先清空该数据库的所有表
        tables = get_all_tables(conn, db_name)
        with conn.cursor() as cur:
            for table_name in tables:
                cur.execute(f"DELETE FROM `{table_name}`")
        conn.commit()

        # 从 JSON 恢复数据
        for filename in sorted(os.listdir(db_path)):
            if not filename.endswith(".json"):
                continue
            table_name = filename[:-5]  # 去掉 .json
            filepath = os.path.join(db_path, filename)

            with open(filepath, "r", encoding="utf-8") as f:
                rows = json.load(f)

            if not rows:
                continue

            columns = list(rows[0].keys())
            col_str = ", ".join(f"`{c}`" for c in columns)
            placeholders = ", ".join(["%s"] * len(columns))
            sql = f"INSERT INTO `{table_name}` ({col_str}) VALUES ({placeholders})"

            conn.select_db(db_name)
            with conn.cursor() as cur:
                for record in rows:
                    vals = [record.get(c) for c in columns]
                    cur.execute(sql, vals)
            conn.commit()

            total_tables += 1
            total_rows += len(rows)
            print(f"  ✓ {db_name}.{table_name}: {len(rows)} 行")

    conn.cursor().execute("SET FOREIGN_KEY_CHECKS=1")
    conn.close()
    print(f"\n✅ 恢复完成: {total_tables} 张表, {total_rows} 行")


# ─── 主流程 ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="校园MIS 数据库重置工具 - 导出备份并清除非固定数据"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览将要清理的内容，不实际执行",
    )
    parser.add_argument(
        "--restore",
        metavar="BACKUP_DIR",
        help="从指定备份目录恢复数据（不执行清理）",
    )
    parser.add_argument(
        "--backup-only",
        action="store_true",
        help="仅导出备份，不清理数据",
    )
    args = parser.parse_args()

    # 恢复模式
    if args.restore:
        restore_from_backup(args.restore)
        return

    conn = get_connection()

    try:
        # 生成备份目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(BACKUP_ROOT, f"reset_{timestamp}")

        # 1. 导出备份
        export_all(conn, backup_dir)

        # 2. 写入恢复脚本到备份目录
        restore_script = os.path.join(backup_dir, "restore.py")
        with open(restore_script, "w", encoding="utf-8") as f:
            f.write(
                f'''#!/usr/bin/env python3
"""快速恢复脚本：将备份数据恢复到 MySQL。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from reset_db import restore_from_backup
restore_from_backup("{backup_dir}")
'''
            )
        print(f"\n📝 恢复脚本已生成: {restore_script}")

        # 3. 显示哪些数据会保留
        if not args.backup_only:
            show_keep_summary(conn)

        # 4. 清理（或预览）
        if args.backup_only:
            print("\n⏭  跳过清理（--backup-only 模式）")
        elif args.dry_run:
            clear_all(conn, dry_run=True)
            print("\n💡 这是预览模式，未实际修改数据。去掉 --dry-run 参数可执行实际清理。")
        else:
            # 确认操作
            print("\n" + "=" * 50)
            print("⚠️  即将清除非固定数据！")
            print("=" * 50)
            confirm = input("确认执行清理？输入 YES 继续: ")
            if confirm.strip() != "YES":
                print("❌ 已取消清理操作。备份已保存。")
                conn.close()
                return

            clear_all(conn, dry_run=False)

            # 5. 输出汇总
            print("\n" + "=" * 50)
            print("📊 清理后数据概况")
            print("=" * 50)
            show_keep_summary(conn)

            for db_name, plan in CLEANUP_PLAN.items():
                for table_name in plan.get("clear", []):
                    try:
                        count = get_row_count(conn, db_name, table_name)
                        print(f"  💨 {db_name}.{table_name}: {count} 行")
                    except Exception:
                        pass

        print(f"\n💾 备份文件: {backup_dir}")
        print(f"🔄 恢复命令: python3 reset_db.py --restore {backup_dir}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
