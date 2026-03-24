import sqlite3
import datetime

# 準備頂級艱澀單字包
hard_words = [
    {
        "word": "loquacious", "def": "饒舌的；多話的", "pos": "adj.",
        "col": "loquacious neighbor",
        "mne": "【字根】loqu- (speak 說) + -ous (多...的)。【諧音】「撈魁色」：撈到魁首臉色紅潤，滔滔不絕講個不停。",
        "ex": "The **loquacious neighbor** kept me talking for over an hour this morning.",
        "reviews": 180, "correct": 165
    },
    {
        "word": "recalcitrant", "def": "頑抗的；不聽從指揮的", "pos": "adj.",
        "col": "recalcitrant employees",
        "mne": "【字源】re- (向後) + calc- (heels 腳後跟)：像驢子向後踢腳一樣頑強。【諧音】「雷卡死拽」：像雷劈中卡住一樣死拽不動。",
        "ex": "The manager struggled to lead a team of **recalcitrant employees**.",
        "reviews": 35, "correct": 8
    },
    {
        "word": "magnanimous", "def": "寬宏大量的；大度的", "pos": "adj.",
        "col": "magnanimous gesture",
        "mne": "【字根】magn- (large 大) + anim- (mind/soul 心靈)：有顆大心臟的人。",
        "ex": "He was **magnanimous** enough to forgive his enemies after winning the election.",
        "reviews": 92, "correct": 88
    },
    {
        "word": "capricious", "def": "反覆無常的；善變的", "pos": "adj.",
        "col": "capricious weather",
        "mne": "【記憶】字源與「山羊」(capri)有關，像山羊一樣亂跳跳躍、難以捉摸。",
        "ex": "Because of the **capricious weather**, we decided to cancel our hiking trip.",
        "reviews": 120, "correct": 45
    },
    {
        "word": "euphemism", "def": "委婉語；婉轉的說法", "pos": "n.",
        "col": "use a euphemism",
        "mne": "【字根】eu- (good 好) + phem (speak 說)：說好聽的話。",
        "ex": "'Senior citizen' is a common **euphemism** for an elderly person.",
        "reviews": 75, "correct": 70
    }
]

conn = sqlite3.connect('vocabulary.db')
cursor = conn.cursor()

# 確保抓到你的 User ID
user = cursor.execute('SELECT id FROM users LIMIT 1').fetchone()
if not user:
    print("找不到使用者，請先註冊帳號！")
    exit()
user_id = user[0]

for item in hard_words:
    # 存入單字表
    cursor.execute('''
        INSERT OR REPLACE INTO words (word, level, part_of_speech, definition, collocation, mnemonic, example1)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (item['word'], 6, item['pos'], item['def'], item['col'], item['mne'], item['ex']))

    # 存入使用者學習紀錄
    word_id = cursor.execute('SELECT id FROM words WHERE word = ?', (item['word'],)).fetchone()[0]
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT OR REPLACE INTO word_user_data (user_id, word_id, review_count, correct_count, last_reviewed)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, word_id, item['reviews'], item['correct'], now))

conn.commit()
conn.close()
print("🎉 艱澀記憶單字注入成功！")