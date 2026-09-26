# ============================================================
#  database.py  –  Supabase Python client orqali ishlash
#  Aniq va Butun so'zlar bo'yicha mukammal qidiruv (Tor vs Restorant)
# ============================================================
import logging
import re
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

_client: Client = None

def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def init_db():
    try:
        client = get_client()
        client.table("movies").select("id").limit(1).execute()
        logger.info("✅ Supabase ulanish muvaffaqiyatli.")
    except Exception as e:
        logger.error(f"❌ Supabase ulanish xatosi: {e}")


def normalize_title(text: str) -> str:
    """Nomlarni solishtirish uchun tozalash va standartlashtirish"""
    if not text:
        return ""
    # Emojilar va maxsus belgilarni tozalash
    t = re.sub(r"[\U00010000-\U0010ffff\u2600-\u26FF\u2700-\u27BF\U0001F300-\U0001F9FF\U0001FA00-\U0001FA9F\ufe0e\ufe0f]+", "", text)
    # Apostroflarni birlashtirish (o'rgimchak, o‘rgimchak -> o'rgimchak)
    t = re.sub(r"[`ʻʼ’']", "'", t)
    # Tire, defis va tinish belgilarini bo'shliqqa aylantirish
    t = re.sub(r"[\-_–—:.,!?/()\[\]«»\"*~]+", " ", t)
    return re.sub(r"\s+", " ", t).strip().lower()


_STOP_WORDS = {"va", "bilan", "haqida", "kino", "film", "uchun", "degan", "dagi"}


def words_score(query: str, title: str) -> float:
    """
    Ikkita kino nomi o'rtasidagi so'zlar o'xshashlik foizini hisoblaydi.
    Masalan: 'Ajdarho va malika' va 'Malika va Ajdar' -> 1.0 (100%)
    'Tor' va 'Restorant haqidagi kinoga' -> 0.0
    """
    norm_q = normalize_title(query)
    norm_t = normalize_title(title)
    q_words = [w for w in norm_q.split() if len(w) >= 3 and w not in _STOP_WORDS]
    t_words = [w for w in norm_t.split() if len(w) >= 3 and w not in _STOP_WORDS]
    if not q_words or not t_words:
        return 0.0

    def word_similar(w1, w2):
        if w1 == w2:
            return True
        min_len = min(len(w1), len(w2))
        return min_len >= 4 and (w1.startswith(w2[:4]) or w2.startswith(w1[:4]))

    matched = sum(1 for qw in q_words if any(word_similar(qw, tw) for tw in t_words))
    return matched / len(q_words)


def _is_whole_word_match(query: str, title: str) -> bool:
    """
    Qidirilayotgan so'z yoki ibora kino nomida mustaqil so'z sifatida qatnashganligini tekshiradi.
    Masalan:
      query="tor", title="Tor" -> True
      query="tor", title="Tor: Sevgi va Momaqaldiroq" -> True
      query="tor", title="Restorant haqidagi kinoga" -> False!
    """
    if not title or not query:
        return False
    norm_q = normalize_title(query)
    norm_t = normalize_title(title)
    if not norm_q or not norm_t:
        return False
    if norm_q == norm_t:
        return True
    pattern = rf"(?:^|\s){re.escape(norm_q)}(?:$|\s)"
    return bool(re.search(pattern, norm_t))


