import sqlite3

DB_FILE = "vocabulary.db"

# 整理好的單字記憶法清單
mnemonics_data = {
    "abandon": "一個樂團 (a band) 在船上 (on)，船要沉了，只好『放棄』樂器逃生。",
    "absolute": "絕對的 (absolute) 權力，使人完全 (solute) 腐化。",
    "forsake": "諧音法：佛 (for) 說 (sake) -> 佛說做人不能『背棄』承諾。",
    "desert": "字根聯想：沙漠 (desert) 是一個寸草不生的地方，被丟在那裡就等於被『遺棄』了。"
}

def update_mnemonics():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    print("開始更新單字記憶法...")
    success_count = 0
    
    for word, mnemonic in mnemonics_data.items():
        # 檢查單字是否存在於資料庫中
        cursor.execute("SELECT id FROM words WHERE word = ?", (word,))
        if cursor.fetchone():
            cursor.execute("UPDATE words SET mnemonic = ? WHERE word = ?", (mnemonic, word))
            success_count += 1
            print(f"✅ 已更新 '{word}' 的記憶法")
        else:
            print(f"⚠️ 找不到單字 '{word}'，跳過更新")
            
    conn.commit()
    conn.close()
    print(f"\n🎉 更新完成！共更新了 {success_count} 個單字。")

if __name__ == "__main__":
    update_mnemonics()