import os
import json
import re
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

model = None
if api_key:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro-latest')
    except Exception as e:
        print(f"初始化 Gemini 模型時發生錯誤: {e}")

def clean_json_response(text):
    """安全地清理 AI 回傳的 markdown json 標籤"""
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text

def get_word_info(word):
    if not model: return {"error": "AI 模型未初始化，請檢查 API Key。"}
    try:
        prompt = f"""
        You are a professional lexicographer and English teacher creating data for a learning app.
        For the English word "{word}", provide a single, valid, RFC 8259 compliant JSON object and nothing else.
        The JSON object MUST contain the following eight keys:
        - "word": (string) The exact word "{word}".
        - "level": (integer) The estimated vocabulary level from 1 to 6, please classify "{word}" as level 4.
        - "part_of_speech": (string) The most common part of speech in abbreviated form (e.g., "n.", "v.", "adj.").
        - "definition": (string) The most common and clear definition in Traditional Chinese.
        - "collocation": (string) A very common and useful two or three-word phrase or collocation.
        - "mnemonic": (string) A short, creative, and memorable learning tip in Traditional Chinese, possibly using association or word breakdown.
        - "example1": (string) An English example sentence of over 10 words using the collocation, with the collocation enclosed in **double asterisks**.
        - "example2": (string) A second, different English example sentence of over 10 words using the collocation, with the collocation enclosed in **double asterisks**.
        - "etymology": {{ "prefixes": [{{ "part": "string", "meaning": "string" }}], "roots": [{{ "part": "string", "meaning": "string" }}], "suffixes": [{{ "part": "string", "meaning": "string" }}] }}.
        - "relations": {{ "synonyms": ["string"], "antonyms": ["string"] }}.
        """
        response = model.generate_content(prompt)
        cleaned_response = clean_json_response(response.text)
        ai_data = json.loads(cleaned_response)
        return ai_data
    except Exception as e:
        print(f"AI 查詢 '{word}' 或 JSON 解析時發生錯誤: {e}")
        return {"error": f"AI 查詢時發生嚴重錯誤，請檢查終端機日誌。"}

def get_sentence_feedback(word, user_sentence):
    # 【測試模式】攔截特定的單字與句子，回傳對應的假資料
    
    # 測試情境 1：完美的句子 (測試 UI 的 ✅ 綠色成功提示)
    if word == "abandon" and "sinking ship" in user_sentence.lower():
        return {
            "analysis": "文法完全正確！時態與語意都非常清晰。使用 'refused to do something' 的句型搭配這個單字非常道地。",
            "suggestion": "The captain refused to abandon the sinking ship. (你的句子已經很棒了，維持這樣就好！)",
            "usage_ok": True
        }
        
    # 測試情境 2：單字用法對，但有小文法錯誤 (測試 UI 修正建議)
    elif word == "absolute" and "confident" in user_sentence.lower():
        return {
            "analysis": "你使用了 'absolute' 這個形容詞來修飾，方向是正確的。不過 'confident' 是形容詞，在動詞 have 後面應該要用名詞 'confidence' 才符合文法。",
            "suggestion": "I have absolute confidence in you.",
            "usage_ok": True
        }
        
    # 測試情境 3：單字用法錯誤、語境不自然 (測試 UI 的 ⚠️ 橘色警告提示)
    elif word == "desert" and "homework" in user_sentence.lower():
        return {
            "analysis": "'desert' 通常用來指「遺棄、拋棄（人、地方或重大責任）」，帶有殘忍或背棄的意味。用來形容「放棄寫作業」語氣太重且非常不自然。",
            "suggestion": "I want to give up on my homework. (放棄一般的事物用 give up 即可)",
            "usage_ok": False
        }
        
    # 預設回覆：如果你隨便打其他的句子，就給這個預設值
    return {
        "analysis": "這是一個預設的測試分析。你的句子結構基本完整。",
        "suggestion": "這是 AI 建議的優化版本。",
        "usage_ok": True
    }

def get_wrong_answer_explanation(word, definition, user_guess, sentence):
    if not model: return "AI 模型未初始化"
    try:
        prompt = f"""
        As a helpful English teacher, a student is reviewing "{word}" (definition: {definition}) but answered incorrectly with "{user_guess}" for the sentence: "{sentence}".
        Provide a brief, friendly explanation in Traditional Chinese to help the student remember.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 詳解生成時發生錯誤: {e}"

def get_english_suggestions_from_chinese(chinese_term):
    if not model: return {"error": "AI 模型未初始化"}
    try:
        prompt = f"""
        As a linguistic expert and translator, your task is to suggest English words based on a Traditional Chinese term.
        The user provides the term: "{chinese_term}"

        Please return a valid JSON object containing a single key "suggestions".
        The value of "suggestions" should be an array of JSON objects.
        Each object in the array must have two keys:
        1. "word": (string) The suggested English word.
        2. "hint": (string) A brief explanation in Traditional Chinese about the nuance or typical usage of this English word, to help the user choose.

        Provide 3 to 5 distinct suggestions.
        """
        response = model.generate_content(prompt)
        cleaned_response = clean_json_response(response.text)
        ai_data = json.loads(cleaned_response)
        return ai_data
    except Exception as e:
        print(f"AI 建議生成時發生錯誤: {e}")
        return {"error": f"AI 建議生成時發生錯誤: {e}"}

def generate_multi_word_cloze(words_list):
    if not model: return {"error": "AI 模型未初始化"}
    word_string = ", ".join(words_list)
    try:
        prompt = f"""
        As an expert storyteller, create a short, coherent English story or dialogue (about 50-80 words).
        This story MUST use all of the following English words: {word_string}.

        Return a single, valid JSON object with one key, "story".
        The value of "story" should be the complete story you created.
        """
        response = model.generate_content(prompt)
        cleaned_response = clean_json_response(response.text)
        ai_data = json.loads(cleaned_response)
        return ai_data
    except Exception as e:
        print(f"AI 故事生成時發生錯誤: {e}")
        return {"error": f"AI 故事生成時發生錯誤: {e}"}