def search_movie(query: str) -> list[dict]:
    """
    Kino qidiradi.
    1. Kod bo'yicha (masalan "209" yoki "Kod:209")
    2. Aniq butun so'z mosligi bo'yicha ("Tor" faqat "Tor"ni topadi, "Restorant"ni emas!)
    3. To'liq ibora mosligi bo'yicha
    """
    client = get_client()
    query_clean = query.strip()
    if not query_clean:
        return []

    # 1. Kod bo'yicha qidirish (agar faqat raqam yoki Kod:... yozilgan bo'lsa)
    code_match = re.search(r"\b(\d+)\b", query_clean)
    if code_match and len(query_clean) < 15:
        c_num = code_match.group(1)
        try:
            # Aniq shu kodga teng yoki Kod:123
            res_code = client.table("movies").select("*").or_(f"bot_code.eq.Kod:{c_num},bot_code.eq.{c_num}").limit(5).execute()
            if res_code.data:
                return res_code.data[:5]
        except Exception:
            pass

    # 2. Supabase dan nomida shu harflar qatnashgan kinolarni tortib olamiz
    # Apostroflarning barcha turlarini (' ` ʻ ʼ ’) SQL '_' belgisi orqali qamrab olamiz
    norm_q = normalize_title(query_clean)
    sql_q = re.sub(r"[`ʻʼ’']", "_", query_clean)
    q = f"%{sql_q}%"
    raw_candidates = []
    try:
        res = client.table("movies").select("*").or_(f"title.ilike.{q},title_ru.ilike.{q},title_en.ilike.{q}").order("year", desc=True).limit(25).execute()
        raw_candidates = res.data or []
    except Exception as e:
        logger.error(f"Qidiruv xatosi (title): {e}")

    # Agar qidiruv bir nechta so'zdan iborat bo'lsa va hali topilmagan bo'lsa:
    words = [w for w in norm_q.split() if len(w) >= 3 and w not in _STOP_WORDS]
    if len(raw_candidates) < 5 and words:
        for w in words[:3]:
            stem = w[:5] if len(w) >= 5 else w
            try:
                res_w = client.table("movies").select("*").or_(f"title.ilike.%{stem}%,title_ru.ilike.%{stem}%,title_en.ilike.%{stem}%").limit(15).execute()
                for r in (res_w.data or []):
                    if not any(x["id"] == r["id"] for x in raw_candidates):
                        raw_candidates.append(r)
            except Exception:
                pass

    if not raw_candidates:
        return []

    # 3. FILTRLASH VA SARALASH:
    exact_matches = []      # Nom qidiruvga aynan teng bo'lsa (masalan "Tor" == "Tor")
    whole_word_matches = [] # Butun so'z yoki so'zlar tarkibi mos kelsa ("Malika va Ajdar" == "Ajdarho va malika")
    partial_matches = []    # Faqat 5+ harfli so'zlarda qisman moslik ("Titanik" -> "Titanik 2")

    for m in raw_candidates:
        title = m.get("title", "")
        norm_t = normalize_title(title)

        if norm_t == norm_q:
            exact_matches.append(m)
        elif _is_whole_word_match(query_clean, title) or words_score(query_clean, title) >= 0.6:
            whole_word_matches.append(m)
        elif len(norm_q) >= 5 and norm_q in norm_t:
            partial_matches.append(m)

    # Agar aynan yoki butun so'z mosligi topilsa, noto'g'ri qisman so'zlarni butunlay tashlab yuboramiz
    if exact_matches or whole_word_matches:
        results = exact_matches + whole_word_matches
    else:
        results = partial_matches

    # ID bo'yicha dublikatlarni olib tashlaymiz
    unique_results = []
    seen = set()
    for r in results:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique_results.append(r)

    return unique_results[:5]


def add_movie(title: str, bot_code: str,
              title_ru: str = None, title_en: str = None,
              year: int = None, genre: str = None,
              description: str = None,
              channel_msg_id: int = None) -> int:
    client = get_client()

    data = {
        "title":          title,
        "title_ru":       title_ru,
        "title_en":       title_en,
        "year":           year,
        "genre":          genre,
        "description":    description,
        "bot_code":       bot_code,
        "channel_msg_id": channel_msg_id,
    }

    try:
        res = (
            client.table("movies")
            .upsert(data, on_conflict="bot_code")
            .execute()
        )
        new_id = res.data[0]["id"] if res.data else 0
        logger.info(f"🎬 Saqlandi: '{title}' → {bot_code} (ID={new_id})")
        return new_id
    except Exception as e:
        logger.error(f"add_movie xatosi: {e}")
        raise


def movie_exists_by_code(bot_code: str) -> bool:
    client = get_client()
    try:
        res = (
            client.table("movies")
            .select("id")
            .eq("bot_code", bot_code)
            .limit(1)
            .execute()
        )
        return len(res.data) > 0
    except Exception as e:
        logger.error(f"movie_exists xatosi: {e}")
        return False


def log_search(user_id: int, username: str, full_name: str,
               query: str, found: bool):
    client = get_client()
    try:
        client.table("search_log").insert({
            "user_id":   user_id,
            "username":  username,
            "full_name": full_name,
            "query":     query,
            "found":     found,
        }).execute()
    except Exception as e:
        logger.error(f"log_search xatosi: {e}")


