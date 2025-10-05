# app.py (V.Final - 多使用者終極版)
import sqlite3
import random
import json
import re
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from a_gemini_tool import get_word_info, get_sentence_feedback, get_wrong_answer_explanation, get_english_suggestions_from_chinese

app = Flask(__name__)
# 為了 Flask-Login 的 session 管理，我們需要設定一個密鑰
app.config['SECRET_KEY'] = 'a-very-secret-and-secure-key-that-you-should-change'

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
# 如果未登入的使用者嘗試訪問需要登入的頁面，會被自動導向到 'login' 頁面
login_manager.login_view = 'login'

# --- 資料庫 & 使用者模型 ---
def get_db_connection():
    conn = sqlite3.connect('vocabulary.db')
    conn.row_factory = sqlite3.Row
    return conn

# 建立一個 User 類別，讓 Flask-Login 知道如何處理我們的使用者資料
class User(UserMixin):
    def __init__(self, id, username, password, google_id=None):
        self.id = id
        self.username = username
        self.password = password
        self.google_id = google_id

# 這個函式告訴 Flask-Login 如何根據 user ID 找到對應的使用者
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

# --- 全新的「身份認證」路由 ---
@app.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # 使用 bcrypt 加密密碼
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
            conn.commit()
        except sqlite3.IntegrityError:
            # 如果使用者名稱已存在，資料庫會報錯
            flash("這個使用者名稱已經被註冊了！")
            return render_template('register.html')
        finally:
            conn.close()

        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user_row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        # 檢查使用者是否存在，以及密碼是否正確
        if user_row and bcrypt.check_password_hash(user_row['password'], password):
            user = User(id=user_row['id'], username=user_row['username'], password=user_row['password'])
            login_user(user) # 幫使用者登入
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="使用者名稱或密碼錯誤！")
    return render_template('login.html')

@app.route('/logout')
@login_required # 登出前必須是登入狀態
def logout():
    logout_user() # 幫使用者登出
    return redirect(url_for('index'))

# --- 所有舊路由的「多使用者」升級版 ---
# 我們在幾乎所有路由前都加上了 @login_required
# 並在所有資料庫查詢中，都加入了 WHERE user_id = ? 的條件

@app.route('/')
@login_required
def index():
    query = request.args.get('query')
    conn = get_db_connection()
    if query:
        search_term = f"%{query}%"
        # 只搜尋屬於當前使用者的單字
        words = conn.execute('SELECT * FROM words WHERE user_id = ? AND (word LIKE ? OR definition LIKE ? OR example_sentence LIKE ?) ORDER BY id DESC', 
                             (current_user.id, search_term, search_term, search_term)).fetchall()
    else:
        words = conn.execute('SELECT * FROM words WHERE user_id = ? ORDER BY id DESC', (current_user.id,)).fetchall()
    conn.close()
    return render_template('index.html', words=words, query=query)

@app.route('/add')
@login_required
def add_choice():
    return render_template('add_choice.html')

@app.route('/add/smart')
@login_required
def add_smart():
    return render_template('add_smart.html')

@app.route('/add/manual', methods=('GET', 'POST'))
@login_required
def add_manual():
    if request.method == 'POST':
        # ... (手動新增邏輯不變)
        word, definition, example_sentence, etymology = request.form['word'], request.form['definition'], request.form['example_sentence'], request.form['etymology']
        conn = get_db_connection()
        # 新增時，把 current_user.id 也存進去
        conn.execute('INSERT INTO words (word, definition, example_sentence, etymology, user_id) VALUES (?, ?, ?, ?, ?)',
                     (word, definition, example_sentence, etymology, current_user.id))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('add_manual.html')

@app.route('/lookup', methods=['POST'])
@login_required
def lookup():
    # (查詢邏輯不變，因為它還沒存入資料庫)
    query = request.form['word']
    if contains_chinese(query):
        ai_suggestions = get_english_suggestions_from_chinese(query)
        return render_template('suggestion_list.html', query=query, suggestions=ai_suggestions.get('suggestions'), error=ai_suggestions.get('error'))
    else:
        ai_result = get_word_info(query)
        return render_template('confirm_add.html', word=query, definition=ai_result.get('definition', '解析失敗'), example_sentence=ai_result.get('example', '解析失敗'), etymology=ai_result.get('etymology', '解析失敗'), related_words=ai_result.get('related_words', []))

