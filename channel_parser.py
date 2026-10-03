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



# ── Qo'shimcha format qoidalari ──────────────────────────────

# "🎬 ➺ Lutsifer" kabi strelka bilan yozilgan qatorlar
_ARROW_RE = re.compile(r"^[^\w\n]*?[➺➔➜➤➞➡→⇒»▶►]+\s*(\S.*)$")
_SEASON_RE = re.compile(r"(?i)^\d{1,2}\s*[-–]?\s*(?:fasl|mavsum|sezon|season|qism|part)\w*$")
_LANG_RE = re.compile(r"(?i)\btil(?:i|ida)?\b|o['ʻʼ`’]?zbek|uzbek|\brus\b|ingliz|turk|koreys|hind|sinxron")
_COUNTRY_RE = re.compile(r"(?i)^(.*?)\s*\b(?:filmi|serial[i]?|multfilm[i]?|animatsiya)\b$")
_GENRE_WORDS = (
    "jangari", "fantastik", "drama", "komedi", "triller", "horror", "dahshat", "ujas",
    "melodrama", "sarguzasht", "detektiv", "tarix", "biograf", "harbiy", "multfilm",
    "oilaviy", "romantik", "sevgi", "kriminal", "mistik", "fentezi", "anime",
)

# "(@kanal_nomi)" yoki "@kanal_nomi" - alohida kanal havolasi
_USERNAME_RE = re.compile(r"@([A-Za-z][A-Za-z0-9_]{3,31})")

# Nom bo'la olmaydigan e'lon so'zlari (faqat nomi bor postlar uchun qattiqroq filtr)
_NAME_ONLY_BAD = [
    "obuna", "reklama", "konkurs", "ovoz", "reaksiya", "kanalimiz", "sotiladi",
    "murojaat", "yutuq", "sovg'a", "sovga", "aksiya", "donat", "karta",
    "diqqat", "e'lon", "elon", "rahmat", "tabrik", "bayram",
]

_PLACEHOLDER_PREFIX = "Kino #"


def is_placeholder_title(title: str) -> bool:
    return bool(title) and title.startswith(_PLACEHOLDER_PREFIX)


def _strip_leading_symbols(t: str) -> str:
    """Nom boshidagi ▌, |, -, nuqta kabi belgilarni olib tashlaydi."""
    return re.sub(r"^[\W_]+", "", t, flags=re.UNICODE).strip()


def _clean_media_name(name: str | None) -> str:
    """Video fayl nomidan (masalan 'Yetti_qirollik_ritsari_720p.mp4') kino nomini ajratadi."""
    if not name:
        return ""
    t = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", name)
    t = re.sub(r"[_.]+", " ", t)
    t = re.sub(r"(?i)\b(?:\d{3,4}p|hd|full\s*hd|uzkinomovie|uzbek|o'zbek|tilida|skachat|1080|720|480)\b", " ", t)
    t = re.sub(r"(?i)@\w+", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" -–")
    return t if len(t) >= 3 and not t.isdigit() else ""


def _split_aliases(raw: str) -> tuple[str, str | None]:
    """'Shelbylar oilasi | Thomas Shelby' -> ('Shelbylar oilasi', 'Thomas Shelby')"""
    parts = [p.strip() for p in re.split(r"\s*[|/]\s*", raw) if p.strip()]
    if not parts:
        return raw.strip(), None
    return parts[0], (" / ".join(parts[1:]) or None)


def _parse_link_list(text: str, message_id: int | None) -> list[dict]:
    """
    Nom + alohida kanal havolasi ro'yxati (kodsiz):
        Chuqur 👇
        (@chuqur_serial_uzbek_t1lida)
    Har biri alohida yozuv bo'ladi (bot_code = 'Link:<username>').
    Nom - havola qatoridan oldingi oxirgi matn bloki (bo'sh qator bloklarni ajratadi).
    """
    entries: list[dict] = []
    seen: set[str] = set()
    block: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            # bo'sh qator: blok yopiladi, lekin havola qatori hali kelishi mumkin
            if block:
                block.append("\n")
            continue

        um = _USERNAME_RE.search(line)
        rest = _clean_emojis(_USERNAME_RE.sub("", line)).strip(" ()[]:-–—•")
        if um and not rest:
            # eng oxirgi to'liq blokni olamiz (bo'sh qatordan keyingi)
            parts = " ".join(block).split("\n")
            parts = [p.strip() for p in parts if p.strip()]
            name_raw = _strip_leading_symbols(parts[-1]) if parts else ""
            uname = um.group(1)
            if name_raw and uname.lower() not in seen and not uname.lower().endswith("bot"):
                title, alt = _split_aliases(name_raw)
                title = title.strip(" .:–-")
                if len(title) >= 2:
                    seen.add(uname.lower())
                    entries.append({
                        "title": title,
                        "title_ru": None,
                        "title_en": alt,
                        "year": None,
                        "genre": None,
                        "description": f"🔗 Alohida kanal: @{uname}",
                        "bot_code": f"Link:{uname}",
                        "channel_msg_id": message_id,
                    })
            block = []
        else:
            cleaned = _clean_emojis(line)
            if cleaned:
                # oldingi blok yopilgan bo'lsa (orada "\n" bor) yangisini boshlaymiz
                if block and block[-1] == "\n":
                    block = []
                block.append(cleaned)
    return entries


