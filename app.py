# app.py (V.Final - 知識圖譜版)
import os
import sqlite3
import random
import json
import re
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv


load_dotenv()
from a_gemini_tool import (
    get_word_info, 
    get_sentence_feedback, 
    get_wrong_answer_explanation, 
    get_english_suggestions_from_chinese,
    generate_multi_word_cloze
)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "a-default-secret-key-for-development")

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

def get_db_connection():
    conn = sqlite3.connect('vocabulary.db')
    conn.row_factory = sqlite3.Row
    return conn

class User(UserMixin):
    def __init__(self, id, username, password, google_id=None):
        self.id, self.username, self.password, self.google_id = id, username, password, google_id

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user_row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user_row:
        return User(id=user_row['id'], username=user_row['username'], password=user_row['password'], google_id=user_row['google_id'])
    return None

def contains_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

@app.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
            conn.commit()
        except sqlite3.IntegrityError:
            flash("這個使用者名稱已經被註冊了！", "error")
            return render_template('register.html')
        finally: conn.close()
        flash("註冊成功，請登入！", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        conn = get_db_connection()
        user_row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user_row and bcrypt.check_password_hash(user_row['password'], password):
            user = User(id=user_row['id'], username=user_row['username'], password=user_row['password'])
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash("使用者名稱或密碼錯誤！", "error")
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/login/google')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/callback/google')
def google_callback():
    token = google.authorize_access_token()
    user_info = google.userinfo()
    google_id = user_info['sub']
    conn = get_db_connection()
    user_row = conn.execute('SELECT * FROM users WHERE google_id = ?', (google_id,)).fetchone()
    if not user_row:
        new_username = user_info.get('name', f"user_{random.randint(1000,9999)}")
        while conn.execute('SELECT * FROM users WHERE username = ?', (new_username,)).fetchone(): new_username = f"{new_username}_{random.randint(100,999)}"
        dummy_password = bcrypt.generate_password_hash('!@#$disabled-password-for-oauth$#@!').decode('utf-8')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (username, password, google_id) VALUES (?, ?, ?)', (new_username, dummy_password, google_id))
        conn.commit()
        user_row = conn.execute('SELECT * FROM users WHERE google_id = ?', (google_id,)).fetchone()
    user = User(id=user_row['id'], username=user_row['username'], password=user_row['password'], google_id=user_row['google_id'])
    conn.close()
    login_user(user)
    return redirect(url_for('index'))

@app.route('/')
@login_required
def index():
    query = request.args.get('query')
    conn = get_db_connection()
    base_query = """
        SELECT w.id, w.word, w.definition, w.example_sentence, 
               COALESCE(ud.review_count, 0) as review_count, 
               COALESCE(ud.correct_count, 0) as correct_count
        FROM words w
        JOIN word_user_data ud ON w.id = ud.word_id
        WHERE ud.user_id = ?
    """
    params = [current_user.id]
    if query:
        search_term = f"%{query}%"
        base_query += " AND (w.word LIKE ? OR w.definition LIKE ?)"
        params.extend([search_term, search_term])
    base_query += " ORDER BY ud.last_reviewed DESC, w.id DESC"
    words = conn.execute(base_query, tuple(params)).fetchall()
    conn.close()
    return render_template('index.html', words=words, query=query)

def add_word_to_user_list(word_id):
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO word_user_data (user_id, word_id) VALUES (?, ?)', (current_user.id, word_id))
        conn.commit()
        flash(f"成功將單字加入你的列表！", "success")
    except sqlite3.IntegrityError:
        flash("這個單字已經在你的列表中了。", "info")
    finally:
        conn.close()

@app.route('/add')
@login_required
def add_choice(): return render_template('add_choice.html')

@app.route('/add/smart')
@login_required
def add_smart(): return render_template('add_smart.html')

