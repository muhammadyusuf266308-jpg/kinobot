# ============================================================
#  ai_service.py  –  Google Gemini & Gemma AI Xizmati
#  Syujet bo'yicha qidiruv va Dinamik Model Reytingi
# ============================================================
import os
import re
import json
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Ishonchli AI modellari ketma-ketligi (Dinamik moslashuvchan tartib)
# Qaysi model birinchi bo'lib muvaffaqiyatli javob bersa, u 1-o'ringa ko'tariladi.
# Ishlamagan yoki vaqti o'tib ketgan modellar oxiriga tushiriladi.
MODELS = [
    "gemma-4-26b-a4b-it",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
]


def _promote_model(model: str):
    """Muvaffaqiyatli ishlagan modelni ro'yxatning 1-o'rniga olib chiqadi."""
    global MODELS
    if model in MODELS and MODELS[0] != model:
        MODELS.remove(model)
        MODELS.insert(0, model)
        logger.info(f"🚀 Model {model} muvaffaqiyatli ishladi va 1-o'ringa ko'tarildi! Yangi tartib: {MODELS}")


def _demote_model(model: str):
    """Xato bergan yoki qotib qolgan modelni ro'yxat oxiriga tushiradi."""
    global MODELS
    if model in MODELS and len(MODELS) > 1:
        MODELS.remove(model)
        MODELS.append(model)
        logger.warning(f"⚠️ Model {model} muammoli bo'lgani sababli oxiriga surildi. Yangi tartib: {MODELS}")


def _call_gemini(prompt: str, json_mode: bool = False, timeout: int = 10) -> str | None:
    """Gemini / Gemma API ga tezkor va adaptiv so'rov yuborish"""
    if not GEMINI_API_KEY:
        return None

    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 450}
    }
    if json_mode:
        data["generationConfig"]["response_mime_type"] = "application/json"

    # Hozirgi modellarni nusxalab iteratsiya qilamiz
    for model in list(MODELS):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            res = requests.post(url, json=data, timeout=timeout)
            if res.status_code == 200:
                result = res.json()
                candidates = result.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        text = parts[0].get("text", "").strip()
                        if text:
                            _promote_model(model)
                            return text
                _demote_model(model)
            else:
                logger.warning(f"Model {model} javob bermadi (status {res.status_code})")
                _demote_model(model)
        except Exception as e:
            logger.warning(f"Model {model} vaqti tugadi yoki xatolik: {e}")
            _demote_model(model)

    return None


def _clean_ai_title(raw: str) -> str:
    """AI qaytargan sarlavhadan markdown, 'Selected:', 'Title:' kabi ortiqcha prefikslarni tozalaydi"""
    if not raw:
        return ""
    # Oldidagi 'Selected:', 'Title:', 'Kino nomi:' kabi so'zlarni tozalash
    t = re.sub(r"(?i)^(?:selected|title|movie|kino\s*nomi|nomi|film|ans|javob)\s*[:*–-]+\s*", "", raw.strip())
    # Markdown belgilari (*, _, `, ~, #)
    t = re.sub(r"[*_`~#]", "", t)
    # Qo'shtirnoq va tinish belgilari
    return t.strip(' "\'«»\n.:–-')


def ask_ai_for_movie_title(user_query: str) -> dict | None:
    """
    Foydalanuvchi kino syujetini yoki tavsifini yozganda,
    AI dan kinoning o'zbekcha va inglizcha nomlarini aniqlab berishni so'raydi.
    """
    prompt = f"""Kino ekspertisan. Foydalanuvchi yozgan tavsif yoki syujetdan kino nomini aniqla.
Hech qanday izohsiz, to'g'ridan-to'g'ri FAQAT quyidagi JSON formatida javob ber:
{{
  "title_uz": "O'zbekcha nomi",
  "title_en": "Inglizcha nomi"
}}

Foydalanuvchi: "{user_query}"
"""

    ans = _call_gemini(prompt)
    if ans:
        # 1. JSON javobni qidirish (teskari tartibda, oxirgi aniq natijani olish uchun)
        matches = re.findall(r'\{[^{}]*"title_uz"[^{}]*\}', ans, flags=re.DOTALL)
        for m in reversed(matches):
            try:
                data = json.loads(m)
                if isinstance(data, dict):
                    uz = _clean_ai_title(data.get("title_uz", ""))
                    en = _clean_ai_title(data.get("title_en", ""))
                    # Promptdagi placeholder larni inkor qilish
                    if uz.lower() not in ["o'zbekcha nomi", "kino nomi", "...", "nomi", "oʻzbekcha nomi"] and (uz or en):
                        res = {"title_uz": uz or en, "title_en": en or uz}
                        logger.info(f"🤖 AI aniqladi (json): '{user_query}' -> {res}")
                        return res
            except Exception:
                continue

        # 2. To'g'ridan-to'g'ri kalit regex ("title_uz": "...", "title_en": "...")
        uz_keys = [m for m in re.findall(r'"title_uz"\s*:\s*"([^"]+)"', ans) if m.lower() not in ["o'zbekcha nomi", "kino nomi", "...", "nomi"]]
        en_keys = [m for m in re.findall(r'"title_en"\s*:\s*"([^"]+)"', ans) if m.lower() not in ["inglizcha nomi", "movie title", "...", "title"]]
        if uz_keys or en_keys:
            uz = _clean_ai_title(uz_keys[-1]) if uz_keys else ""
            en = _clean_ai_title(en_keys[-1]) if en_keys else ""
            if uz or en:
                res = {"title_uz": uz or en, "title_en": en or uz}
                logger.info(f"🤖 AI aniqladi (key-regex): '{user_query}' -> {res}")
                return res

        # 3. Kalit so'zlar bo'yicha qidirish (Uzbek: ... English: ...)
        uz_match = re.findall(r"(?:Uzbek|O'zbekcha|Oʻzbekcha)\s*(?:Title|nomi)?\s*[:*–-]+\s*([^\n\r*`]+)", ans, re.IGNORECASE)
        en_match = re.findall(r"(?:English|Inglizcha)\s*(?:Title|nomi)?\s*[:*–-]+\s*([^\n\r*`]+)", ans, re.IGNORECASE)
        if uz_match or en_match:
            uz = _clean_ai_title(uz_match[-1]) if uz_match else ""
            en = _clean_ai_title(en_match[-1]) if en_match else ""
            if uz or en:
                res = {"title_uz": uz or en, "title_en": en or uz}
                logger.info(f"🤖 AI aniqladi (title-regex): '{user_query}' -> {res}")
                return res

        # 4. Oddiy tozalangan matn
        clean_ans = _clean_ai_title(ans.splitlines()[-1] if "\n" in ans else ans)
        if clean_ans and len(clean_ans) < 60:
            logger.info(f"🤖 AI aniqladi (raw): '{user_query}' -> '{clean_ans}'")
            return {"title_uz": clean_ans, "title_en": clean_ans}

    return None


