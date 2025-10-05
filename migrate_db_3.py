# migrate_db_3.py (最終一步到位版)
import sqlite3

conn = sqlite3.connect('vocabulary.db')
cursor = conn.cursor()

print("正在為資料庫進行使用者系統擴建...")

# 1. 建立 users 資料表 (直接包含 google_id 欄位)
try:
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            google_id TEXT UNIQUE 
        )
    ''')
    print(" -> 'users' 資料表建立成功 (已包含 google_id)！")
except Exception as e:
    print(f" -> 'users' 資料表建立時發生錯誤 (可能已存在): {e}")

# 2. 在 words 資料表中新增 user_id 欄位
try:
    cursor.execute("ALTER TABLE words ADD COLUMN user_id INTEGER REFERENCES users(id)")
    print(" -> 'words' 資料表擴充成功！已新增 user_id 欄位。")
except Exception as e:
    print(f" -> 'words' 資料表擴充時發生錯誤 (可能欄位已存在): {e}")

conn.commit()
conn.close()

print("\n擴建完成！你的資料庫現在擁有最終結構。")