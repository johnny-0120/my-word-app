# app.py (V.Final - 修復完整版)
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
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "a-super-secret-key-that-no-one-can-guess")

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Google OAuth 設定 ---
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

# --- 身份認證路由 (不變) ---
@app.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        if not username or not password:
            flash("使用者名稱和密碼為必填項。", "error")
            return render_template('register.html')
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
            conn.commit()
            flash("註冊成功，請登入！", "success")
        except sqlite3.IntegrityError:
            flash("這個使用者名稱已經被註冊了！", "error")
            return render_template('register.html')
        finally: 
            conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        conn = get_db_connection()
        user_row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user_row and user_row['password'] and bcrypt.check_password_hash(user_row['password'], password):
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
        while conn.execute('SELECT * FROM users WHERE username = ?', (new_username,)).fetchone(): 
            new_username = f"{new_username}_{random.randint(100,999)}"
        dummy_password = bcrypt.generate_password_hash('!@#$disabled-password-for-oauth$#@!').decode('utf-8')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (username, password, google_id) VALUES (?, ?, ?)', (new_username, dummy_password, google_id))
        conn.commit()
        user_row = conn.execute('SELECT * FROM users WHERE google_id = ?', (google_id,)).fetchone()
    
    user = User(id=user_row['id'], username=user_row['username'], password=user_row['password'], google_id=user_row['google_id'])
    conn.close()
    login_user(user)
    return redirect(url_for('index'))

# --- 核心功能路由 ---
@app.route('/')
@login_required
def index():
    query = request.args.get('query')
    conn = get_db_connection()
    # 注意這裡將 example1 映射為 example_sentence 供前端使用
    base_query = """
        SELECT w.*, w.example1 AS example_sentence,
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

@app.route('/add_to_my_list/<int:word_id>', methods=['POST'])
@login_required
def add_to_my_list(word_id):
    conn = get_db_connection()
    try:
        conn.execute('INSERT OR IGNORE INTO word_user_data (user_id, word_id) VALUES (?, ?)', (current_user.id, word_id))
        conn.commit()
        flash("成功將單字加入你的列表！", "success")
    except sqlite3.IntegrityError:
        flash("這個單字已經在你的列表中了。", "info")
    finally:
        conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/add')
@login_required
def add_choice(): 
    return render_template('add_choice.html')

@app.route('/add/smart')
@login_required
def add_smart(): 
    return render_template('add_smart.html')

# 補上漏掉的手動新增路由
@app.route('/add/manual', methods=['GET', 'POST'])
@login_required
def add_manual():
    if request.method == 'POST':
        conn = get_db_connection()
        try:
            word_str = request.form['word']
            definition = request.form['definition']
            example_sentence = request.form.get('example_sentence', '')
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO words (word, definition, example1) 
                VALUES (?, ?, ?)
                ON CONFLICT(word) DO NOTHING
            """, (word_str, definition, example_sentence))
            
            word_id_row = cursor.execute('SELECT id FROM words WHERE word = ?', (word_str,)).fetchone()
            if word_id_row:
                cursor.execute("INSERT OR IGNORE INTO word_user_data (user_id, word_id) VALUES (?, ?)", (current_user.id, word_id_row['id']))
                conn.commit()
                flash(f"單字 '{word_str}' 已成功手動儲存並加入列表！", "success")
            else:
                flash("新增失敗，可能發生預期外的錯誤。", "error")
        except Exception as e:
            conn.rollback()
            flash(f"儲存時發生錯誤: {e}", "error")
        finally:
            conn.close()
        return redirect(url_for('index'))
    return render_template('add_manual.html')

@app.route('/lookup', methods=['POST'])
@login_required
def lookup():
    query = request.form['word'].strip()
    if not query: return redirect(url_for('add_smart'))
    
    if contains_chinese(query):
        # 處理中文建議
        ai_result = get_english_suggestions_from_chinese(query)
        if "error" in ai_result:
            flash(ai_result['error'], "error")
            return redirect(url_for('add_smart'))
        return render_template('suggestion_list.html', suggestions=ai_result.get('suggestions', []), query=query)
    else:
        # 處理英文查詢
        query = query.lower()
        ai_result = get_word_info(query)
        if "error" in ai_result:
            flash(f"AI 查詢時發生錯誤: {ai_result['error']}", "error")
            return redirect(url_for('add_smart'))

        # 對齊介面使用的欄位名稱 (example_sentence 對應 example1)
        return render_template('confirm_add.html', 
                               word=query,
                               definition=ai_result.get('definition', ''),
                               example_sentence=ai_result.get('example1', ''),
                               etymology=ai_result.get('etymology', {}),
                               synonyms=ai_result.get('relations', {}).get('synonyms', []),
                               antonyms=ai_result.get('relations', {}).get('antonyms', []),
                               data=ai_result)

