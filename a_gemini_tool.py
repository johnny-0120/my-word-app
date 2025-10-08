# a_gemini_tool.py (語言強化版)
import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

model = None
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro-latest') # 我們換回更穩定的 Pro 模型

# 在 a_gemini_tool.py 中找到 get_word_info 函式並替換
import json # 再次確認檔案頂部有 import json

# 在 a_gemini_tool.py 中找到 get_word_info 函式並替換
def get_word_info(word):
    if not model: return {"error": "AI 模型未初始化"}
    try:
        prompt = f"""
        Analyze the English word "{word}". Return a single, valid JSON object with these keys:
        "definition": (string) Most common definition in Traditional Chinese.
        "example": (string) An English example sentence with Traditional Chinese translation.
        "synonyms": (array of strings) A list of 2-3 common synonyms.
        "antonyms": (array of strings) A list of 1-2 common antonyms.
        "etymology": {{ "prefixes": [{{ "prefix": string, "meaning": string }}], "roots": [{{ "root": string, "meaning": string }}], "suffixes": [{{ "suffix": string, "meaning": string }}] }}
        """
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace('`json', '').replace('`', '')
        ai_data = json.loads(cleaned_response)
        return ai_data
    except Exception as e:
        return {"error": f"AI 查詢失敗: {e}"}
    
def get_sentence_feedback(word, user_sentence):
    if not model:
        return {"error": "AI 模型未初始化"}

    try:
        # --- START: 語言強化指令 ---
        prompt = f"""
        As an English grammar expert, analyze the user's sentence.
        The user is learning "{word}" and wrote: "{user_sentence}"

        Return a JSON object with three keys. All string values MUST be in **Traditional Chinese**.
        - "analysis": (string) Briefly analyze the grammar.
        - "suggestion": (string) Provide a better, more natural version of the sentence.
        - "usage_ok": (boolean) Is the usage of "{word}" appropriate?
        """
        # --- END: 語言強化指令 ---

        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace('`json', '').replace('`', '')
        ai_data = json.loads(cleaned_response)
        return ai_data

    except Exception as e:
        print(f"AI 查詢或 JSON 解析時發生錯誤: {e}")
        return {"error": f"AI 批改時發生錯誤: {e}"}

def get_wrong_answer_explanation(word, definition, user_guess, sentence):
    if not model:
        return "AI 模型未初始化"

    try:
        # --- START: 語言強化指令 ---
        prompt = f"""
        You are a helpful English teacher.
        A student is reviewing the word "{word}" (definition: {definition}) but answered incorrectly with "{user_guess}" in the context of the sentence: "{sentence}".

        Provide a brief, friendly explanation in **Traditional Chinese** to help the student remember.
        """
        # --- END: 語言強化指令 ---

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 詳解生成時發生錯誤: {e}"
    
    # 在 a_gemini_tool.py 的最下方加入這個新函式

def get_english_suggestions_from_chinese(chinese_term):
    if not model:
        return {"error": "AI 模型未初始化"}

    try:
        # 全新的 AI 指令，專門用來反向查詢
        prompt = f"""
        As a linguistic expert and translator, your task is to suggest English words based on a Traditional Chinese term.
        The user provides the term: "{chinese_term}"

        Please return a valid JSON object containing a single key "suggestions".
        The value of "suggestions" should be an array of JSON objects.
        Each object in the array must have two keys:
        1. "word": (string) The suggested English word.
        2. "hint": (string) A brief explanation in Traditional Chinese about the nuance or typical usage of this English word, to help the user choose.

        Provide 3 to 5 distinct suggestions.
        Example response for "短暫的":
        {{
          "suggestions": [
            {{"word": "ephemeral", "hint": "形容美麗但生命週期極短的事物，帶有詩意。"}},
            {{"word": "transient", "hint": "指短時間的停留或存在，常用於形容過客或短期的狀況。"}},
            {{"word": "fleeting", "hint": "形容飛逝而過的、難以捕捉的瞬間，如情感或機會。"}},
            {{"word": "temporary", "hint": "指暫時的、非永久性的安排或解決方案。"}}]
        }}
        """

        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace('`json', '').replace('`', '')
        ai_data = json.loads(cleaned_response)

        return ai_data

    except Exception as e:
        print(f"AI 建議生成時發生錯誤: {e}")
        return {"error": f"AI 建議生成時發生錯誤: {e}"}
    
    # 在 a_gemini_tool.py 的最下方加入這個新函式

def generate_multi_word_cloze(words_list):
    if not model:
        return {"error": "AI 模型未初始化"}

    # 將單字列表轉換成一個簡單的字串，例如 "ephemeral, ubiquitous, ..."
    word_string = ", ".join(words_list)

    try:
        prompt = f"""
        As an expert storyteller, create a short, coherent English story or dialogue (about 50-80 words).
        This story MUST use all of the following English words: {word_string}.

        Return a single, valid JSON object with one key, "story".
        The value of "story" should be the complete story you created.
        """

        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace('`json', '').replace('`', '')
        ai_data = json.loads(cleaned_response)

        return ai_data

    except Exception as e:
        print(f"AI 故事生成時發生錯誤: {e}")
        return {"error": f"AI 故事生成時發生錯誤: {e}"}