@app.route('/add/manual', methods=('GET', 'POST'))
@login_required
def add_manual():
    if request.method == 'POST':
        word_str, definition, example = request.form['word'], request.form['definition'], request.form['example_sentence']
        conn = get_db_connection()
        word_row = conn.execute('SELECT id FROM words WHERE word = ?', (word_str,)).fetchone()
        if not word_row:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO words (word, definition, example_sentence) VALUES (?, ?, ?)', (word_str, definition, example))
            word_id = cursor.lastrowid
        else:
            word_id = word_row['id']
        conn.close()
        add_word_to_user_list(word_id)
        return redirect(url_for('index'))
    return render_template('add_manual.html')

# 在 app.py 中找到 lookup 函式並替換

# 在 app.py 中找到 lookup 函式並替換

# 在 app.py 中找到 lookup 函式並替換

# 在 app.py 中找到 lookup 函式並替換

@app.route('/lookup', methods=['POST'])
@login_required
def lookup():
    query = request.form['word'].strip().lower()
    if not query:
        return redirect(url_for('add_smart'))

    if contains_chinese(query):
        ai_suggestions = get_english_suggestions_from_chinese(query)
        return render_template('suggestion_list.html',
                               query=query,
                               suggestions=ai_suggestions.get('suggestions'),
                               error=ai_suggestions.get('error'))
    else:
        conn = get_db_connection()
        word_from_db = conn.execute('SELECT * FROM words WHERE LOWER(word) = ?', (query,)).fetchone()

        ai_result = {}
        if word_from_db:
            print(f"--- 本地字典命中: {query} ---")
            ai_result = dict(word_from_db)
            word_id = ai_result['id']

            # --- START: 全新的完整關聯查詢邏輯 ---
            synonyms = conn.execute('SELECT w.word, w.definition FROM words w JOIN synonyms s ON w.id = s.word2_id WHERE s.word1_id = ?', (word_id,)).fetchall()
            antonyms = conn.execute('SELECT w.word, w.definition FROM words w JOIN antonyms a ON w.id = a.word2_id WHERE a.word1_id = ?', (word_id,)).fetchall()

            prefixes = conn.execute('SELECT p.prefix, p.meaning FROM prefixes p JOIN word_prefixes wp ON p.id = wp.prefix_id WHERE wp.word_id = ?', (word_id,)).fetchall()
            roots = conn.execute('SELECT r.root, r.meaning FROM roots r JOIN word_roots wr ON r.id = wr.root_id WHERE wr.word_id = ?', (word_id,)).fetchall()
            suffixes = conn.execute('SELECT s.suffix, s.meaning FROM suffixes s JOIN word_suffixes ws ON s.id = ws.suffix_id WHERE ws.word_id = ?', (word_id,)).fetchall()

            related_words = []
            for s in synonyms: related_words.append({'word': s['word'], 'hint': f"(同義詞) {s['definition']}"})
            for a in antonyms: related_words.append({'word': a['word'], 'hint': f"(反義詞) {a['definition']}"})
            ai_result['related_words'] = related_words

            etymology_parts = []
            for p in prefixes: etymology_parts.append(f"字首: {p['prefix']} ({p['meaning']})")
            for r in roots: etymology_parts.append(f"字根: {r['root']} ({r['meaning']})")
            for s in suffixes: etymology_parts.append(f"字尾: {s['suffix']} ({s['meaning']})")
            ai_result['etymology'] = ' + '.join(etymology_parts) if etymology_parts else "無明確詞源結構"
            # --- END: 全新的完整關聯查詢邏輯 ---

        else:
            print(f"--- 本地字典未命中: {query}，正在呼叫 AI... ---")
            ai_result = get_word_info(query)
            # (後面將 AI 結果存入資料庫的邏輯，會在我們的大量匯入完成後再優化)

        conn.close()

        return render_template('confirm_add.html', 
                               word=query,
                               definition=ai_result.get('definition', '解析失敗'),
                               example_sentence=ai_result.get('example_sentence', '解析失敗'),
                               etymology=ai_result.get('etymology', '解析失敗'),
                               related_words=ai_result.get('related_words', []))
    
