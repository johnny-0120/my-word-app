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
from a_gemini_tool import get_word_info, get_sentence_feedback, get_wrong_answer_explanation, get_english_suggestions_from_chinese

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

@app.route('/')
@login_required
def index():
    query = request.args.get('query')
    conn = get_db_connection()
    base_query = """
        SELECT w.id, w.word, w.definition, w.example1, 
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
def add_choice(): return render_template('add_choice.html')

@app.route('/add/smart')
@login_required
def add_smart(): return render_template('add_smart.html')

@app.route('/add/manual')
@login_required
def add_manual():
    # 手動新增暫時使用智能查詢來簡化
    return redirect(url_for('add_smart'))

@app.route('/lookup', methods=['POST'])
@login_required
def lookup():
    query = request.form['word'].strip().lower()
    if not query: return redirect(url_for('add_smart'))
    
    ai_result = get_word_info(query)
    
    if ai_result.get("error"):
        flash(f"AI 查詢時發生錯誤: {ai_result['error']}", "error")
        return redirect(url_for('add_smart'))

    return render_template('confirm_add.html', data=ai_result)

@app.route('/save', methods=['POST'])
@login_required
def save():
    conn = get_db_connection()
    try:
        word_data_json = request.form.get('word_data_json', '{}')
        data = json.loads(word_data_json)
        word_str = data.get('word')

        if not word_str:
            raise ValueError("Word cannot be empty")

        cursor = conn.cursor()

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
        word_id = cursor.execute('SELECT id FROM words WHERE word = ?', (word_str,)).fetchone()['id']

        # 2. 處理並連結詞源
        etymology = data.get('etymology', {})
        for p_data in etymology.get('prefixes', []):
            cursor.execute("INSERT OR IGNORE INTO prefixes (prefix, meaning) VALUES (?, ?)", (p_data['part'], p_data['meaning']))
            prefix_id = cursor.execute('SELECT id FROM prefixes WHERE prefix = ?', (p_data['part'],)).fetchone()['id']
            cursor.execute("INSERT OR IGNORE INTO word_prefixes (word_id, prefix_id) VALUES (?, ?)", (word_id, prefix_id))
        
        for r_data in etymology.get('roots', []):
            cursor.execute("INSERT OR IGNORE INTO roots (root, meaning) VALUES (?, ?)", (r_data['part'], r_data['meaning']))
            root_id = cursor.execute('SELECT id FROM roots WHERE root = ?', (r_data['part'],)).fetchone()['id']
            cursor.execute("INSERT OR IGNORE INTO word_roots (word_id, root_id) VALUES (?, ?)", (word_id, root_id))

        for s_data in etymology.get('suffixes', []):
            cursor.execute("INSERT OR IGNORE INTO suffixes (suffix, meaning) VALUES (?, ?)", (s_data['part'], s_data['meaning']))
            suffix_id = cursor.execute('SELECT id FROM suffixes WHERE suffix = ?', (s_data['part'],)).fetchone()['id']
            cursor.execute("INSERT OR IGNORE INTO word_suffixes (word_id, suffix_id) VALUES (?, ?)", (word_id, suffix_id))

        # 3. 處理並連結同義/反義詞
        relations = data.get('relations', {})
        for syn_word in relations.get('synonyms', []):
            cursor.execute("INSERT OR IGNORE INTO words (word) VALUES (?)", (syn_word,))
            syn_id = cursor.execute('SELECT id FROM words WHERE word = ?', (syn_word,)).fetchone()['id']
            cursor.execute("INSERT OR IGNORE INTO synonyms (word1_id, word2_id) VALUES (?, ?)", (word_id, syn_id))
            cursor.execute("INSERT OR IGNORE INTO synonyms (word1_id, word2_id) VALUES (?, ?)", (syn_id, word_id))
        
        for ant_word in relations.get('antonyms', []):
            cursor.execute("INSERT OR IGNORE INTO words (word) VALUES (?)", (ant_word,))
            ant_id = cursor.execute('SELECT id FROM words WHERE word = ?', (ant_word,)).fetchone()['id']
            cursor.execute("INSERT OR IGNORE INTO antonyms (word1_id, word2_id) VALUES (?, ?)", (word_id, ant_id))
            cursor.execute("INSERT OR IGNORE INTO antonyms (word1_id, word2_id) VALUES (?, ?)", (ant_id, word_id))
        
        # 4. 將單字加入使用者個人列表
        cursor.execute("INSERT OR IGNORE INTO word_user_data (user_id, word_id) VALUES (?, ?)", (current_user.id, word_id))

        conn.commit()
        flash(f"單字 '{word_str}' 已成功儲存並加入列表！", "success")

    except Exception as e:
        conn.rollback()
        flash(f"儲存時發生嚴重錯誤: {e}", "error")
    finally:
        conn.close()
            
    return redirect(url_for('add_smart'))

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_word(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM word_user_data WHERE word_id = ? AND user_id = ?', (id, current_user.id))
    conn.commit()
    conn.close()
    flash("成功從你的列表中移除單字。", "success")
    return redirect(url_for('index'))
    
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_word(id):
    flash("編輯公共字典的功能是一個複雜的管理權限議題，暫時禁用。", "info")
    return redirect(url_for('index'))

@app.route('/level/<int:level_num>')
@login_required
def level_view(level_num):
    conn = get_db_connection()
    words = conn.execute('''
        SELECT w.*, ud.user_id 
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
    word = conn.execute('SELECT * FROM words WHERE id = ?', (word_id,)).fetchone()
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')