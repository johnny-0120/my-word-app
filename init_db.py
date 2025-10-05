# init_db.py
import sqlite3

# 連接到資料庫檔案 (如果不存在，它會自動被建立)
connection = sqlite3.connect('vocabulary.db')
cursor = connection.cursor()

# 建立一個名為 'words' 的資料表
# TEXT NOT NULL 代表這個欄位必須是文字，且不能是空的
# INTEGER PRIMARY KEY AUTOINCREMENT 代表這是一個會自動增加的數字ID
cursor.execute('''
    CREATE TABLE IF NOT EXISTS words (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        word TEXT NOT NULL,
        definition TEXT NOT NULL,
        example_sentence TEXT,
        date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# 提交變更並關閉連接
connection.commit()
connection.close()

print("資料庫和資料表建立成功！")