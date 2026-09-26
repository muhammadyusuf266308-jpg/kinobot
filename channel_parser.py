# ============================================================
#  channel_parser.py  –  Haqiqiy Kino Postlarini Aniq Tanuvchi Parser
#  Ko'p kinoli ro'yxatlar va barcha formatlarni qo'llab-quvvatlaydi
# ============================================================
import re
import logging

logger = logging.getLogger(__name__)

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

# Aniq kod qidiruv:
# "Kino kodi: 226", "Film kodi: 110", "Kino kodi; 214", "<<205>> kodini", "`110`", "🆔 Film kodi: 244", "Kodi: 243", "Kod: 234"
_KOD_PATTERNS = [
    re.compile(r"(?i)(?:🆔\s*|🔎\s*|🔰\s*|📌\s*)?(?:kino|film|kinolar|serial)?\s*k[io]d[iı]?\s*[:;\-–—]?\s*[`*\"'\s]*(\d{1,5})"),
    re.compile(r"(?i)\bk[io]d[iı]?\s*[:;\-–—]?\s*[`*\"'\s]*(\d{1,5})"),
    re.compile(r"(?i)(?:<<|`|\b)(\d{1,5})(?:>>|`|\b)\s*(?:kodini|kodi|kod)"),
    re.compile(r"(?i)\bcode\s*[:;\-–—]?\s*[`*\"'\s]*(\d{1,5})"),
]

# Ro'yxat formati qatori: masalan "127 — 📺Tor" yoki "147 - Momaqaldiroqlar" yoki "№124. Qasoskorlar"
_LIST_LINE_RE = re.compile(r"^(?:№\s*)?(\d{1,5})\s*[\.\-—–:]\s*(.+)$")

# Reklama va oddiy gaplarni aniqlovchi filtr (faqat aniq no-kino postlar uchun)
_SPAM_KEYWORDS = [
    "kanal sotiladi", "open budget", "ovoz bering", "ovoz olamiz",
    "arzonga bervoraman", "dangal oladiganlar"
]

_FIELD_RE = re.compile(
    r"^(?:[\U00010000-\U0010ffff\u2600-\u26FF\u2700-\u27BF"
    r"\U0001F300-\U0001F9FF\U0001FA00-\U0001FA9F"
    r"\U00002702-\U000027B0\U0001F1E0-\U0001F1FF\ufe0e\ufe0f]*\s*)?"
    r"([^:\n]{1,30}):\s*(.+)$"
)

# Sarlavha bo'la olmaydigan umumiy e'lon / chaqiruv iboralari
_IGNORE_PHRASES = [
    "ajoyib premyera", "premyera", "ko'rmagansiz", "kormagansiz",
    "yangi kino yuklandi", "yangi kino", "bugun ko'rishga", "bugun korishga",
    "kechga ko'rishga zo'r kino", "kechga korishga zor kino", "kechga koʻrishga zoʻr kino",
    "mualiflik huquqi", "mualliflik huquqi", "kanalga joylamadik", "kutgan premyera", "barcha kutgan",
    "botga joyladik", "botimizda",
    "reaksiya bilan", "reaksiyani", "reaksiya yig'ib", "reaksiya yigʻib",
    "sizga albatta yoqadi", "imdb da", "kinopoisk da",
    "shu kinoni botga joyladik", "instagramni portlatgan kino",
]


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


