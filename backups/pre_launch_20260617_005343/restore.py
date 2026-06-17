"""
快速恢复脚本：将备份 JSON 数据恢复到 MySQL。
用法: python3 restore.py
"""
import pymysql, json, os, glob

DB_HOST = "47.93.226.110"
DB_PORT = 3306
DB_USER = "root"
DB_PASS = ""

BACKUP_DIR = os.path.dirname(os.path.abspath(__file__))

conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, charset="utf8mb4")
cur = conn.cursor()

# 先清空所有表
cur.execute("SET FOREIGN_KEY_CHECKS=0")
for db_name in os.listdir(BACKUP_DIR):
    db_path = os.path.join(BACKUP_DIR, db_name)
    if not os.path.isdir(db_path):
        continue
    cur.execute(f"USE {db_name}")
    for fpath in glob.glob(os.path.join(db_path, "*.json")):
        tbl = os.path.splitext(os.path.basename(fpath))[0]
        cur.execute(f"DELETE FROM `{tbl}`")
        print(f"  清空 {db_name}.{tbl}")
cur.execute("SET FOREIGN_KEY_CHECKS=1")
conn.commit()

# 恢复数据
cur.execute("SET FOREIGN_KEY_CHECKS=0")
for db_name in sorted(os.listdir(BACKUP_DIR)):
    db_path = os.path.join(BACKUP_DIR, db_name)
    if not os.path.isdir(db_path):
        continue
    cur.execute(f"USE {db_name}")
    for fpath in sorted(glob.glob(os.path.join(db_path, "*.json"))):
        tbl = os.path.splitext(os.path.basename(fpath))[0]
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not data:
            continue
        columns = list(data[0].keys())
        col_str = ", ".join(f"`{c}`" for c in columns)
        placeholders = ", ".join(["%s"] * len(columns))
        sql = f"INSERT INTO `{tbl}` ({col_str}) VALUES ({placeholders})"
        for record in data:
            vals = [record.get(c) for c in columns]
            cur.execute(sql, vals)
        conn.commit()
        print(f"  恢复 {db_name}.{tbl}: {len(data)} 行")
cur.execute("SET FOREIGN_KEY_CHECKS=1")
conn.commit()
conn.close()
print("\n✅ 恢复完成！")