def parse_post_with_ai(text: str, message_id: int = None) -> list[dict]:
    """
    Telegram kanalidagi murakkab postni AI orqali tahlil qiladi.
    Agar postda kino kodi bo'lsa, uni to'g'ri ajratib beradi.
    """
    prompt = f"""Quyidagi Telegram postini tahlil qil.
Agar postda bir yoki bir nechta KINO va ularning KODI (kod raqami) bo'lsa, JSON ro'yxat qaytar.
Agar bu oddiy reklama, e'lon yoki kodi yo'q post bo'lsa, bo'sh ro'yxat [] qaytar.

JSON formati:
[
  {{
    "title": "kino nomi",
    "bot_code": "Kod:123",
    "year": 2024,
    "genre": "janri yoki tili"
  }}
]

POST:
{text}
"""

    ans = _call_gemini(prompt)
    if not ans:
        return []

    try:
        json_array_match = re.search(r'\[[\s\S]*\]', ans)
        if json_array_match:
            items = json.loads(json_array_match.group(0))
            if isinstance(items, list):
                res = []
                for it in items:
                    if it.get("title") and it.get("bot_code"):
                        code = str(it["bot_code"]).strip()
                        if not code.lower().startswith("kod:"):
                            code = f"Kod:{code}"
                        res.append({
                            "title": str(it["title"]).strip(),
                            "title_ru": None,
                            "title_en": None,
                            "year": it.get("year"),
                            "genre": it.get("genre"),
                            "description": None,
                            "bot_code": code,
                            "channel_msg_id": message_id
                        })
                return res
    except Exception as e:
        logger.warning(f"AI JSON parse xatosi: {e}")

    return []


def ask_ai_recommend(user_request: str, available_genres: list[str] = None) -> dict | None:
    """
    Foydalanuvchining kayfiyati yoki so'rovi asosida kino janrini va tavsiyasini qaytaradi.
    Qaytariladigan format: {"genre_keyword": "janr so'zi", "reason": "sababining qisqacha matni"}
    """
    genres_hint = ", ".join(available_genres) if available_genres else "jangari, fantastika, komediya, horror, oilaviy, drama, triller"
    prompt = f"""Sen kino maslahatchisin. Foydalanuvchi kino ko'rmoqchi va quyidagicha yozdi:
"{user_request}"

Foydalanuvchining kayfiyati yoki istagiga qarab, quyidagi janrlar orasidan eng mos birini tanla: {genres_hint}

Hech qanday izohsiz, FAQAT JSON formatida javob ber:
{{"genre_keyword": "tanlangan janr", "reason": "nima uchun shu janr mos (1 jumla, o'zbek tilida)"}}
"""
    ans = _call_gemini(prompt)
    if not ans:
        return None
    try:
        matches = re.findall(r'\{[^{}]*"genre_keyword"[^{}]*\}', ans, flags=re.DOTALL)
        for m in reversed(matches):
            data = json.loads(m)
            if isinstance(data, dict) and data.get("genre_keyword"):
                gk = _clean_ai_title(data["genre_keyword"])
                reason = data.get("reason", "")
                if gk and gk.lower() not in ["...", "janr"]:
                    logger.info(f"🤖 AI tavsiya janri: '{user_request}' -> '{gk}'")
                    return {"genre_keyword": gk, "reason": reason}
    except Exception:
        pass
    return None
