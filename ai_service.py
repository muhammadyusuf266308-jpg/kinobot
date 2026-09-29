# ============================================================
#  ai_service.py  –  Google Gemini AI Xizmati (Async + Ishonchli)
#  Syujet bo'yicha qidiruv va Dinamik Model Reytingi
# ============================================================
import os
import re
import json
import logging
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Haqiqiy mavjud Google Gemini modellari (eng tezi birinchi)
MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash",
]


def _promote_model(model: str):
    """Muvaffaqiyatli ishlagan modelni ro'yxatning 1-o'rniga olib chiqadi."""
    global MODELS
    if model in MODELS and MODELS[0] != model:
        MODELS.remove(model)
        MODELS.insert(0, model)
        logger.info(f"🚀 Model {model} 1-o'ringa ko'tarildi: {MODELS}")


def _demote_model(model: str):
    """Xato bergan modelni ro'yxat oxiriga tushiradi."""
    global MODELS
    if model in MODELS and len(MODELS) > 1:
        MODELS.remove(model)
        MODELS.append(model)
        logger.warning(f"⚠️ Model {model} oxiriga surildi: {MODELS}")


async def _call_gemini(prompt: str, json_mode: bool = False, timeout: int = 15) -> str | None:
    """Gemini API ga async va adaptiv so'rov yuborish (event loopni bloklamaydi)"""
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY o'rnatilmagan!")
        return None

    import asyncio

    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 800}
    }
    if json_mode:
        data["generationConfig"]["response_mime_type"] = "application/json"

    async with httpx.AsyncClient(timeout=timeout) as client:
        for model in list(MODELS):
            for attempt in range(2):  # 503 uchun 1 marta qayta urinish
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
                    res = await client.post(url, json=data)
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
                        break  # Empty response, skip to next model
                    elif res.status_code == 503 and attempt == 0:
                        # Vaqtinchalik yuklama — 1.5 soniya kutib qayta urinamiz
                        logger.info(f"Model {model} band (503), 1.5s kutilmoqda...")
                        await asyncio.sleep(1.5)
                        continue
                    elif res.status_code == 429 and attempt == 0:
                        # Rate limit — 2 soniya kutib qayta urinamiz
                        logger.info(f"Model {model} rate limit (429), 2s kutilmoqda...")
                        await asyncio.sleep(2.0)
                        continue
                    else:
                        logger.warning(f"Model {model} xato (status {res.status_code})")
                        _demote_model(model)
                        break
                except httpx.TimeoutException:
                    logger.warning(f"Model {model} vaqti tugadi ({timeout}s)")
                    _demote_model(model)
                    break
                except Exception as e:
                    logger.warning(f"Model {model} xatolik: {e}")
                    _demote_model(model)
                    break

    return None


def _clean_ai_title(raw: str) -> str:
    """AI qaytargan sarlavhadan markdown, ortiqcha prefikslarni tozalaydi"""
    if not raw:
        return ""
    t = re.sub(r"(?i)^(?:selected|title|movie|kino\s*nomi|nomi|film|ans|javob)\s*[:*–-]+\s*", "", raw.strip())
    t = re.sub(r"[*_`~#]", "", t)
    return t.strip(' "\'«»\n.:–-')


