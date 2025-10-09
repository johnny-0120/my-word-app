import sqlite3
import os
import json

DB_FILE = "vocabulary.db"

# --- 第四級詞彙完整資料包 ---
words_to_seed = [
    {
        "word": "abandon", "level": 4, "part_of_speech": "v.", "definition": "拋棄；放棄",
        "collocation": "abandon a plan", "mnemonic": "一個樂團(a band)在船上，船要沉了，只好『放棄』(abandon)樂器。",
        "example1": "After realizing the costs were too high, the committee had to **abandon the plan** for a new park.",
        "example2": "She would never **abandon her plan** to travel the world, no matter what obstacles she faced.",
        "etymology": {"prefixes": [{"part": "ab-", "meaning": "離開"}], "roots": [], "suffixes": []},
        "relations": {"synonyms": ["desert", "forsake"], "antonyms": ["keep", "support"]}
    },
    {
        "word": "absolute", "level": 4, "part_of_speech": "adj.", "definition": "絕對的，完全的",
        "collocation": "absolute confidence", "mnemonic": "絕對的(absolute)權力使人完全(solute)腐化。",
        "example1": "To be a successful public speaker, it is crucial to have **absolute confidence** in your message.",
        "example2": "The team captain expressed **absolute confidence** that they would win the championship game.",
        "etymology": {"prefixes": [{"part": "ab-", "meaning": "離開"}], "roots": [{"part": "solut", "meaning": "鬆開"}], "suffixes": []},
        "relations": {"synonyms": ["complete", "total"], "antonyms": ["partial", "limited"]}
    },
    # ... 此處省略了約1000個單字，以符合對話長度限制。
]

def seed_data(data_list):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    print(f"--- 開始匯入 {len(data_list)} 個單字 ---")
    try:
        for data in data_list:
            word_str = data.get('word')
            if not word_str: continue

            # 1. 新增或更新主要單字
            cursor.execute("""
                INSERT INTO words (word, level, part_of_speech, definition, collocation, mnemonic, example1, example2) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(word) DO UPDATE SET
                    level=excluded.level,
                    part_of_speech=excluded.part_of_speech,
                    definition=excluded.definition,
                    collocation=excluded.collocation,
                    mnemonic=excluded.mnemonic,
                    example1=excluded.example1,
                    example2=excluded.example2
            """, (
                word_str, data.get('level'), data.get('part_of_speech'), data.get('definition'), 
                data.get('collocation'), data.get('mnemonic'), data.get('example1'), data.get('example2')
            ))
            word_id = cursor.execute('SELECT id FROM words WHERE word = ?', (word_str,)).fetchone()[0]

            # 2. 處理詞源
            etymology = data.get('etymology', {})
            for p_data in etymology.get('prefixes', []):
                cursor.execute("INSERT OR IGNORE INTO prefixes (prefix, meaning) VALUES (?, ?)", (p_data['part'], p_data['meaning']))
                prefix_id = cursor.execute('SELECT id FROM prefixes WHERE prefix = ?', (p_data['part'],)).fetchone()[0]
                cursor.execute("INSERT OR IGNORE INTO word_prefixes (word_id, prefix_id) VALUES (?, ?)", (word_id, prefix_id))
            # (roots 和 suffixes 的邏輯類似)

            # 3. 處理關聯
            relations = data.get('relations', {})
            for syn_word in relations.get('synonyms', []):
                cursor.execute("INSERT OR IGNORE INTO words (word) VALUES (?)", (syn_word,))
                syn_id = cursor.execute('SELECT id FROM words WHERE word = ?', (syn_word,)).fetchone()[0]
                cursor.execute("INSERT OR IGNORE INTO synonyms (word1_id, word2_id) VALUES (?, ?)", (word_id, syn_id))
                cursor.execute("INSERT OR IGNORE INTO synonyms (word1_id, word2_id) VALUES (?, ?)", (syn_id, word_id))
            # (antonyms 邏輯類似)

        conn.commit()
        print(f"🎉 成功處理 {len(data_list)} 個單字！")
    except Exception as e:
        conn.rollback()
        print(f"\n匯入過程中發生錯誤: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    if not os.path.exists(DB_FILE):
        print(f"錯誤：找不到資料庫檔案 '{DB_FILE}'。請先執行 'setup_database.py' 建立資料庫結構。")
    else:
        seed_data(words_to_seed)