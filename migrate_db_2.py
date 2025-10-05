# migrate_db_2.py
import sqlite3

conn = sqlite3.connect('vocabulary.db')
cursor = conn.cursor()

try:
    # 新增 'review_count' 欄位，記錄總複習次數，預設為 0
    cursor.execute("ALTER TABLE words ADD COLUMN review_count INTEGER NOT NULL DEFAULT 0")
    # 新增 'correct_count' 欄位，記錄答對次數，預設為 0
    cursor.execute("ALTER TABLE words ADD COLUMN correct_count INTEGER NOT NULL DEFAULT 0")
    # 新增 'last_reviewed' 欄位，記錄上次複習時間
    cursor.execute("ALTER TABLE words ADD COLUMN last_reviewed TIMESTAMP")
    print("資料庫第二次升級成功！已新增進度追蹤欄位。")
except Exception as e:
    print(f"資料庫升級時發生錯誤 (可能欄位已存在): {e}")

conn.commit()
conn.close()