def _new_entry(title, code, message_id, **kw) -> dict:
    d = {"title": title, "title_ru": None, "title_en": None, "year": None,
         "genre": None, "description": None, "bot_code": code,
         "channel_msg_id": message_id}
    d.update(kw)
    return d


def _list_item_ok(title: str) -> bool:
    return bool(title) and len(title) > 1 and not any(
        skip in title.lower() for skip in ["botimiz", "kanalimiz", "http", "t.me"])


def parse_post_multiple(text: str, message_id: int = None,
                        has_media: bool = False, media_name: str | None = None) -> list[dict]:
    """
    Postdan bir yoki bir nechta kinoni ajratadi. Qo'llab-quvvatlanadigan turlar:
      1) Kodli + nomli oddiy post            -> bot_code = Kod:123
      2) Kod-nom ro'yxati (ko'p kinoli)      -> har biri Kod:N (nomi 2 qatorga o'tsa ham)
      3) Nom + alohida kanal havolasi ro'yxati -> bot_code = Link:<username>
      4) Faqat kodi bor post (nomi yo'q)     -> sarlavha "Kino #123" (yoki video fayl nomi)
      5) Faqat nomi bor media post (kodsiz)  -> bot_code = Post:<post_id> (kanaldagi postga havola)
    """
    if not text or len(text.strip()) < 5:
        return []

    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]

    # 2) Kod - nom ro'yxati
    list_items: list[dict] = []
    last: dict | None = None
    for idx, line in enumerate(lines):
        clean_l = _clean_emojis(line)
        m = _LIST_LINE_RE.match(clean_l)
        if m:
            code_num = m.group(1).strip()
            raw_t = _strip_leading_symbols(_clean_emojis(m.group(2)).strip(". :–- "))
            title = _clean_title_candidate(raw_t)
            if _list_item_ok(title):
                last = _new_entry(title, f"Kod:{code_num}", message_id)
                list_items.append(last)
            else:
                last = None
            continue

        # Nom keyingi qatorga o'tib ketgan bo'lsa ("Shang-Chi: O'nta" / "Uzuk Afsonasi"):
        # keyingi qator yana ro'yxat elementi bo'lsa, bu qator oldingi nomning davomi.
        if (last is not None and clean_l and len(clean_l) <= 45
                and idx + 1 < len(lines)
                and _LIST_LINE_RE.match(_clean_emojis(lines[idx + 1]))
                and not re.search(r"(?i)k[io]d|bot\b|t\.me|http|@", clean_l)):
            last["title"] = _clean_title_candidate(f"{last['title']} {clean_l}")

    if len(list_items) >= 2:
        return list_items

    # 3) Nom + kanal havolasi ro'yxati
    link_items = _parse_link_list(text, message_id)
    if len(link_items) >= 2:
        return link_items

    # 1, 4, 5) Yakka post
    single = parse_post(text, message_id, has_media=has_media, media_name=media_name)
    return [single] if single else []


def _arrow_fields(raw_lines: list[str]) -> dict:
    """'🎬 ➺ Lutsifer' / '🎞 ➺ 1-Fasl' / '🇺🇿 ➺ O'zbek Tilida' ... qatorlaridan maydonlarni ajratadi."""
    vals = []
    for line in raw_lines:
        m = _ARROW_RE.match(line.strip())
        if m:
            v = _clean_emojis(m.group(1)).strip(" .")
            if v:
                vals.append(v)
    if not vals:
        return {}

    out: dict = {"title": _clean_title_candidate(vals[0]), "season": None,
                 "tili": None, "davlat": None, "janri": None}
    for v in vals[1:]:
        low = v.lower()
        if _SEASON_RE.match(v) and not out["season"]:
            out["season"] = v
        elif _LANG_RE.search(v) and not out["tili"]:
            out["tili"] = v
        elif _COUNTRY_RE.match(v) and not out["davlat"]:
            out["davlat"] = (_COUNTRY_RE.match(v).group(1) or v).strip() or v
        elif (any(g in low for g in _GENRE_WORDS) or "," in v) and not out["janri"]:
            out["janri"] = v
    return out


