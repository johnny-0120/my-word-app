# seed_data_level4_part1.py
# 這是「高中參考詞彙表 - 第四級」的第一卷
import sqlite3
import os
import json

DB_FILE = "vocabulary.db"

# --- 第四級詞彙資料包 (第一卷) ---
# 包含了詞性、中文意思、常用搭配、記憶技巧、兩個長例句、字根字首、同義詞、反義詞
words_to_seed = [
    {
        "word": "abandon", "level": 4, "part_of_speech": "v.", "definition": "拋棄；放棄",
        "collocation": "abandon a plan/project", "mnemonic": "想像一個樂團(a band)在船上，船要沉了，只好『放棄』(abandon)樂器。",
        "example1": "Due to the unexpected budget cuts, the research team had to **abandon their project** entirely.",
        "example2": "The mother bird would never abandon her young chicks in the nest, no matter the danger.",
        "etymology": {"prefixes": [{"part": "ab-", "meaning": "離開"}], "roots": [], "suffixes": []},
        "relations": {"synonyms": ["desert", "forsake"], "antonyms": ["keep", "support"]}
    },
    {
        "word": "absolute", "level": 4, "part_of_speech": "adj.", "definition": "絕對的，完全的",
        "collocation": "absolute confidence", "mnemonic": "絕對的(absolute)權力使人完全(solute)腐化。",
        "example1": "To be a successful entrepreneur, you must have **absolute confidence** in your own abilities and vision.",
        "example2": "The dictator ruled the country with absolute power for over three decades.",
        "etymology": {"prefixes": [{"part": "ab-", "meaning": "離開"}], "roots": [{"part": "solut", "meaning": "鬆開"}], "suffixes": []},
        "relations": {"synonyms": ["complete", "total", "utter"], "antonyms": ["partial", "limited"]}
    },
    {
        "word": "absorb", "level": 4, "part_of_speech": "v.", "definition": "吸收",
        "collocation": "absorb information", "mnemonic": "想像吸(ab)水的SpongeBob(sorb)，他很會『吸收』資訊。",
        "example1": "It is difficult to **absorb all the information** presented in such a long and dense lecture.",
        "example2": "The dark-colored fabric tends to absorb more heat from the sun on a hot day.",
        "etymology": {"prefixes": [{"part": "ab-", "meaning": "離開, 從"}], "roots": [{"part": "sorb", "meaning": "吸入"}], "suffixes": []},
        "relations": {"synonyms": ["assimilate", "digest", "take in"], "antonyms": ["emit", "reflect"]}
    },
    {
        "word": "abstract", "level": 4, "part_of_speech": "adj.", "definition": "抽象的",
        "collocation": "abstract concept", "mnemonic": "abs(離開)+tract(拉) -> 從具體事物中『拉』出來的概念，就是『抽象的』。",
        "example1": "Freedom is an **abstract concept** that has been defined differently by various philosophers throughout history.",
        "example2": "The artist was famous for her large, abstract paintings filled with vibrant colors and shapes.",
        "etymology": {"prefixes": [{"part": "ab-", "meaning": "離開"}], "roots": [{"part": "tract", "meaning": "拉"}], "suffixes": []},
        "relations": {"synonyms": ["theoretical", "conceptual"], "antonyms": ["concrete", "realistic"]}
    },
    {
        "word": "academic", "level": 4, "part_of_speech": "adj.", "definition": "學術的",
        "collocation": "academic performance", "mnemonic": "在學院(academy)裡做的事，都是『學術的』。",
        "example1": "The university closely monitors the **academic performance** of all its student-athletes.",
        "example2": "She has published numerous articles in prestigious academic journals on the subject of ancient history.",
        "etymology": {"roots": [{"part": "academ", "meaning": "學院"}], "suffixes": [{"part": "-ic", "meaning": "有關...的"}]},
        "relations": {"synonyms": ["scholarly", "educational"], "antonyms": ["practical", "vocational"]}
    },
    # --- 為了篇幅，此處省略約 45 個單字，實際腳本將包含完整內容 ---
]
# --- 創世腳本的主程式 ---
def seed():
    if not os.path.exists(DB_FILE):
        print(f"錯誤：找不到資料庫檔案 '{DB_FILE}'。請先執行 'setup_database.py'。")
        return
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    print("--- 開始填充資料庫 (第四級 - 第一卷) ---")
    try:
        for data in words_to_seed:
            # 1. 新增/取得主要單字 ID
            cursor.execute("INSERT OR IGNORE INTO words (word, level, part_of_speech, definition, collocation, mnemonic, example1, example2) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                         (data['word'], data['level'], data['part_of_speech'], data['definition'], data['collocation'], data['mnemonic'], data['example1'], data['example2']))
            word_id = cursor.execute('SELECT id FROM words WHERE word = ?', (data['word'],)).fetchone()['id']
            # 2. 處理並連結詞源
            etymology = data.get('etymology', {})
            for p_data in etymology.get('prefixes', []):
                cursor.execute("INSERT OR IGNORE INTO prefixes (prefix, meaning) VALUES (?, ?)", (p_data['part'], p_data['meaning']))
                prefix_id = cursor.execute('SELECT id FROM prefixes WHERE prefix = ?', (p_data['part'],)).fetchone()['id']
                cursor.execute("INSERT OR IGNORE INTO word_prefixes (word_id, prefix_id) VALUES (?, ?)", (word_id, prefix_id))
            for r_data in etymology.get('roots', []):
                cursor.execute("INSERT OR IGNORE INTO roots (root, meaning) VALUES (?, ?)", (r_data['root'], r_data['meaning']))
                root_id = cursor.execute('SELECT id FROM roots WHERE root = ?', (r_data['root'],)).fetchone()['id']
                cursor.execute("INSERT OR IGNORE INTO word_roots (word_id, root_id) VALUES (?, ?)", (word_id, root_id))
            for s_data in etymology.get('suffixes', []):
                cursor.execute("INSERT OR IGNORE INTO suffixes (suffix, meaning) VALUES (?, ?)", (s_data['part'], s_data['meaning']))
                suffix_id = cursor.execute('SELECT id FROM suffixes WHERE suffix = ?', (s_data['part'],)).fetchone()['id']
                cursor.execute("INSERT OR IGNORE INTO word_suffixes (word_id, suffix_id) VALUES (?, ?)", (word_id, suffix_id))
            # 3. 處理並連結同義/反義詞
            relations = data.get('relations', {})
            for syn_word in relations.get('synonyms', []):
                syn_row = cursor.execute('SELECT id FROM words WHERE word = ?', (syn_word,)).fetchone()
                if syn_row:
                    syn_id = syn_row['id']
                    cursor.execute("INSERT OR IGNORE INTO synonyms (word1_id, word2_id) VALUES (?, ?)", (word_id, syn_id))
                    cursor.execute("INSERT OR IGNORE INTO synonyms (word1_id, word2_id) VALUES (?, ?)", (syn_id, word_id))
            for ant_word in relations.get('antonyms', []):
                ant_row = cursor.execute('SELECT id FROM words WHERE word = ?', (ant_word,)).fetchone()
                if ant_row:
                    ant_id = ant_row['id']
                    cursor.execute("INSERT OR IGNORE INTO antonyms (word1_id, word2_id) VALUES (?, ?)", (word_id, ant_id))
                    cursor.execute("INSERT OR IGNORE INTO antonyms (word1_id, word2_id) VALUES (?, ?)", (ant_id, word_id))
        conn.commit()
        print(f"\n🎉 恭喜！成功匯入 {len(words_to_seed)} 個第四級核心單字及其關聯！")
    except Exception as e:
        conn.rollback()
        print(f"\n匯入過程中發生錯誤: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    seed()