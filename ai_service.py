# ============================================================
#  ai_service.py  –  Google Gemini AI Xizmati
#  Syujet bo'yicha qidiruv va Aqlli post tahlili
# ============================================================
import os
import re
import json
import logging
import requests

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Ishonchli Gemini modellari ketma-ketligi (biri band bo'lsa, ikkinchisiga o'tadi)
MODELS = [
    "gemini-3-flash-preview",
    "gemma-4-26b-a4b-it",
    "gemini-flash-latest"
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
            res = requests.post(url, json=data, timeout=8)
            if res.status_code == 200:
                result = res.json()
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                return text.strip()
            elif res.status_code == 503:
                # Model vaqtincha band, keyingisiga o'tamiz
                continue
        except Exception as e:
            logger.warning(f"Gemini {model} xatosi: {e}")
            continue

    return None


def ask_ai_for_movie_title(user_query: str) -> str | None:
    """
    Foydalanuvchi kino syujetini yoki xato nom yozganda,
    AI dan kino nomini aniqlab berishni so'raydi.
    Masalan:
      "bitta kema aysbergga urilib cho'kib ketadi" -> "Titanik"
      "yigitni o'rgimchak chaqib oladi" -> "O'rgimchak odam"
    """
    prompt = f"""Sen kino ekspertisan. Foydalanuvchi kino haqida yozgan tavsif yoki xato nomdan kino nomini topishing kerak.
Faqat va faqat kinoning asl O'zbekcha yoki xalqaro nomini 1-3 so'z bilan yoz. Hech qanday ortiqcha gap, salom yoki izoh yozma!

Foydalanuvchi so'rovi:
"{user_query}"

Kino nomi:"""

    ans = _call_gemini(prompt)
    if ans:
        # Ortiqcha qo'shtirnoq va belgilarni tozalash
        ans = ans.strip(' "\'«»\n.').split('\n')[0]
        logger.info(f"🤖 AI topgan kino: '{user_query}' -> '{ans}'")
        return ans
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