def parse_post(text: str, message_id: int = None,
               has_media: bool = False, media_name: str | None = None) -> dict | None:
    """
    Bitta kino postini tahlil qiladi (kodli, strelkali, faqat kodli yoki faqat nomli).
    """
    if not text or len(text.strip()) < 3:
        return None

    text = re.sub(r"[*_`~]", "", text)
    lower_text = text.lower()

    for bad in _SPAM_KEYWORDS:
        if bad in lower_text:
            return None

    # ── Kodni aniqlash ───────────────────────────────────────
    bot_code = None
    if re.search(r"(?i)\b(?:k[io]d[a-z]*|code)\b|k[io]d[:;\-–—]", text):
        for pattern in _KOD_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                bot_code = f"Kod:{matches[-1]}"
                break

    # Kodsiz post faqat media (video/rasm) bo'lsa va qisqa, toza nom bo'lsa qabul qilinadi
    name_only = False
    if not bot_code:
        if not (has_media and message_id):
            return None
        if len(text) > 300 or len(text.splitlines()) > 8:
            return None
        if any(bad in lower_text for bad in _NAME_ONLY_BAD):
            return None
        name_only = True
        bot_code = f"Post:{message_id}"

    raw_lines = text.strip().splitlines()
    result = _new_entry(None, bot_code, message_id)
    extra: dict = {}
    plain_candidates: list[str] = []
    quoted_candidates: list[str] = []

    arrow = _arrow_fields(raw_lines)

    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        low_line = line.lower()
        if any(skip in low_line for skip in ["botimiz", "kanalimiz", "t.me/", "http", "bizning bot"]):
            continue
        if _ARROW_RE.match(line):
            continue  # strelkali qatorlar _arrow_fields da ishlangan
        if re.search(r"(?i)(?:🆔\s*|🔎\s*|🔰\s*|📌\s*)?(?:kino|film|kinolar|serial)?\s*k[io]d[iı]?", line) \
                or re.search(r"(?i)\bk[io]d\b", line):
            continue

        for qm in re.findall(r'["«“]([^"»”]{2,50})["»”]', line):
            c_qm = _clean_emojis(qm).strip()
            if c_qm and len(c_qm) >= 3 and not any(
                    ign in c_qm.lower() for ign in ["ajdar uyi ning", "sababli", "kanalga"]):
                quoted_candidates.append(c_qm)

        subparts = [p.strip() for p in line.split("|") if p.strip()] if "|" in line else [line]
        matched_field = False
        for part in subparts:
            mp = _FIELD_RE.match(part)
            if mp and len(mp.group(1).strip().split()) <= 2:
                raw_key = mp.group(1).strip()
                val = mp.group(2).strip()
                key = _normalize_key(raw_key)
                if any(k in key for k in ["kinopoisk", "imdb", "reyting", "rating"]):
                    extra["reyting"] = val
                    matched_field = True
                elif any(k in key for k in ["kino nomi", "serial nomi", "nomi", "film nomi", "title"]):
                    clean_v = _clean_title_candidate(val)
                    if clean_v and len(clean_v) > 1 and not any(
                            skip in clean_v.lower() for skip in ["botimiz", "kanalimiz", "http"]):
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

        clean = _strip_leading_symbols(_clean_emojis(line))
        if clean and len(clean) > 2 and not clean.startswith("@") and "@" not in clean:
            if not any(skip in clean.lower() for skip in _IGNORE_PHRASES):
                plain_candidates.append(clean)

    # ── Sarlavhani tanlash ───────────────────────────────────
    if arrow.get("title"):
        result["title"] = arrow["title"]
        if arrow.get("season"):
            result["title"] = f"{result['title']} {arrow['season']}"
        for k in ("tili", "davlat", "janri"):
            if arrow.get(k) and not extra.get(k):
                extra[k] = arrow[k]

    if not result["title"]:
        if quoted_candidates:
            result["title"] = _clean_title_candidate(quoted_candidates[0])
        else:
            # Gapga o'xshash uzun qatorlar nom bo'la olmaydi
            for cand in plain_candidates:
                if len(cand.split()) <= (6 if name_only else 9) and not cand.endswith((".", "?", "!")):
                    result["title"] = _clean_title_candidate(cand)
                    break

    if not result["title"]:
        if name_only:
            return None  # nom ham, kod ham yo'q - kino posti emas
        # Kodi bor, nomi yo'q: video fayl nomi yoki "Kino #123"
        n = re.sub(r"[^\d]", "", bot_code)
        result["title"] = _clean_media_name(media_name) or f"{_PLACEHOLDER_PREFIX}{n}"

    result["title"] = _clean_title_candidate(result["title"]) or result["title"]

    if not result["year"]:
        yr_m = _YEAR_RE.search(result["title"])
        if yr_m:
            result["year"] = int(yr_m.group())

    genres = [extra[k] for k in ("tili", "janri") if extra.get(k)]
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