async def ask_ai_for_movie_title(user_query: str) -> dict | None:
    """
    Foydalanuvchi kino syujetini yoki tavsifini yozganda,
    AI dan kinoning o'zbekcha, inglizcha, ruscha nomlarini aniqlab beradi.
    """
    prompt = f"""Sen jahon kinosining eng kuchli ekspertisan.
Foydalanuvchi yozgan tavsif, syujet yoki parcha qaysi filmga tegishli ekanligini aniqla.
Hech qanday boshqa izohsiz, to'g'ridan-to'g'ri FAQAT quyidagi JSON formatida javob ber:
{{
  "title_uz": "O'zbekcha nomi",
  "title_en": "Original Inglizcha nomi",
  "title_ru": "Ruscha nomi",
  "year": 2024,
  "alt_titles": ["Muqobil nom 1", "Muqobil nom 2"]
}}

Foydalanuvchi yozgan matn: "{user_query}"
"""

    ans = await _call_gemini(prompt)
    if ans:
        try:
            m = re.search(r'\{[\s\S]*"title_uz"[\s\S]*\}', ans)
            if m:
                data = json.loads(m.group(0))
                if isinstance(data, dict):
                    uz = _clean_ai_title(data.get("title_uz", ""))
                    en = _clean_ai_title(data.get("title_en", ""))
                    ru = _clean_ai_title(data.get("title_ru", ""))
                    year = data.get("year")
                    alts = [_clean_ai_title(a) for a in data.get("alt_titles", []) if _clean_ai_title(a)]

                    if uz.lower() not in ["o'zbekcha nomi", "kino nomi", "...", "nomi", "oʻzbekcha nomi"] and (uz or en or ru):
                        res = {
                            "title_uz": uz or en or ru,
                            "title_en": en or uz or ru,
                            "title_ru": ru or uz or en,
                            "year": year if isinstance(year, int) else None,
                            "alt_titles": alts
                        }
                        logger.info(f"🤖 AI kino aniqladi: '{user_query}' -> {res}")
                        return res
        except Exception as e:
            logger.warning(f"AI movie title parse xatosi: {e}")

        # Regex fallback
        uz_match = re.findall(r'"title_uz"\s*:\s*"([^"]+)"', ans)
        en_match = re.findall(r'"title_en"\s*:\s*"([^"]+)"', ans)
        ru_match = re.findall(r'"title_ru"\s*:\s*"([^"]+)"', ans)
        if uz_match or en_match or ru_match:
            uz = _clean_ai_title(uz_match[-1]) if uz_match else ""
            en = _clean_ai_title(en_match[-1]) if en_match else ""
            ru = _clean_ai_title(ru_match[-1]) if ru_match else ""
            if uz or en or ru:
                return {
                    "title_uz": uz or en or ru,
                    "title_en": en or uz or ru,
                    "title_ru": ru or uz or en,
                    "year": None,
                    "alt_titles": []
                }

    return None


async def ask_ai_universal(
    user_message: str,
    user_name: str = "Foydalanuvchi",
    chat_title: str = None,
    is_channel_comment: bool = False,
    post_context: str = None
) -> dict:
    """
    Har qanday savol, suhbat yoki kino so'rovini tahlil qiluvchi Universal AI.
    """
    context_info = []
    if chat_title:
        context_info.append(f"Guruh/Chat: {chat_title}")
    if is_channel_comment:
        context_info.append("Holat: Kanal posti ostidagi kommentariya")
    if post_context:
        context_info.append(f"Post mazmuni: {post_context[:200]}")

    ctx_str = "\n".join(context_info) if context_info else ""

    prompt = f"""Sen kino kanali va botining eng kuchli, tajribali jahon kinosi ensiklopediyasi va universal intellektli AI yordamchisisan.
Sen minglab kinolarni, ularning eng kichik detallari, qisqa syujet parchalari, qahramonlari, atmosferasi (masalan, kimsasiz cho'l poygalari, vampirlar va qorong'u qal'a, orolga tushib qolgan odam va to'p, vaqt sayohati va qora tuynuk kabilar) orqali darhol qaysi film ekanligini 100% aniqlik bilan topa olasan.
Shuningdek, foydalanuvchilarning HAR QANDAY boshqa savoliga (kino olami, aktyorlar, fan, dunyoqarash, faktlar, salom-alik, botdan foydalanish) to'liq, muloyim, qiziqarli va o'zbek tilida javob bera oladigan bilimdon intellektsan.

FOYDALANUVCHI XABARINI TAHLIL QIL VA FAQAT QUYIDAGI JSON FORMATIDA JAVOB BER:

1. Agar foydalanuvchi ma'lum bir KINONI qidirayotgan bo'lsa (nomini to'liq yozgan, noto'g'ri yozgan, yoki faqat qisqa syujetini, bitta sahnasini, atmosferasini, aktyorini yoki voqealar rivojini tasvirlab bergan bo'lsa):
{{
  "type": "movie_search",
  "title_uz": "Kinoning o'zbekcha mashhur nomi",
  "title_en": "Original inglizcha rasmiy nomi",
  "title_ru": "Ruscha nomi",
  "year": 2024,
  "alt_titles": ["Muqobil nom 1", "Muqobil nom 2"]
}}

2. Agar foydalanuvchi KINO TAVSIYASI so'rayotgan bo'lsa (masalan "qanaqa kino ko'ray", "dahshatli kino ayt", "zerikdim", "kayfiyatim yo'q"):
{{
  "type": "recommendation",
  "genre": "jangari",
  "text": "Tavsiya sababi (1 jumla)"
}}

3. HAR QANDAY BOSHQA SAVOL, SUHBAT, ILMIY/DUNYOVIY SAVOL, SALOM-ALIK YOKI MUROJAAT BO'LSA:
{{
  "type": "chat",
  "text": "Savolga to'liq, aniq, muloyim va foydali javob (Telegram HTML formatida, <b>, <i>, <code> teglaridan foydalanib yoz)"
}}

{ctx_str}
Foydalanuvchi ismi: {user_name}
Foydalanuvchi xabari: "{user_message}"
"""

    ans = await _call_gemini(prompt, json_mode=True)
    if ans:
        try:
            m = re.search(r'\{[\s\S]*\}', ans)
            if m:
                data = json.loads(m.group(0))
                if isinstance(data, dict) and "type" in data:
                    return data
        except Exception as e:
            logger.warning(f"Universal AI parse xatosi: {e}")

    # Fallback
    raw_chat = await ask_ai_admin_assistant(user_message, user_name, chat_title, is_channel_comment, post_context)
    if raw_chat:
        return {"type": "chat", "text": raw_chat}

    return {"type": "chat", "text": f"Assalomu alaykum, <b>{user_name}</b>! Sizga qanday yordam bera olaman? Kino nomi yoki kodini yozing, darhol topib beraman! 😊"}


