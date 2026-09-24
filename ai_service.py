# ============================================================
#  ai_service.py  –  Google Gemini AI Xizmati
#  Syujet bo'yicha qidiruv va Aqlli post tahlili
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

# Ishonchli Gemini modellari ketma-ketligi (birinchisi band bo'lsa, keyingisiga o'tadi)
MODELS = [
    "gemini-3.6-flash",
    "gemma-4-26b-a4b-it",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
]


def _call_gemini(prompt: str, json_mode: bool = False) -> str | None:
    """Gemini API ga xavfsiz so'rov yuborish"""
    if not GEMINI_API_KEY:
        return None

    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    if json_mode:
        data["generationConfig"] = {"response_mime_type": "application/json"}

    for model in MODELS:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            res = requests.post(url, json=data, timeout=15)
            if res.status_code == 200:
                result = res.json()
                candidates = result.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
            else:
                logger.warning(f"Gemini {model} javob bermadi (status {res.status_code})")
                continue
        except Exception as e:
            logger.warning(f"Gemini {model} xatosi: {e}")
            continue

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
    prompt = f"""Sen kino ekspertisan. Foydalanuvchi kino haqida yozgan tavsif, syujet yoki xato nomdan qidirilayotgan kinoni aniqla.
Javobni quyidagi JSON formatda ber:
{{
  "title_uz": "O'zbekcha nomi (masalan: O'rgimchak odam, Qasoskorlar, Tor, Titanik)",
  "title_en": "Inglizcha nomi (masalan: Spider-Man, The Avengers, Thor, Titanic)"
}}

Foydalanuvchi so'rovi:
"{user_query}"
"""

    ans = _call_gemini(prompt, json_mode=True)
    if ans:
        try:
            clean = re.sub(r"^```(?:json)?\s*", "", ans.strip(), flags=re.IGNORECASE)
            clean = re.sub(r"\s*```$", "", clean).strip()
            data = json.loads(clean)
            if isinstance(data, dict):
                title_uz = _clean_ai_title(data.get("title_uz", ""))
                title_en = _clean_ai_title(data.get("title_en", ""))
                res = {"title_uz": title_uz, "title_en": title_en}
                logger.info(f"🤖 AI aniqladi: '{user_query}' -> {res}")
                return res
        except Exception:
            pass

    # Agar JSON bo'lmasa oddiy matn sifatida so'raymiz
    text_prompt = f"Kino syujetidan o'zbekcha kino nomini 1-3 so'z bilan yoz:\n\"{user_query}\"\nKino nomi:"
    raw_ans = _call_gemini(text_prompt)
    if raw_ans:
        lines = [line.strip(' \t\r"*-\'') for line in raw_ans.splitlines() if line.strip(' \t\r"*-')]
        clean_ans = lines[-1] if lines else raw_ans
        clean_ans = _clean_ai_title(clean_ans)
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

    ans = _call_gemini(prompt, json_mode=True)
    if not ans:
        return []

    try:
        # JSON parsing
        # Ba'zida model ```json ... ``` bilan berishi mumkin
        cleaned = re.sub(r"^```json\s*|\s*```$", "", ans.strip())
        items = json.loads(cleaned)
        if isinstance(items, list):
            res = []
            for it in items:
                if it.get("title") and it.get("bot_code"):
                    # Kodni to'g'rilash
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
