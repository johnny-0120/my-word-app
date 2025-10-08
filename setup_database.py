# setup_database.py (V.Final - 深度學習卡片版)
import sqlite3
import os

DB_FILE = "vocabulary.db"

if os.path.exists(DB_FILE):
    os.remove(DB_FILE)
    print(f"已刪除舊的資料庫檔案 '{DB_FILE}'。")

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
print("\n正在建立全新的資料庫結構 (深度學習卡片版)...")

# --- 使用者系統 (不變) ---
cursor.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password TEXT NOT NULL, google_id TEXT UNIQUE)')
print(" -> 'users' 資料表建立成功。")

# --- 公共知識庫 (重大升級) ---
cursor.execute('''
    CREATE TABLE words (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        word TEXT NOT NULL UNIQUE,
        level INTEGER,
        part_of_speech TEXT,
        definition TEXT,
        collocation TEXT,
        mnemonic TEXT,
        example1 TEXT,
        example2 TEXT
    )
''')
print(" -> 'words' 主資料表 (擴充版) 建立成功。")

# --- 個人進度表 (不變) ---
cursor.execute('''
    CREATE TABLE word_user_data (
        user_id INTEGER NOT NULL REFERENCES users(id),
        word_id INTEGER NOT NULL REFERENCES words(id),
        review_count INTEGER NOT NULL DEFAULT 0,
        correct_count INTEGER NOT NULL DEFAULT 0,
        last_reviewed TIMESTAMP,
        PRIMARY KEY (user_id, word_id)
    )
''')
print(" -> 'word_user_data' 個人進度表建立成功。")

# --- 關聯表 (不變) ---
cursor.execute('CREATE TABLE synonyms (word1_id INTEGER, word2_id INTEGER, PRIMARY KEY (word1_id, word2_id))')
cursor.execute('CREATE TABLE antonyms (word1_id INTEGER, word2_id INTEGER, PRIMARY KEY (word1_id, word2_id))')
cursor.execute('CREATE TABLE prefixes (id INTEGER PRIMARY KEY, prefix TEXT UNIQUE, meaning TEXT)')
cursor.execute('CREATE TABLE roots (id INTEGER PRIMARY KEY, root TEXT UNIQUE, meaning TEXT)')
cursor.execute('CREATE TABLE suffixes (id INTEGER PRIMARY KEY, suffix TEXT UNIQUE, meaning TEXT)')
cursor.execute('CREATE TABLE word_prefixes (word_id INTEGER, prefix_id INTEGER, PRIMARY KEY (word_id, prefix_id))')
cursor.execute('CREATE TABLE word_roots (word_id INTEGER, root_id INTEGER, PRIMARY KEY (word_id, root_id))')
cursor.execute('CREATE TABLE word_suffixes (word_id INTEGER, suffix_id INTEGER, PRIMARY KEY (word_id, suffix_id))')
print(" -> 所有關聯資料表建立成功。")

conn.commit()
conn.close()
print("\n🎉 恭喜！你的單字宇宙最終基礎建設已完成！")