@app.route('/api/save', methods=['POST'])
@login_required
def api_save():
    data = request.json
    word_str = data.get('word')
    definition = data.get('definition')
    example_sentence = data.get('example_sentence')
    etymology = data.get('etymology') # 雖然我們新資料庫沒用，但先接收

    conn = get_db_connection()

    # 1. 檢查單字是否已在公共字典中，若無則新增
    word_row = conn.execute('SELECT id FROM words WHERE word = ?', (word_str,)).fetchone()
    if not word_row:
        cursor = conn.cursor()
        # 注意：我們的 words 表已簡化，不再儲存 etymology
        cursor.execute('INSERT INTO words (word, definition, example_sentence) VALUES (?, ?, ?)',
                     (word_str, definition, example_sentence))
        word_id = cursor.lastrowid
        conn.commit() # *** 修正點 1：立刻儲存對公共字典的修改 ***
    else:
        word_id = word_row['id']

    # 2. 將單字與使用者的關聯寫入 word_user_data
    try:
        conn.execute('INSERT INTO word_user_data (user_id, word_id) VALUES (?, ?)',
                     (current_user.id, word_id))
        conn.commit() # *** 修正點 2：再次儲存對個人筆記的修改 ***
        return jsonify({'status': 'success', 'message': f"單字 '{word_str}' 已成功加入你的個人列表！"})
    except sqlite3.IntegrityError:
        return jsonify({'status': 'info', 'message': f"單字 '{word_str}' 已經在你的列表中了！"})
    finally:
        conn.close()

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_word(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM word_user_data WHERE word_id = ? AND user_id = ?', (id, current_user.id))
    conn.commit()
    conn.close()
    flash("成功從你的列表中移除單字。", "success")
    return redirect(url_for('index'))
    
@app.route('/edit/<int:id>', methods=('GET', 'POST'))
@login_required
def edit_word(id):
    flash("編輯公共字典的功能是一個複雜的管理權限議題，暫時禁用。", "info")
    return redirect(url_for('index'))

@app.route('/review')
@login_required
def review_choice(): return render_template('review_choice.html')

@app.route('/review/cloze')
@login_required
def review_cloze(): return render_template('review.html')

@app.route('/api/review/next_word')
@login_required
def api_next_word():
    conn = get_db_connection()
    weakest_words = conn.execute('''
        SELECT w.id, w.word, w.definition, w.example_sentence FROM words w
        JOIN word_user_data ud ON w.id = ud.word_id WHERE ud.user_id = ?
        ORDER BY ud.review_count ASC, (CAST(ud.correct_count AS REAL) / CASE WHEN ud.review_count = 0 THEN 1 ELSE ud.review_count END) ASC, ud.last_reviewed ASC 
        LIMIT 10
    ''', (current_user.id,)).fetchall()
    conn.close()
    if not weakest_words: return jsonify({'error': '你的單字書是空的，無法進行此測驗！'}), 404
    word_to_review = random.choice(weakest_words)
    return jsonify(dict(word_to_review))

@app.route('/api/check/cloze', methods=['POST'])
@login_required
def api_check_cloze():
    data = request.json
    user_guess, word_id = data.get('guess'), data.get('word_id')
    conn = get_db_connection()
    word_info = conn.execute('SELECT * FROM words WHERE id = ?', (word_id,)).fetchone()
    user_progress = conn.execute('SELECT * FROM word_user_data WHERE word_id = ? AND user_id = ?', (word_id, current_user.id)).fetchone()
    if not user_progress: return jsonify({'error': '找不到單字或該單字不在你的列表中'}), 403
    is_correct = user_guess.lower() == word_info['word'].lower()
    new_review_count, new_correct_count = user_progress['review_count'] + 1, user_progress['correct_count']
    if is_correct: new_correct_count += 1
    conn.execute('UPDATE word_user_data SET review_count = ?, correct_count = ?, last_reviewed = CURRENT_TIMESTAMP WHERE word_id = ? AND user_id = ?',
                 (new_review_count, new_correct_count, word_id, current_user.id))
    conn.commit()
    explanation = None
    if not is_correct:
        explanation = get_wrong_answer_explanation(word=word_info['word'], definition=word_info['definition'], user_guess=user_guess, sentence=word_info['example_sentence'])
    conn.close()
    return jsonify({'is_correct': is_correct, 'correct_word': dict(word_info), 'user_guess': user_guess, 'explanation': explanation})

@app.route('/review/sentence')
@login_required
def review_sentence():
    conn = get_db_connection()
    word = conn.execute('''
        SELECT w.* FROM words w JOIN word_user_data ud ON w.id = ud.word_id 
        WHERE ud.user_id = ? ORDER BY RANDOM() LIMIT 1
    ''', (current_user.id,)).fetchone()
    conn.close()
    if word is None: 
        flash("你的單字書是空的，無法進行造句練習！", "info")
        return redirect(url_for('add_choice'))
    return render_template('review_sentence.html', word=word)

@app.route('/check/sentence', methods=['POST'])
@login_required
def check_sentence():
    word, user_sentence = request.form['word'], request.form['user_sentence']
    ai_feedback = get_sentence_feedback(word, user_sentence)
    return render_template('result_sentence.html', user_sentence=user_sentence, ai_feedback=ai_feedback)

@app.route('/review/multi_cloze')
@login_required
def review_multi_cloze():
    conn = get_db_connection()
    weakest_words_rows = conn.execute('''
        SELECT w.word FROM words w JOIN word_user_data ud ON w.id = ud.word_id 
        WHERE ud.user_id = ? 
        ORDER BY ud.review_count ASC, (CAST(ud.correct_count AS REAL) / CASE WHEN ud.review_count = 0 THEN 1 ELSE ud.review_count END) ASC, ud.last_reviewed ASC 
        LIMIT 20
    ''', (current_user.id,)).fetchall()
    
    if len(weakest_words_rows) < 3:
        flash("你的單字少於3個，無法進行綜合測驗！", "info")
        return redirect(url_for('review_choice'))
        
    num_to_pick = random.randint(3, min(5, len(weakest_words_rows)))
    words_to_use_rows = random.sample(weakest_words_rows, num_to_pick)
    correct_words = [row['word'] for row in words_to_use_rows]
    ai_response = generate_multi_word_cloze(correct_words)
    story = ai_response.get('story', 'AI 故事生成失敗，請稍後再試。')
    shuffled_words = random.sample(correct_words, len(correct_words))
    story_with_blanks = story
    for i, word in enumerate(correct_words):
        input_field = f'<input type="text" name="guess_{i}" style="width: 150px; display: inline-block;">'
        story_with_blanks = re.sub(r'\b' + re.escape(word) + r'\b', input_field, story_with_blanks, count=1, flags=re.IGNORECASE)
    conn.close()
    return render_template('review_multi_cloze.html', story_with_blanks=story_with_blanks, shuffled_words=shuffled_words, correct_words_json=json.dumps(correct_words))

@app.route('/check/multi_cloze', methods=['POST'])
@login_required
def check_multi_cloze():
    user_guesses = request.form
    correct_words = json.loads(request.form['correct_words_json'])
    ai_response = generate_multi_word_cloze(correct_words)
    story = ai_response.get('story', '')
    temp_story, score = story, 0
    for i, correct_word in enumerate(correct_words):
        user_answer = user_guesses.get(f'guess_{i}', '').strip()
        replacement = ""
        if user_answer.lower() == correct_word.lower():
            score += 1
            replacement = f'<strong style="color:green">{correct_word}</strong>'
        else:
            replacement = f'(<span style="color:red; text-decoration: line-through;">{user_answer or "未作答"}</span> <strong style="color:green">{correct_word}</strong>)'
        temp_story = re.sub(r'\b' + re.escape(correct_word) + r'\b', replacement, temp_story, count=1, flags=re.IGNORECASE)
    return render_template('result_multi_cloze.html', score=score, total=len(correct_words), result_story=temp_story)
    
@app.route('/admin/sql', methods=('GET', 'POST'))
@login_required
def admin_sql():
    flash("在新架構下，批次匯入是更複雜的管理員功能，暫時禁用。", "info")
    return redirect(url_for('index'))

# 在 app.py 中加入這兩個新路由

# 路由 1: 顯示單字詳情頁
@app.route('/word/<int:word_id>')
@login_required
def word_detail(word_id):
    conn = get_db_connection()
    # 查詢單字基本資訊
    word = conn.execute('SELECT * FROM words WHERE id = ?', (word_id,)).fetchone()

    # 查詢所有關聯資訊
    synonyms = conn.execute('SELECT w.* FROM words w JOIN synonyms s ON w.id = s.word2_id WHERE s.word1_id = ?', (word_id,)).fetchall()
    antonyms = conn.execute('SELECT w.* FROM words w JOIN antonyms a ON w.id = a.word2_id WHERE a.word1_id = ?', (word_id,)).fetchall()
    prefixes = conn.execute('SELECT p.* FROM prefixes p JOIN word_prefixes wp ON p.id = wp.prefix_id WHERE wp.word_id = ?', (word_id,)).fetchall()
    roots = conn.execute('SELECT r.* FROM roots r JOIN word_roots wr ON r.id = wr.root_id WHERE wr.word_id = ?', (word_id,)).fetchall()
    suffixes = conn.execute('SELECT s.* FROM suffixes s JOIN word_suffixes ws ON s.id = ws.suffix_id WHERE ws.word_id = ?', (word_id,)).fetchall()

    conn.close()

    return render_template('word_detail.html', 
                           word=word, 
                           synonyms=synonyms, 
                           antonyms=antonyms,
                           prefixes=prefixes,
                           roots=roots,
                           suffixes=suffixes)

# 路由 2: 顯示字根/字首/字尾的關聯單字列表
@app.route('/explore/<affix_type>/<int:affix_id>')
@login_required
def explore_by_affix(affix_type, affix_id):
    conn = get_db_connection()
    affix = None
    words = []
    affix_type_display = ""

    # 根據不同的類型，查詢不同的關聯表
    if affix_type == 'prefix':
        affix_type_display = "字首"
        affix = conn.execute('SELECT * FROM prefixes WHERE id = ?', (affix_id,)).fetchone()
        words = conn.execute('''
            SELECT w.* FROM words w
            JOIN word_prefixes wp ON w.id = wp.word_id
            JOIN word_user_data ud ON w.id = ud.word_id
            WHERE wp.prefix_id = ? AND ud.user_id = ?
        ''', (affix_id, current_user.id)).fetchall()
    elif affix_type == 'root':
        affix_type_display = "字根"
        affix = conn.execute('SELECT * FROM roots WHERE id = ?', (affix_id,)).fetchone()
        words = conn.execute('''
            SELECT w.* FROM words w
            JOIN word_roots wr ON w.id = wr.word_id
            JOIN word_user_data ud ON w.id = ud.word_id
            WHERE wr.root_id = ? AND ud.user_id = ?
        ''', (affix_id, current_user.id)).fetchall()
    elif affix_type == 'suffix':
        affix_type_display = "字尾"
        affix = conn.execute('SELECT * FROM suffixes WHERE id = ?', (affix_id,)).fetchone()
        words = conn.execute('''
            SELECT w.* FROM words w
            JOIN word_suffixes ws ON w.id = ws.word_id
            JOIN word_user_data ud ON w.id = ud.word_id
            WHERE ws.suffix_id = ? AND ud.user_id = ?
        ''', (affix_id, current_user.id)).fetchall()

    conn.close()

    return render_template('explore_by_affix.html', 
                           affix=affix, 
                           words=words, 
                           affix_type_display=affix_type_display)

@app.route('/save', methods=['POST'])
@login_required
def save():
    conn = get_db_connection()
    try:
        # 從表單接收所有 AI 提供的資料
        word_str = request.form['word']
        definition = request.form['definition']
        example = request.form['example_sentence']
        etymology_json = request.form.get('etymology_json', '{}')
        synonyms_json = request.form.get('synonyms_json', '[]')
        antonyms_json = request.form.get('antonyms_json', '[]')

        etymology = json.loads(etymology_json)
        synonyms = json.loads(synonyms_json)
        antonyms = json.loads(antonyms_json)

        # --- 開始資料庫交易 ---
        cursor = conn.cursor()

        # 1. 新增或取得主要單字 ID
        cursor.execute("INSERT OR IGNORE INTO words (word, definition, example_sentence) VALUES (?, ?, ?)", (word_str, definition, example))
        word_id = cursor.execute('SELECT id FROM words WHERE word = ?', (word_str,)).fetchone()['id']

        # 2. 處理並連結詞源
        for p_data in etymology.get('prefixes', []):
            cursor.execute("INSERT OR IGNORE INTO prefixes (prefix, meaning) VALUES (?, ?)", (p_data['prefix'], p_data['meaning']))
            prefix_id = cursor.execute('SELECT id FROM prefixes WHERE prefix = ?', (p_data['prefix'],)).fetchone()['id']
            cursor.execute("INSERT OR IGNORE INTO word_prefixes (word_id, prefix_id) VALUES (?, ?)", (word_id, prefix_id))

        for r_data in etymology.get('roots', []):
            cursor.execute("INSERT OR IGNORE INTO roots (root, meaning) VALUES (?, ?)", (r_data['root'], r_data['meaning']))
            root_id = cursor.execute('SELECT id FROM roots WHERE root = ?', (r_data['root'],)).fetchone()['id']
            cursor.execute("INSERT OR IGNORE INTO word_roots (word_id, root_id) VALUES (?, ?)", (word_id, root_id))

        for s_data in etymology.get('suffixes', []):
            cursor.execute("INSERT OR IGNORE INTO suffixes (suffix, meaning) VALUES (?, ?)", (s_data['suffix'], s_data['meaning']))
            suffix_id = cursor.execute('SELECT id FROM suffixes WHERE suffix = ?', (s_data['suffix'],)).fetchone()['id']
            cursor.execute("INSERT OR IGNORE INTO word_suffixes (word_id, suffix_id) VALUES (?, ?)", (word_id, suffix_id))

        # 3. 處理並連結同義/反義詞
        for syn_word in synonyms:
            syn_row = cursor.execute('SELECT id FROM words WHERE word = ?', (syn_word,)).fetchone()
            if syn_row:
                syn_id = syn_row['id']
                cursor.execute("INSERT OR IGNORE INTO synonyms (word1_id, word2_id) VALUES (?, ?)", (word_id, syn_id))
                cursor.execute("INSERT OR IGNORE INTO synonyms (word1_id, word2_id) VALUES (?, ?)", (syn_id, word_id))

        for ant_word in antonyms:
            ant_row = cursor.execute('SELECT id FROM words WHERE word = ?', (ant_word,)).fetchone()
            if ant_row:
                ant_id = ant_row['id']
                cursor.execute("INSERT OR IGNORE INTO antonyms (word1_id, word2_id) VALUES (?, ?)", (word_id, ant_id))
                cursor.execute("INSERT OR IGNORE INTO antonyms (word1_id, word2_id) VALUES (?, ?)", (ant_id, word_id))

        # 4. 將單字加入使用者個人列表
        cursor.execute("INSERT OR IGNORE INTO word_user_data (user_id, word_id) VALUES (?, ?)", (current_user.id, word_id))

        conn.commit()
        flash(f"單字 '{word_str}' 已成功加入並建立關聯！", "success")

    except Exception as e:
        conn.rollback()
        flash(f"儲存時發生錯誤: {e}", "error")
    finally:
        conn.close()

    return redirect(url_for('add_smart'))

# 在 app.py 中加入這個新路由
@app.route('/level/<int:level_num>')
@login_required
def level_view(level_num):
    conn = get_db_connection()
    # 使用 LEFT JOIN 來找出所有第四級的單字，並標示出哪些已經在使用者列表中
    words = conn.execute('''
        SELECT w.*, ud.user_id 
        FROM words w
        LEFT JOIN word_user_data ud ON w.id = ud.word_id AND ud.user_id = ?
        WHERE w.level = ?
        ORDER BY w.word
    ''', (current_user.id, level_num)).fetchall()
    conn.close()
    return render_template('level_view.html', words=words, level_num=level_num)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')