@app.route('/save', methods=['POST'])
@login_required
def save():
    conn = get_db_connection()
    try:
        word_str = request.form.get('word')
        definition = request.form.get('definition')
        example_sentence = request.form.get('example_sentence')
        
        # 接收隱藏欄位中的 JSON
        etymology = json.loads(request.form.get('etymology_json', '{}'))
        synonyms = json.loads(request.form.get('synonyms_json', '[]'))
        antonyms = json.loads(request.form.get('antonyms_json', '[]'))

        if not word_str:
            raise ValueError("單字不得為空")

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO words (word, definition, example1) 
            VALUES (?, ?, ?)
            ON CONFLICT(word) DO NOTHING
        """, (word_str, definition, example_sentence))
        
        word_id = cursor.execute('SELECT id FROM words WHERE word = ?', (word_str,)).fetchone()['id']

        for p_data in etymology.get('prefixes', []):
            if 'part' in p_data and 'meaning' in p_data:
                cursor.execute("INSERT OR IGNORE INTO prefixes (prefix, meaning) VALUES (?, ?)", (p_data['part'], p_data['meaning']))
                prefix_id = cursor.execute('SELECT id FROM prefixes WHERE prefix = ?', (p_data['part'],)).fetchone()['id']
                cursor.execute("INSERT OR IGNORE INTO word_prefixes (word_id, prefix_id) VALUES (?, ?)", (word_id, prefix_id))
        
        for r_data in etymology.get('roots', []):
            if 'part' in r_data and 'meaning' in r_data:
                cursor.execute("INSERT OR IGNORE INTO roots (root, meaning) VALUES (?, ?)", (r_data['part'], r_data['meaning']))
                root_id = cursor.execute('SELECT id FROM roots WHERE root = ?', (r_data['part'],)).fetchone()['id']
                cursor.execute("INSERT OR IGNORE INTO word_roots (word_id, root_id) VALUES (?, ?)", (word_id, root_id))

        for s_data in etymology.get('suffixes', []):
            if 'part' in s_data and 'meaning' in s_data:
                cursor.execute("INSERT OR IGNORE INTO suffixes (suffix, meaning) VALUES (?, ?)", (s_data['part'], s_data['meaning']))
                suffix_id = cursor.execute('SELECT id FROM suffixes WHERE suffix = ?', (s_data['part'],)).fetchone()['id']
                cursor.execute("INSERT OR IGNORE INTO word_suffixes (word_id, suffix_id) VALUES (?, ?)", (word_id, suffix_id))

        for syn_word in synonyms:
            cursor.execute("INSERT OR IGNORE INTO words (word) VALUES (?)", (syn_word,))
            syn_id = cursor.execute('SELECT id FROM words WHERE word = ?', (syn_word,)).fetchone()['id']
            cursor.execute("INSERT OR IGNORE INTO synonyms (word1_id, word2_id) VALUES (?, ?)", (word_id, syn_id))
            cursor.execute("INSERT OR IGNORE INTO synonyms (word1_id, word2_id) VALUES (?, ?)", (syn_id, word_id))
        
        for ant_word in antonyms:
            cursor.execute("INSERT OR IGNORE INTO words (word) VALUES (?)", (ant_word,))
            ant_id = cursor.execute('SELECT id FROM words WHERE word = ?', (ant_word,)).fetchone()['id']
            cursor.execute("INSERT OR IGNORE INTO antonyms (word1_id, word2_id) VALUES (?, ?)", (word_id, ant_id))
            cursor.execute("INSERT OR IGNORE INTO antonyms (word1_id, word2_id) VALUES (?, ?)", (ant_id, word_id))
        
        cursor.execute("INSERT OR IGNORE INTO word_user_data (user_id, word_id) VALUES (?, ?)", (current_user.id, word_id))

        conn.commit()
        flash(f"單字 '{word_str}' 已成功儲存並加入列表！", "success")

    except Exception as e:
        conn.rollback()
        flash(f"儲存時發生嚴重錯誤: {e}", "error")
    finally:
        conn.close()
            
    return redirect(url_for('add_smart'))

@app.route('/delete/<int:word_id>', methods=['POST'])
@login_required
def delete_word(word_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM word_user_data WHERE word_id = ? AND user_id = ?', (word_id, current_user.id))
    conn.commit()
    conn.close()
    flash("成功從你的列表中移除單字。", "success")
    return redirect(url_for('index'))
    
@app.route('/edit/<int:word_id>', methods=('GET', 'POST'))
@login_required
def edit_word(word_id):
    flash("編輯公共字典的功能是一個複雜的管理權限議題，暫時禁用。", "info")
    return redirect(url_for('index'))

@app.route('/level/<int:level_num>')
@login_required
def level_view(level_num):
    conn = get_db_connection()
    words = conn.execute('''
        SELECT w.*, w.example1 AS example_sentence, ud.user_id 
        FROM words w
        LEFT JOIN word_user_data ud ON w.id = ud.word_id AND ud.user_id = ?
        WHERE w.level = ? ORDER BY w.word
    ''', (current_user.id, level_num)).fetchall()
    conn.close()
    return render_template('level_view.html', words=words, level_num=level_num)

@app.route('/word/<int:word_id>')
@login_required
def word_detail(word_id):
    conn = get_db_connection()
    word = conn.execute('SELECT *, example1 AS example_sentence FROM words WHERE id = ?', (word_id,)).fetchone()
    synonyms = conn.execute('SELECT w.* FROM words w JOIN synonyms s ON w.id = s.word2_id WHERE s.word1_id = ?', (word_id,)).fetchall()
    antonyms = conn.execute('SELECT w.* FROM words w JOIN antonyms a ON w.id = a.word2_id WHERE a.word1_id = ?', (word_id,)).fetchall()
    prefixes = conn.execute('SELECT p.* FROM prefixes p JOIN word_prefixes wp ON p.id = wp.prefix_id WHERE wp.word_id = ?', (word_id,)).fetchall()
    roots = conn.execute('SELECT r.* FROM roots r JOIN word_roots wr ON r.id = wr.root_id WHERE wr.word_id = ?', (word_id,)).fetchall()
    suffixes = conn.execute('SELECT s.* FROM suffixes s JOIN word_suffixes ws ON s.id = ws.suffix_id WHERE ws.word_id = ?', (word_id,)).fetchall()
    conn.close()
    return render_template('word_detail.html', word=word, synonyms=synonyms, antonyms=antonyms, prefixes=prefixes, roots=roots, suffixes=suffixes)

@app.route('/explore/<affix_type>/<int:affix_id>')
@login_required
def explore_by_affix(affix_type, affix_id):
    conn = get_db_connection()
    affix, words, affix_type_display = None, [], ""
    table_map = {
        'prefix': ('prefixes', 'word_prefixes', 'prefix_id', '字首'),
        'root': ('roots', 'word_roots', 'root_id', '字根'),
        'suffix': ('suffixes', 'word_suffixes', 'suffix_id', '字尾')
    }
    if affix_type in table_map:
        table, join_table, id_col, display = table_map[affix_type]
        affix_type_display = display
        affix = conn.execute(f'SELECT * FROM {table} WHERE id = ?', (affix_id,)).fetchone()
        words = conn.execute(f'''
            SELECT w.* FROM words w
            JOIN {join_table} jt ON w.id = jt.word_id
            JOIN word_user_data ud ON w.id = ud.word_id
            WHERE jt.{id_col} = ? AND ud.user_id = ?
        ''', (affix_id, current_user.id)).fetchall()
    conn.close()
    return render_template('explore_by_affix.html', affix=affix, words=words, affix_type_display=affix_type_display)


# ==========================================
# 補齊遺失的複習 (Review) 與 AI 測驗相關路由
# ==========================================

@app.route('/review_choice')
@login_required
def review_choice():
    return render_template('review_choice.html')

@app.route('/review/cloze')
@login_required
def review_cloze():
    return render_template('review.html')

@app.route('/api/review/next_word')
@login_required
def api_next_word():
    conn = get_db_connection()
    word = conn.execute('''
        SELECT w.*, w.example1 AS example_sentence FROM words w
        JOIN word_user_data ud ON w.id = ud.word_id
        WHERE ud.user_id = ?
        ORDER BY RANDOM() LIMIT 1
    ''', (current_user.id,)).fetchone()
    conn.close()
    if not word: return jsonify({"error": "No words in your list"}), 404
    return jsonify(dict(word))

@app.route('/api/check/cloze', methods=['POST'])
@login_required
def check_cloze_api():
    data = request.json
    word_id = data.get('word_id')
    guess = data.get('guess', '').strip().lower()
    
    conn = get_db_connection()
    word = conn.execute('SELECT *, example1 AS example_sentence FROM words WHERE id = ?', (word_id,)).fetchone()
    
    is_correct = (guess == word['word'].lower())
    
    cursor = conn.cursor()
    if is_correct:
        cursor.execute('UPDATE word_user_data SET review_count = review_count + 1, correct_count = correct_count + 1, last_reviewed = CURRENT_TIMESTAMP WHERE user_id = ? AND word_id = ?', (current_user.id, word_id))
    else:
        cursor.execute('UPDATE word_user_data SET review_count = review_count + 1, last_reviewed = CURRENT_TIMESTAMP WHERE user_id = ? AND word_id = ?', (current_user.id, word_id))
    conn.commit()
    conn.close()
    
    explanation = ""
    if not is_correct:
        explanation = get_wrong_answer_explanation(word['word'], word['definition'], guess, word['example_sentence'] or '')
    
    return jsonify({
        "is_correct": is_correct,
        "user_guess": guess,
        "correct_word": dict(word),
        "explanation": explanation
    })

@app.route('/review/sentence')
@login_required
def review_sentence():
    conn = get_db_connection()
    word = conn.execute('''
        SELECT w.* FROM words w
        JOIN word_user_data ud ON w.id = ud.word_id
        WHERE ud.user_id = ?
        ORDER BY RANDOM() LIMIT 1
    ''', (current_user.id,)).fetchone()
    conn.close()
    if not word:
        flash("請先將單字加入列表，才能使用造句測驗！", "warning")
        return redirect(url_for('index'))
    return render_template('review_sentence.html', word=word)

@app.route('/check_sentence', methods=['POST'])
@login_required
def check_sentence():
    word_str = request.form['word']
    user_sentence = request.form['user_sentence']
    ai_feedback = get_sentence_feedback(word_str, user_sentence)
    return render_template('result_sentence.html', user_sentence=user_sentence, ai_feedback=ai_feedback)

@app.route('/review/multi_cloze')
@login_required
def review_multi_cloze():
    conn = get_db_connection()
    words = conn.execute('''
        SELECT w.word FROM words w
        JOIN word_user_data ud ON w.id = ud.word_id
        WHERE ud.user_id = ?
        ORDER BY RANDOM() LIMIT 3
    ''', (current_user.id,)).fetchall()
    conn.close()
    
    if len(words) < 3:
        flash("單字量不足！請先將至少 3 個單字加入列表才能進行綜合測驗。", "warning")
        return redirect(url_for('review_choice'))
        
    word_list = [w['word'] for w in words]
    ai_data = generate_multi_word_cloze(word_list)
    
    if not ai_data or "error" in ai_data:
        flash("AI 產生測驗時發生錯誤，請稍後再試。", "error")
        return redirect(url_for('review_choice'))
        
    story = ai_data.get('story', '')
    story_with_blanks = story
    
    # 建立動態輸入框
    for idx, w in enumerate(word_list):
        pattern = re.compile(r'\b' + re.escape(w) + r'\b', re.IGNORECASE)
        story_with_blanks = pattern.sub(f'<input type="text" name="guess_{idx}" style="width: 120px; display: inline-block; padding: 2px; margin: 0 4px;" required>', story_with_blanks)

    shuffled_words = list(word_list)
    random.shuffle(shuffled_words)
    
    return render_template('review_multi_cloze.html', 
                           story_with_blanks=story_with_blanks, 
                           shuffled_words=shuffled_words, 
                           correct_words_json=json.dumps(word_list))

@app.route('/check_multi_cloze', methods=['POST'])
@login_required
def check_multi_cloze():
    correct_words = json.loads(request.form['correct_words_json'])
    score = 0
    total = len(correct_words)
    
    details = []
    for idx, correct_word in enumerate(correct_words):
        guess = request.form.get(f'guess_{idx}', '').strip().lower()
        if guess == correct_word.lower():
            score += 1
            details.append(f"<span style='color:green;'>{correct_word} (✅ 答對)</span>")
        else:
            details.append(f"<span style='color:red; text-decoration: line-through;'>{guess}</span> ➡️ <span style='color:green;'>{correct_word}</span>")
    
    result_story_html = "你的填寫結果對照：<br><br>" + "<br>".join([f"空格 {i+1}: {d}" for i, d in enumerate(details)])
    
    return render_template('result_multi_cloze.html', score=score, total=total, result_story=result_story_html)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')