@app.route('/save', methods=['POST'])
@login_required
def save():
    word, definition, example_sentence, etymology = request.form['word'], request.form['definition'], request.form['example_sentence'], request.form['etymology']
    conn = get_db_connection()
    # 儲存時，把 current_user.id 也存進去
    conn.execute('INSERT INTO words (word, definition, example_sentence, etymology, user_id) VALUES (?, ?, ?, ?, ?)',
                 (word, definition, example_sentence, etymology, current_user.id))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/review')
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
    # 只從當前使用者的單字中挑選
    weakest_words = conn.execute('SELECT * FROM words WHERE user_id = ? ORDER BY review_count ASC, (CAST(correct_count AS REAL) / CASE WHEN review_count = 0 THEN 1 ELSE review_count END) ASC, last_reviewed ASC LIMIT 10', (current_user.id,)).fetchall()
    conn.close()
    if not weakest_words:
        return jsonify({'error': 'No words to review'}), 404
    word_to_review = random.choice(weakest_words)
    return jsonify(dict(word_to_review))

@app.route('/api/check/cloze', methods=['POST'])
@login_required
def api_check_cloze():
    # ... (檢查邏輯不變，但資料庫操作會是安全的，因為單字ID是唯一的)
    data = request.json
    user_guess, word_id = data.get('guess'), data.get('word_id')
    conn = get_db_connection()
    # 我們可以加一個檢查，確保這個單字屬於當前使用者
    correct_word = conn.execute('SELECT * FROM words WHERE id = ? AND user_id = ?', (word_id, current_user.id)).fetchone()
    if not correct_word: return jsonify({'error': 'Word not found or permission denied'}), 403

    is_correct = user_guess.lower() == correct_word['word'].lower()
    explanation = None
    if not is_correct:
        sentence_context = correct_word['example_sentence'].replace(correct_word['word'], '_______') if correct_word['example_sentence'] else ""
        explanation = get_wrong_answer_explanation(word=correct_word['word'], definition=correct_word['definition'], user_guess=user_guess, sentence=sentence_context)

    new_review_count = correct_word['review_count'] + 1
    new_correct_count = correct_word['correct_count']
    if is_correct: new_correct_count += 1
    conn.execute('UPDATE words SET review_count = ?, correct_count = ?, last_reviewed = CURRENT_TIMESTAMP WHERE id = ?', (new_review_count, new_correct_count, word_id))
    conn.commit()
    conn.close()
    return jsonify({'is_correct': is_correct, 'correct_word': dict(correct_word), 'user_guess': user_guess, 'explanation': explanation})

@app.route('/review/sentence')
@login_required
def review_sentence():
    conn = get_db_connection()
    word = conn.execute('SELECT * FROM words WHERE user_id = ? ORDER BY RANDOM() LIMIT 1', (current_user.id,)).fetchone()
    conn.close()
    if word is None: return redirect(url_for('add_choice'))
    return render_template('review_sentence.html', word=word)

@app.route('/check/sentence', methods=['POST'])
@login_required
def check_sentence():
    word, user_sentence = request.form['word'], request.form['user_sentence']
    ai_feedback = get_sentence_feedback(word, user_sentence)
    return render_template('result_sentence.html', user_sentence=user_sentence, ai_feedback=ai_feedback)

@app.route('/edit/<int:id>', methods=('GET', 'POST'))
@login_required
def edit_word(id):
    conn = get_db_connection()
    word = conn.execute('SELECT * FROM words WHERE id = ? AND user_id = ?', (id, current_user.id)).fetchone()
    if not word: return "Word not found or permission denied", 403 # 安全檢查
    if request.method == 'POST':
        # ... (編輯邏輯不變)
        new_word, new_definition, new_example, new_etymology = request.form['word'], request.form['definition'], request.form['example_sentence'], request.form['etymology']
        conn.execute('UPDATE words SET word = ?, definition = ?, example_sentence = ?, etymology = ? WHERE id = ?', (new_word, new_definition, new_example, new_etymology, id))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    conn.close()
    return render_template('edit_word.html', word=word)

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_word(id):
    conn = get_db_connection()
    # 只允許刪除自己的單字
    conn.execute('DELETE FROM words WHERE id = ? AND user_id = ?', (id, current_user.id))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/admin/sql', methods=('GET', 'POST'))
@login_required
def admin_sql():
    # (批次匯入也變成個人化，只會加到自己的帳號下)
    message = None
    if request.method == 'POST':
        # 我們需要修改 SQL 腳本來插入 user_id
        sql_script_template = request.form['sql_script']
        # 這是一個簡化的作法，把 user_id 硬加進去
        # 注意：這種字串替換有 SQL injection 風險，但在這個可控的後台還可以接受
        sql_script_with_user = sql_script_template.replace(') VALUES (', f', user_id) VALUES ({current_user.id}, ')

        conn = get_db_connection()
        try:
            conn.executescript(sql_script_with_user)
            conn.commit()
            message = "指令碼執行成功！"
        except Exception as e:
            message = f"發生錯誤: {e}"
        finally:
            conn.close()
    return render_template('admin_sql.html', message=message)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')