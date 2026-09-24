# ============================================================
#  channel_parser.py  –  Haqiqiy Kino Postlarini Aniq Tanuvchi Parser
#  Ko'p kinoli ro'yxatlar va barcha formatlarni qo'llab-quvvatlaydi
# ============================================================
import re
import logging

logger = logging.getLogger(__name__)

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

# Aniq kod qidiruv: "Kino kodi: 226", "Kino kodi 209", "Kod: 237", "Kod:216", "Kodi: 165"
_KOD_PATTERNS = [
    re.compile(r"(?i)(?:🔎\s*)?(?:kino\s*)?kod[iı]?\s*[:\-]?\s*(\d+)"),
    re.compile(r"(?i)\bkod\s*[:\-]?\s*(\d+)"),
]

# Ro'yxat formati qatori: masalan "127 — 📺Tor" yoki "147 - Momaqaldiroqlar" yoki "№124. Qasoskorlar"
_LIST_LINE_RE = re.compile(r"^(?:№\s*)?(\d{1,5})\s*[\.\-—–:]\s*(.+)$")

# Reklama va oddiy gaplarni aniqlovchi filtr (faqat aniq no-kino postlar uchun)
_SPAM_KEYWORDS = [
    "kanal sotiladi", "open budget", "ovoz bering", "ovoz olamiz",
    "aktiv bo", "uzur so", "arzonga bervoraman", "dangal oladiganlar"
]

_FIELD_RE = re.compile(
    r"^(?:[\U00010000-\U0010ffff\u2600-\u26FF\u2700-\u27BF"
    r"\U0001F300-\U0001F9FF\U0001FA00-\U0001FA9F"
    r"\U00002702-\U000027B0\U0001F1E0-\U0001F1FF\ufe0e\ufe0f]*\s*)?"
    r"([^:\n]{1,30}):\s*(.+)$"
)


def _clean_emojis(text: str) -> str:
    # 1. Emojilar va maxsus belgilarni tozalash
    t = re.sub(
        r"[\U00010000-\U0010ffff\u2600-\u26FF\u2700-\u27BF"
        r"\U0001F300-\U0001F9FF\U0001FA00-\U0001FA9F"
        r"\U00002702-\U000027B0\U0001F1E0-\U0001F1FF\ufe0e\ufe0f]+",
        "", text
    )
    # 2. Markdown belgilarini tozalash (*, _, `, ~)
    t = re.sub(r"[*_`~]", "", t)
    return t.strip()


def _normalize_key(raw: str) -> str:
    return _clean_emojis(raw).lower()


def parse_post_multiple(text: str, message_id: int = None) -> list[dict]:
    """
    Agar postda bitta post ichida bir nechta kino ro'yxati bo'lsa
    (masalan: 127 — 📺Tor \n 126 — 📺Temir Odam...),
    har birini alohida kino qilib qaytaradi.
    Aks holda bitta elementli ro'yxat yoki bo'sh ro'yxat qaytaradi.
    """
    if not text or len(text.strip()) < 5:
        return []

    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]

    # 1. Post ko'p kinoli ro'yxat ekanligini tekshiramiz
    list_items = []
    for line in lines:
        clean_l = _clean_emojis(line)
        m = _LIST_LINE_RE.match(clean_l)
        if m:
            code_num = m.group(1).strip()
            title = _clean_emojis(m.group(2)).strip(". :–- ")
            if title and len(title) > 1 and not any(skip in title.lower() for skip in ["botimiz", "kanalimiz", "http", "t.me"]):
                list_items.append({
                    "title": title,
                    "title_ru": None,
                    "title_en": None,
                    "year": None,
                    "genre": None,
                    "description": None,
                    "bot_code": f"Kod:{code_num}",
                    "channel_msg_id": message_id
                })

    # Agar kamida 2 ta ro'yxat qatori topilsa, demak bu kino ro'yxati posti!
    if len(list_items) >= 2:
        return list_items

    # 2. Oddiy yakka post bo'lsa
    single = parse_post(text, message_id)
    return [single] if single else []


