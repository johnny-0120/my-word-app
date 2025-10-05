# migrate_db_1.py
import sqlite3

conn = sqlite3.connect('vocabulary.db')
cursor = conn.cursor()

# 使用 ALTER TABLE 指令新增一個名為 etymology 的欄位 (存放字根字首)
# 我們用 try...except 以防我們重複執行這個腳本而出錯
try:
    cursor.execute("ALTER TABLE words ADD COLUMN etymology TEXT")
    print("資料庫升級成功：已新增 etymology 欄位！")
except Exception as e:
    print(f"資料庫升級時發生錯誤 (可能欄位已存在): {e}")

conn.commit()
conn.close()