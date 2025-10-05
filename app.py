# app.py (第十版，功能完整最終版 + AJAX API)
import sqlite3
import random
import re # 確保頂部有 import re
import json

def contains_chinese(text):
    # 這個正規表達式會匹配中文字元
    return bool(re.search(r'[\u4e00-\u9fff]', text))
from flask import Flask, render_template, request, redirect, url_for, jsonify
# 修改 from a_gemini_tool import ... 這一行
from a_gemini_tool import get_word_info, get_sentence_feedback, get_wrong_answer_explanation, get_english_suggestions_from_chinese, generate_multi_word_cloze

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('vocabulary.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- 核心路由 ---
@app.route('/')
def index():
    query = request.args.get('query')
    conn = get_db_connection()
    if query:
        search_term = f"%{query}%"
        words = conn.execute('SELECT * FROM words WHERE word LIKE ? OR definition LIKE ? OR example_sentence LIKE ? ORDER BY id DESC', (search_term, search_term, search_term)).fetchall()
    else:
        words = conn.execute('SELECT * FROM words ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('index.html', words=words, query=query)

# --- 新增單字流程 ---
@app.route('/add')
def add_choice():
    return render_template('add_choice.html')

@app.route('/add/smart')
def add_smart():
    return render_template('add_smart.html')

@app.route('/add/manual', methods=('GET', 'POST'))
def add_manual():
    if request.method == 'POST':
        word = request.form['word']
        definition = request.form['definition']
        example_sentence = request.form['example_sentence']
        etymology = request.form['etymology']
        conn = get_db_connection()
        conn.execute('INSERT INTO words (word, definition, example_sentence, etymology) VALUES (?, ?, ?, ?)',
                     (word, definition, example_sentence, etymology))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('add_manual.html')

# 在 app.py 中找到 lookup 函式並替換
@app.route('/lookup', methods=['POST'])
def lookup():
    query = request.form['word']

    if contains_chinese(query):
        ai_suggestions = get_english_suggestions_from_chinese(query)
        return render_template('suggestion_list.html',
                               query=query,
                               suggestions=ai_suggestions.get('suggestions'),
                               error=ai_suggestions.get('error'))
    else:
        ai_result = get_word_info(query)
        # --- START: 升級的部分 ---
        # 除了基本資訊，我們現在還把 'related_words' 列表也傳給前端
        return render_template('confirm_add.html', 
                               word=query,
                               definition=ai_result.get('definition', '解析失敗'),
                               example_sentence=ai_result.get('example', '解析失敗'),
                               etymology=ai_result.get('etymology', '解析失敗'),
                               related_words=ai_result.get('related_words', [])) # <-- 新增這一行！
        # --- END: 升級的部分 ---

@app.route('/save', methods=['POST'])
def save():
    word = request.form['word']
    definition = request.form['definition']
    example_sentence = request.form['example_sentence']
    etymology = request.form['etymology']
    conn = get_db_connection()
    conn.execute('INSERT INTO words (word, definition, example_sentence, etymology) VALUES (?, ?, ?, ?)',
                 (word, definition, example_sentence, etymology))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# --- 傳統複習流程 (頁面跳轉) ---
@app.route('/review/sentence')
def review_sentence():
    conn = get_db_connection()
    word = conn.execute('SELECT * FROM words ORDER BY RANDOM() LIMIT 1').fetchone()
    conn.close()
    if word is None:
        return redirect(url_for('add_choice'))
    return render_template('review_sentence.html', word=word)

@app.route('/check/sentence', methods=['POST'])
def check_sentence():
    word = request.form['word']
    user_sentence = request.form['user_sentence']
    ai_feedback = get_sentence_feedback(word, user_sentence)
    return render_template('result_sentence.html',
                           user_sentence=user_sentence,
                           ai_feedback=ai_feedback)

# --- 全新改造的無刷新 (AJAX) 複習流程 ---
@app.route('/review')
def review_choice():
    return render_template('review_choice.html')

@app.route('/review/cloze')
def review_cloze():
    # 這個頁面現在只是一個空殼，所有內容都由 JavaScript 載入
    return render_template('review.html')

# API 1: 取得下一個要複習的單字
@app.route('/api/review/next_word')
def api_next_word():
    conn = get_db_connection()
    weakest_words = conn.execute('SELECT * FROM words ORDER BY review_count ASC, (CAST(correct_count AS REAL) / CASE WHEN review_count = 0 THEN 1 ELSE review_count END) ASC, last_reviewed ASC LIMIT 10').fetchall()
    conn.close()
    if not weakest_words:
        return jsonify({'error': 'No words to review'}), 404
    word_to_review = random.choice(weakest_words)
    # 將資料庫的 Row 物件轉換成 Python 的字典 dict，才能用 jsonify
    return jsonify(dict(word_to_review))

# API 2: 檢查答案並回傳結果
@app.route('/api/check/cloze', methods=['POST'])
def api_check_cloze():
    data = request.json
    user_guess = data.get('guess')
    word_id = data.get('word_id')
    conn = get_db_connection()
    correct_word = conn.execute('SELECT * FROM words WHERE id = ?', (word_id,)).fetchone()
    is_correct = user_guess.lower() == correct_word['word'].lower()
    explanation = None
    if not is_correct:
        sentence_context = correct_word['example_sentence'].replace(correct_word['word'], '_______') if correct_word['example_sentence'] else ""
        explanation = get_wrong_answer_explanation(
            word=correct_word['word'],
            definition=correct_word['definition'],
            user_guess=user_guess,
            sentence=sentence_context
        )
    new_review_count = correct_word['review_count'] + 1
    new_correct_count = correct_word['correct_count']
    if is_correct:
        new_correct_count += 1
    conn.execute('UPDATE words SET review_count = ?, correct_count = ?, last_reviewed = CURRENT_TIMESTAMP WHERE id = ?', (new_review_count, new_correct_count, word_id))
    conn.commit()
    conn.close()
    return jsonify({
        'is_correct': is_correct,
        'correct_word': dict(correct_word),
        'user_guess': user_guess,
        'explanation': explanation
    })

# --- 管理功能路由 ---
@app.route('/edit/<int:id>', methods=('GET', 'POST'))
def edit_word(id):
    conn = get_db_connection()
    word = conn.execute('SELECT * FROM words WHERE id = ?', (id,)).fetchone()
    if request.method == 'POST':
        new_word = request.form['word']
        new_definition = request.form['definition']
        new_example = request.form['example_sentence']
        new_etymology = request.form['etymology']
        conn.execute('UPDATE words SET word = ?, definition = ?, example_sentence = ?, etymology = ? WHERE id = ?',
                     (new_word, new_definition, new_example, new_etymology, id))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    conn.close()
    return render_template('edit_word.html', word=word)

@app.route('/delete/<int:id>', methods=['POST'])
def delete_word(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM words WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/admin/sql', methods=('GET', 'POST'))
def admin_sql():
    message = None
    if request.method == 'POST':
        sql_script = request.form['sql_script']
        conn = get_db_connection()
        try:
            conn.executescript(sql_script)
            conn.commit()
            message = "指令碼執行成功！"
        except Exception as e:
            message = f"發生錯誤: {e}"
        finally:
            conn.close()
    return render_template('admin_sql.html', message=message)

# 在 app.py 中加入這兩個新路由

@app.route('/review/multi_cloze')
def review_multi_cloze():
    conn = get_db_connection()
    # 從最弱的 20 個單字中，隨機挑選 3 到 5 個
    weakest_words_rows = conn.execute('SELECT * FROM words ORDER BY review_count ASC, (CAST(correct_count AS REAL) / CASE WHEN review_count = 0 THEN 1 ELSE review_count END) ASC, last_reviewed ASC LIMIT 20').fetchall()
    conn.close()

    if len(weakest_words_rows) < 3:
        # 如果單字少於3個，就無法出題
        return redirect(url_for('review_choice')) # 或導向一個提示頁面

    # 隨機決定這次要考幾個單字 (3到5個)
    num_to_pick = random.randint(3, min(5, len(weakest_words_rows)))
    words_to_use_rows = random.sample(weakest_words_rows, num_to_pick)

    # 提取單字字串列表
    correct_words = [row['word'] for row in words_to_use_rows]

    # 呼叫 AI 來生成故事
    ai_response = generate_multi_word_cloze(correct_words)
    story = ai_response.get('story', 'AI 故事生成失敗，請稍後再試。')

    # 產生被打亂順序的單字庫，供使用者參考
    shuffled_words = random.sample(correct_words, len(correct_words))

    # 將故事中的單字替換成輸入框
    story_with_blanks = story
    for i, word in enumerate(correct_words):
        # 這裡我們用一個特殊的標記來替換，以避免單字本身包含在其他單字中
        input_field = f'<input type="text" name="guess_{i}" style="width: 150px; display: inline-block;">'
        # 使用 re.sub 來確保只替換完整的單字
        story_with_blanks = re.sub(r'\b' + re.escape(word) + r'\b', input_field, story_with_blanks, count=1, flags=re.IGNORECASE)

    return render_template('review_multi_cloze.html',
                           story_with_blanks=story_with_blanks,
                           shuffled_words=shuffled_words,
                           correct_words_json=json.dumps(correct_words)) # 將正確答案順序傳給前端

@app.route('/check/multi_cloze', methods=['POST'])
def check_multi_cloze():
    user_guesses = request.form
    correct_words = json.loads(request.form['correct_words_json'])
    total = len(correct_words)
    score = 0

    result_story = "" # 我們要重新建立一個顯示結果的故事

    # 取得 AI 原始故事 (這一步可以優化，例如也用 hidden input 傳遞)
    # 為了簡化，我們先重新生成一次
    ai_response = generate_multi_word_cloze(correct_words)
    story = ai_response.get('story', '')

    # 逐一比對答案並建立結果故事
    temp_story = story
    for i, correct_word in enumerate(correct_words):
        user_answer = user_guesses.get(f'guess_{i}', '').strip()

        replacement = ""
        if user_answer.lower() == correct_word.lower():
            score += 1
            replacement = f'<strong style="color:green">{correct_word}</strong>'
        else:
            replacement = f'(<span style="color:red; text-decoration: line-through;">{user_answer or "未作答"}</span> <strong style="color:green">{correct_word}</strong>)'

        # 替換故事中的單字
        temp_story = re.sub(r'\b' + re.escape(correct_word) + r'\b', replacement, temp_story, count=1, flags=re.IGNORECASE)

    result_story = temp_story

    return render_template('result_multi_cloze.html',
                           score=score,
                           total=total,
                           result_story=result_story)

# --- 程式主入口 ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')