async def ask_ai_admin_assistant(
    user_message: str,
    user_name: str = "Foydalanuvchi",
    chat_title: str = None,
    is_channel_comment: bool = False,
    post_context: str = None
) -> str | None:
    """
    Kanal admini nomidan foydalanuvchilar bilan samimiy, aqlli va professional muloqot qiladi.
    """
    context_info = []
    if chat_title:
        context_info.append(f"Chat/Guruh nomi: {chat_title}")
    if is_channel_comment:
        context_info.append("Holat: Foydalanuvchi kanaldagi post ostiga komment (Reply) yozdi.")
    if post_context:
        context_info.append(f"Post mazmuni: {post_context[:200]}")

    context_str = "\n".join(context_info) if context_info else "Shaxsiy xabar"

    prompt = f"""Sen kino kanali va botining rasmiy ADMINI yordamchisisan (UzKino AI Assistanti).
Foydalanuvchi bilan xuddi kanal admini kabi samimiy, xushmuomala, professional va o'zbek tilida gaplash.

BOT VA KANAL QOIDALARI:
1. Kinoni botdan olish: Foydalanuvchi kino kodini botga yuborishi kerak (masalan, 243).
2. Kino qidirish: Kino nomini yozish kifoya (masalan, "Astral" yoki "kino Astral").
3. Syujet bo'yicha topish: "kinochi ..." deb syujetni yozish kerak.
4. Menyu tugmalari: 🔥 Top kinolar, 🎭 Janrlar bo'yicha, 🎲 Tasodifiy kino.
5. Agar foydalanuvchi salom bersa, minnatdorchilik bildirsa yoki savol bersa, muloyim javob ber.
6. Agar foydalanuvchi kanalda yo'q kinoni so'rayotgan bo'lsa, "Biroz kuting, adminga so'rovingiz yetkazildi, tez orada kanalga yuklab beriladi!" deb tinchlantir.
7. Javobing ixcham (1-3 jumla), chiroyli va o'zbek tilida Telegram HTML formatida bo'lsin.

KONTEKST:
{context_str}
Foydalanuvchi ismi: {user_name}
Foydalanuvchi xabari: "{user_message}"

ADMIN JAVOBI:"""

    ans = await _call_gemini(prompt)
    if ans:
        ans = re.sub(r"(?i)^(?:admin|javob|uzkino ai)\s*[:*–-]+\s*", "", ans.strip())
        return ans.strip()
    return None


async def parse_post_with_ai(text: str, message_id: int = None) -> list[dict]:
    """
    Telegram kanalidagi murakkab postni AI orqali tahlil qiladi.
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

    ans = await _call_gemini(prompt)
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


async def ask_ai_recommend(user_request: str, available_genres: list[str] = None) -> dict | None:
    """
    Foydalanuvchining kayfiyati yoki so'rovi asosida kino janrini va tavsiyasini qaytaradi.
    """
    genres_hint = ", ".join(available_genres) if available_genres else "jangari, fantastika, komediya, horror, oilaviy, drama, triller"
    prompt = f"""Sen kino maslahatchisin. Foydalanuvchi kino ko'rmoqchi va quyidagicha yozdi:
"{user_request}"

Foydalanuvchining kayfiyati yoki istagiga qarab, quyidagi janrlar orasidan eng mos birini tanla: {genres_hint}

Hech qanday izohsiz, FAQAT JSON formatida javob ber:
{{"genre_keyword": "tanlangan janr", "reason": "nima uchun shu janr mos (1 jumla, o'zbek tilida)"}}
"""
    ans = await _call_gemini(prompt)
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
