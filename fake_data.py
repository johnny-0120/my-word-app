import sqlite3
import datetime

# 強化版單字包：包含諧音 (Mnemonic) 與 搭配 (Collocation)
advanced_words = [
    {
        "word": "ephemeral", 
        "def": "短暫的；轉瞬即逝的", 
        "pos": "adj.",
        "col": "ephemeral pleasure",
        "mne": "諧音「愛、粉、抹、了」：愛像粉底抹掉就沒了，形容美麗但短暫。",
        "ex": "The beauty of sunset is **ephemeral**, lasting only a few minutes.",
        "reviews": 85, "correct": 78
    },
    {
        "word": "obfuscate", 
        "def": "使模糊；使困惑", 
        "pos": "v.",
        "col": "obfuscate the issue",
        "mne": "字根 ob (朝向) + fusc (黑暗)：把事情帶向黑暗，讓人看不清楚。",
        "ex": "Do not try to **obfuscate the issue** with irrelevant details.",
        "reviews": 42, "correct": 15
    },
    {
        "word": "ubiquitous", 
        "def": "無所不在的", 
        "pos": "adj.",
        "col": "ubiquitous influence",
        "mne": "諧音「有比、快、吐了」：到處都是比這還爛的東西，多到快吐了。",
        "ex": "Coffee shops are **ubiquitous** in this city; there is one on every corner.",
        "reviews": 150, "correct": 142
    },
    {
        "word": "fastidious", 
        "def": "愛乾淨的；挑剔的", 
        "pos": "adj.",
        "col": "fastidious attention",
        "mne": "諧音「發、蹄、爹、死」：豬蹄發炎了老爹就要死要活的，形容非常挑剔。",
        "ex": "She is **fastidious** about keeping her desk organized.",
        "reviews": 60, "correct": 55
    }
]

conn = sqlite3.connect('vocabulary.db')
cursor = conn.cursor()

user = cursor.execute('SELECT id FROM users LIMIT 1').fetchone()
if not user:
    print("請先註冊帳號！")
    exit()
user_id = user[0]

for item in advanced_words:
    cursor.execute('''
        INSERT OR REPLACE INTO words (word, level, part_of_speech, definition, collocation, mnemonic, example1)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (item['word'], 6, item['pos'], item['def'], item['col'], item['mne'], item['ex']))

    word_id = cursor.execute('SELECT id FROM words WHERE word = ?', (item['word'],)).fetchone()[0]
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT OR REPLACE INTO word_user_data (user_id, word_id, review_count, correct_count, last_reviewed)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, word_id, item['reviews'], item['correct'], now))

conn.commit()
conn.close()
print("🎉 高級記憶法單字已匯入！")