def _clean_title_candidate(title: str) -> str:
    """Nomdan ortiqcha yuklandi, skachat, full hd, barcha qismlar, qavslarni chiroyli tozalaydi"""
    if not title:
        return ""
    t = _clean_emojis(title).strip(". :–- ")
    # Qo'shtirnoqlar bilan o'ralgan bo'lsa
    q_match = re.search(r'["«“]([^"»”]+)["»”]', t)
    if q_match and len(q_match.group(1).strip()) >= 3:
        inside = q_match.group(1).strip()
        if not any(bad in inside.lower() for bad in ["ajdar uyi ning", "sababli"]):
            t = inside

    # "Astral filmining (men topgan )barcha qismi" -> "Astral"
    t = re.sub(r"(?i)\s*(?:filmining|filmi|kinoning|kino)?\s*(?:\([^)]*\)\s*)?barcha\s*qism[a-z]*.*", "", t)
    # "Liger Uzbek tilida 2022 O'zbekcha tarjima film Full HD skachat" -> "Liger"
    t = re.sub(r"(?i)\s+(?:uzbek|o['ʻʼ`]zbek|rus|ingliz|turk|koreys)?\s*(?:tilida|cha)?\s*(?:tarjima)?\s*(?:film|kino|serial)?\s*(?:full\s*hd|hd|skachat|yuklab\s*olish|onlayn|online|\d{4}).*", "", t)
    t = re.sub(r"(?i)\s+(?:full\s*hd|hd|skachat|yuklab\s*olish|onlayn|online).*", "", t)
    t = re.sub(r"(?i)\s+filmi\b", "", t)
    return t.strip(". :–- ")


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
            raw_t = _clean_emojis(m.group(2)).strip(". :–- ")
            title = _clean_title_candidate(raw_t)
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
    Har xil post turlarini (Nomi: ..., 🎬 Kino, PREMYERA "Nom", Kodi: ...) to'liq taniydi.
    """
    if not text or len(text.strip()) < 8:
        return None

    # Markdown belgilarini tozalash (*, _, `, ~)
    text = re.sub(r"[*_`~]", "", text)
    lower_text = text.lower()

    # 1. Post matnida kod/kodi/kodini/code so'zi bo'lishi tekshiriladi
    if not re.search(r"(?i)\b(?:k[io]d[a-z]*|code)\b|k[io]d[:;\-–—]", text):
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
    quoted_candidates = []

    for line in raw_lines:
        line = line.strip()
        if not line:
            continue

        if any(skip in line.lower() for skip in ["botimiz", "kanalimiz", "t.me/", "http", "bizning bot"]):
            continue

        # Kod qatorining o'zini nom deb olmaslik
        if re.search(r"(?i)(?:🆔\s*|🔎\s*|🔰\s*|📌\s*)?(?:kino|film|kinolar|serial)?\s*k[io]d[iı]?", line) or re.search(r"(?i)\bk[io]d\b", line):
            continue

        # Qo'shtirnoq ichidagi nom nomzodlari (masalan: "Malika va Ajdar")
        q_matches = re.findall(r'["«“]([^"»”]{2,50})["»”]', line)
        for qm in q_matches:
            c_qm = _clean_emojis(qm).strip()
            if c_qm and len(c_qm) >= 3 and not any(ign in c_qm.lower() for ign in ["ajdar uyi ning", "sababli", "kanalga"]):
                quoted_candidates.append(c_qm)

        m = _FIELD_RE.match(line)
        # Agar bitta qatorda bir nechta maydon bo'lsa (masalan: "🎙 Til: O'zbek | 📅 Yil: 2024")
        if "|" in line:
            subparts = [p.strip() for p in line.split("|") if p.strip()]
        else:
            subparts = [line]

        matched_field = False
        for part in subparts:
            mp = _FIELD_RE.match(part)
            if mp and len(mp.group(1).strip().split()) <= 2:
                raw_key = mp.group(1).strip()
                val     = mp.group(2).strip()
                key     = _normalize_key(raw_key)

                if any(k in key for k in ["kinopoisk", "imdb", "reyting", "rating"]):
                    extra["reyting"] = val
                    matched_field = True
                elif any(k in key for k in ["kino nomi", "serial nomi", "nomi", "film nomi", "title"]):
                    clean_v = _clean_title_candidate(val)
                    if clean_v and len(clean_v) > 1 and not any(skip in clean_v.lower() for skip in ["botimiz", "kanalimiz", "http"]):
                        result["title"] = clean_v
                    matched_field = True
                elif any(k in key for k in ["yili", "yil", "sanasi", "sana", "year"]):
                    yr = _YEAR_RE.search(val)
                    if yr:
                        result["year"] = int(yr.group())
                    matched_field = True
                elif any(k in key for k in ["tili", "til", "tilida", "tarjima", "dub"]):
                    extra["tili"] = val
                    matched_field = True
                elif any(k in key for k in ["janri", "janr", "genre"]):
                    extra["janri"] = val
                    matched_field = True
                elif any(k in key for k in ["sifati", "sifat", "farmati", "formati"]):
                    extra["sifat"] = val
                    matched_field = True
                elif any(k in key for k in ["davlati", "davlat", "mamlakat", "country"]):
                    extra["davlat"] = val
                    matched_field = True

        if matched_field:
            continue

        clean = _clean_emojis(line)
        if clean and len(clean) > 2 and not clean.startswith("@"):
            c_low = clean.lower()
            if not any(skip in c_low for skip in _IGNORE_PHRASES):
                plain_candidates.append(clean)

    # Agar explicit nomi maydoni bo'lmasa:
    if not result["title"]:
        # 1. Qo'shtirnoq ichidagi nom bo'lsa
        if quoted_candidates:
            result["title"] = _clean_title_candidate(quoted_candidates[0])
        # 2. Oddiy toza qatorlardan qidiramiz
        elif plain_candidates:
            result["title"] = _clean_title_candidate(plain_candidates[0])

    if not result["title"]:
        return None

    result["title"] = _clean_title_candidate(result["title"])

    # Agar nom ichida yil bo'lsa va year hali belgilanmagan bo'lsa, yilni ajratib olamiz
    if not result["year"]:
        yr_m = _YEAR_RE.search(result["title"])
        if yr_m:
            result["year"] = int(yr_m.group())

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