def get_all_movies() -> list[dict]:
    client = get_client()
    try:
        res = (
            client.table("movies")
            .select("id, title, title_ru, year, genre, bot_code")
            .order("id", desc=True)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error(f"get_all_movies xatosi: {e}")
        return []


def delete_movie(movie_id: int) -> bool:
    client = get_client()
    try:
        res = (
            client.table("movies")
            .delete()
            .eq("id", movie_id)
            .execute()
        )
        return len(res.data) > 0
    except Exception as e:
        logger.error(f"delete_movie xatosi: {e}")
        return False


def get_stats() -> dict:
    client = get_client()
    try:
        total_movies   = client.table("movies").select("id", count="exact").execute().count or 0
        total_searches = client.table("search_log").select("id", count="exact").execute().count or 0
        found_count    = client.table("search_log").select("id", count="exact").eq("found", True).execute().count or 0
        not_found      = client.table("search_log").select("id", count="exact").eq("found", False).execute().count or 0
    except Exception as e:
        logger.error(f"get_stats xatosi: {e}")
        total_movies = total_searches = found_count = not_found = 0

    return {
        "total_movies":   total_movies,
        "total_searches": total_searches,
        "found_count":    found_count,
        "not_found":      not_found,
    }


# ─── Admin boshqaruvi ──────────────────────────────────────────

_ADMINS_FILE = "admins.json"


def _load_local_admins() -> list[dict]:
    import json, os
    if os.path.exists(_ADMINS_FILE):
        try:
            with open(_ADMINS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_local_admins(admins: list[dict]):
    import json
    try:
        with open(_ADMINS_FILE, "w", encoding="utf-8") as f:
            json.dump(admins, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Admins saqlash xatosi: {e}")


def get_all_admins() -> list[dict]:
    """Barcha adminlarni oladi (Supabase 'bot_admins' yoki mahalliy JSON)"""
    client = get_client()
    try:
        res = client.table("bot_admins").select("*").order("id", desc=False).execute()
        return res.data or []
    except Exception:
        return _load_local_admins()


def is_user_admin(user_id: int, super_admin_id: int) -> bool:
    """Foydalanuvchi super admin yoki qo'shimcha admin ekanligini tekshiradi"""
    if user_id == super_admin_id:
        return True
    admins = get_all_admins()
    return any(int(a.get("user_id", 0)) == int(user_id) for a in admins)


def add_new_admin(user_id: int, username: str = None, full_name: str = None, added_by: int = None) -> bool:
    """Yangi admin qo'shadi"""
    client = get_client()
    data = {
        "user_id": user_id,
        "username": username or "",
        "full_name": full_name or "",
        "added_by": added_by
    }
    # 1. Supabase urinishi
    try:
        res = client.table("bot_admins").upsert(data, on_conflict="user_id").execute()
        if res.data:
            return True
    except Exception as e:
        logger.warning(f"Supabase bot_admins ga yozib bo'lmadi, JSON ga saqlanadi: {e}")

    # 2. Mahalliy JSON zaxira
    local = _load_local_admins()
    for a in local:
        if int(a.get("user_id", 0)) == int(user_id):
            a.update(data)
            _save_local_admins(local)
            return True
    local.append(data)
    _save_local_admins(local)
    return True


def remove_admin(user_id: int) -> bool:
    """Adminni o'chiradi"""
    client = get_client()
    try:
        client.table("bot_admins").delete().eq("user_id", user_id).execute()
    except Exception:
        pass

    local = _load_local_admins()
    new_local = [a for a in local if int(a.get("user_id", 0)) != int(user_id)]
    _save_local_admins(new_local)
    return True



def get_random_movie() -> dict | None:
    """Tasodifiy bitta kino qaytaradi"""
    import random
    client = get_client()
    try:
        res = client.table("movies").select("*").execute()
        data = res.data or []
        return random.choice(data) if data else None
    except Exception as e:
        logger.error(f"get_random_movie xatosi: {e}")
        return None


GENRE_SYNONYMS = {
    "horror": ["horror", "ujas", "daxshat", "dahshat", "qorqinchli", "qo'rqinchli", "qõrqinchli"],
    "dahshat": ["horror", "ujas", "daxshat", "dahshat", "qorqinchli", "qo'rqinchli", "qõrqinchli"],
    "jangari": ["jangari", "boevik", "action"],
    "fantastika": ["fantastik", "fentezi", "fantasy", "sci-fi"],
    "komediya": ["komedi", "kamedi", "comedy"],
    "multfilm": ["mult", "animatsiya", "animation", "ertak"],
    "sevgi": ["sevgi", "romantik", "ramantik", "melodrama"],
    "triller": ["triller", "thriller", "detektiv"],
    "tarix": ["tarix", "tarixiy", "biografiya", "harbiy"],
    "oilaviy": ["oilaviy", "sarguzasht"],
    "drama": ["drama", "dramma"],
}


def get_movies_by_genre(genre_keyword: str, limit: int = 8) -> list[dict]:
    """Janr bo'yicha kinolarni kengaytirilgan sinonimlar bilan qaytaradi"""
    client = get_client()
    kw_clean = genre_keyword.strip().lower()
    search_terms = GENRE_SYNONYMS.get(kw_clean, [kw_clean])

    results = []
    seen = set()
    try:
        # Har bir sinonim bo'yicha qidirib, birlashtiramiz
        for term in search_terms:
            res = (
                client.table("movies")
                .select("*")
                .ilike("genre", f"%{term}%")
                .limit(limit)
                .execute()
            )
            for m in (res.data or []):
                if m["id"] not in seen:
                    seen.add(m["id"])
                    results.append(m)
            if len(results) >= limit:
                break
        return results[:limit]
    except Exception as e:
        logger.error(f"get_movies_by_genre xatosi: {e}")
        return []


def get_top_movies(limit: int = 10) -> list[dict]:
    """Eng so'nggi qo'shilgan kinolarni (Top) qaytaradi"""
    client = get_client()
    try:
        res = (
            client.table("movies")
            .select("*")
            .order("id", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error(f"get_top_movies xatosi: {e}")
        return []


def get_similar_movies(movie_id: int, genre: str = None, title: str = None, limit: int = 4) -> list[dict]:
    """O'xshash kinolarni topadi (janr yoki nom bo'yicha)"""
    client = get_client()
    results = []
    try:
        if genre:
            genre_word = genre.split()[0].strip("#") if genre else ""
            if genre_word and len(genre_word) >= 3:
                res = (
                    client.table("movies")
                    .select("*")
                    .ilike("genre", f"%{genre_word}%")
                    .neq("id", movie_id)
                    .limit(limit + 2)
                    .execute()
                )
                results.extend(res.data or [])

        if len(results) < limit and title:
            words = [w for w in normalize_title(title).split() if len(w) >= 4]
            for word in words[:2]:
                res_w = (
                    client.table("movies")
                    .select("*")
                    .ilike("title", f"%{word}%")
                    .neq("id", movie_id)
                    .limit(limit)
                    .execute()
                )
                for r in (res_w.data or []):
                    if not any(x["id"] == r["id"] for x in results):
                        results.append(r)
                if len(results) >= limit:
                    break
    except Exception as e:
        logger.error(f"get_similar_movies xatosi: {e}")

    seen = set()
    unique = []
    for r in results:
        if r["id"] not in seen and r["id"] != movie_id:
            seen.add(r["id"])
            unique.append(r)

    # Agar o'xshash topilmasa, bazadagi boshqa mashhur kinolardan to'ldiramiz
    if len(unique) < limit:
        try:
            fallbacks = get_top_movies(limit + 5)
            for fb in fallbacks:
                if fb["id"] not in seen and fb["id"] != movie_id:
                    seen.add(fb["id"])
                    unique.append(fb)
                if len(unique) >= limit:
                    break
        except Exception:
            pass

    return unique[:limit]


def get_most_searched(limit: int = 10) -> list[dict]:
    """Eng ko'p qidirilgan so'rovlar statistikasi"""
    client = get_client()
    try:
        res = (
            client.table("search_log")
            .select("query")
            .eq("found", True)
            .order("id", desc=True)
            .limit(500)
            .execute()
        )
        queries = [r["query"] for r in (res.data or [])]
        counts: dict[str, int] = {}
        for q in queries:
            q_norm = q.strip().lower()
            if len(q_norm) >= 2:
                counts[q_norm] = counts.get(q_norm, 0) + 1
        sorted_q = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [{"query": q, "count": c} for q, c in sorted_q[:limit]]
    except Exception as e:
        logger.error(f"get_most_searched xatosi: {e}")
        return []