def parse_post(text: str, message_id: int = None) -> dict | None:
    """
    Bitta kino postini aniq tahlil qiladi.
    """
    if not text or len(text.strip()) < 8:
        return None

    lower_text = text.lower()

    # 1. Qat'iy qoida: Post matnida "kod" yoki "kodi" so'zi bo'lishi SHART!
    if "kod" not in lower_text and "kodi" not in lower_text:
        return None

    # Aniq spam/reklama bo'lsa rad etamiz
    for bad in _SPAM_KEYWORDS:
        if bad in lower_text:
            return None

    # 2. Kodni aniqlash
    bot_code = None
    for pattern in _KOD_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            bot_code = f"Kod:{matches[-1]}"
            break

    if not bot_code:
        return None

    raw_lines = text.strip().splitlines()
    result = {
        "title":          None,
        "title_ru":       None,
        "title_en":       None,
        "year":           None,
        "genre":          None,
        "description":    None,
        "bot_code":       bot_code,
        "channel_msg_id": message_id,
    }

    extra = {}
    plain_candidates = []

    for line in raw_lines:
        line = line.strip()
        if not line:
            continue

        if any(skip in line.lower() for skip in ["botimiz", "kanalimiz", "t.me/", "http", "bizning bot"]):
            continue

        # Kod qatorining o'zini nom deb olmaslik
        if re.match(r"(?i)^(?:🔎\s*)?(?:kino\s*)?kod[iı]?\s*[:\-]?\s*\d+$", line):
            continue

        m = _FIELD_RE.match(line)
        if m:
            raw_key = m.group(1).strip()
            val     = m.group(2).strip()
            key     = _normalize_key(raw_key)

            if any(k in key for k in ["kino nomi", "nomi", "film nomi", "title"]):
                if not result["title"]:
                    result["title"] = val
            elif any(k in key for k in ["yili", "yil", "sanasi", "sana", "year"]):
                yr = _YEAR_RE.search(val)
                if yr:
                    result["year"] = int(yr.group())
            elif any(k in key for k in ["tili", "til", "tilida", "tarjima", "dub"]):
                extra["tili"] = val
            elif any(k in key for k in ["janri", "janr", "genre"]):
                extra["janri"] = val
            elif any(k in key for k in ["sifati", "sifat", "farmati", "formati"]):
                extra["sifat"] = val
            elif any(k in key for k in ["davlati", "davlat", "mamlakat", "country"]):
                extra["davlat"] = val
            elif any(k in key for k in ["reyting", "rating", "imdb", "kinopoisk"]):
                extra["reyting"] = val
            continue

        clean = _clean_emojis(line)
        if clean and len(clean) > 2 and not clean.startswith("@"):
            # Sarlavha yoki reklama so'zlari bo'lmasa nom nomzodi sifatida olamiz
            c_low = clean.lower()
            if not any(skip in c_low for skip in [
                "ajoyib premyera", "premyera", "ko'rmagansiz", "kormagansiz",
                "yangi kino yuklandi", "yangi kino", "bugun ko'rishga", "bugun korishga"
            ]):
                plain_candidates.append(clean)

    if not result["title"] and plain_candidates:
        result["title"] = plain_candidates[0]

    if not result["title"]:
        return None

    result["title"] = result["title"].strip(". :–-")

    genres = []
    if extra.get("tili"):
        genres.append(extra["tili"])
    if extra.get("janri"):
        genres.append(extra["janri"])
    if genres:
        result["genre"] = " | ".join(genres)

    desc_parts = []
    if extra.get("sifat"):
        desc_parts.append(f"💽 Sifati: {extra['sifat']}")
    if extra.get("davlat"):
        desc_parts.append(f"🌍 Davlati: {extra['davlat']}")
    if extra.get("reyting"):
        desc_parts.append(f"⭐ Reyting: {extra['reyting']}")
    if desc_parts:
        result["description"] = "\n".join(desc_parts)

    return result
