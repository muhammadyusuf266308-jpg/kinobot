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


def _is_whole_word_match(query: str, title: str) -> bool:
    """
    Qidirilayotgan so'z kino nomida mustaqil so'z sifatida qatnashganligini tekshiradi.
    Masalan:
      query="tor", title="Tor" -> True
      query="tor", title="Tor: Sevgi va Momaqaldiroq" -> True
      query="tor", title="Restorant haqidagi kinoga" -> False! (chunki bu "Restorant" ichidagi harflar)
    """
    if not title:
        return False
    # So'z chegaralari (\b) bo'yicha qidiruv
    pattern = rf"(?i)(?:^|[\s\-_:,\.\(\)\[\]«»'\"/]){re.escape(query)}(?:$|[\s\-_:,\.\(\)\[\]«»'\"/])"
    return bool(re.search(pattern, title))


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
    q = f"%{query_clean}%"
    raw_candidates = []
    try:
        res = client.table("movies").select("*").ilike("title", q).order("year", desc=True).limit(20).execute()
        raw_candidates = res.data or []
    except Exception as e:
        logger.error(f"Qidiruv xatosi (title): {e}")

    # Agar qidiruv 1-2 ta so'zdan iborat bo'lsa, lekin topilmagan bo'lsa:
    if not raw_candidates:
        words = [w for w in re.split(r"[\s\-_:,.]+", query_clean) if len(w) >= 3]
        for w in words[:2]:
            try:
                res_w = client.table("movies").select("*").ilike("title", f"%{w}%").limit(15).execute()
                for r in (res_w.data or []):
                    if not any(x["id"] == r["id"] for x in raw_candidates):
                        raw_candidates.append(r)
            except Exception:
                pass

    if not raw_candidates:
        return []

    # 3. FILTRLASH VA SARALASH (ENG MUHIM QISM):
    # Butun so'z mosligiga qarab darajalarga ajratamiz
    exact_matches = []      # Nom qidiruvga aynan teng bo'lsa (masalan "Tor" == "Tor")
    whole_word_matches = [] # Butun so'z sifatida qatnashgan bo'lsa ("Tor: Sevgi va...")
    partial_matches = []    # Shunchaki ichida harflar qatnashgan bo'lsa ("Restorant...")

    q_lower = query_clean.lower()
    for m in raw_candidates:
        title = m.get("title", "")
        t_lower = title.lower()

        if t_lower == q_lower:
            exact_matches.append(m)
        elif _is_whole_word_match(q_lower, title):
            whole_word_matches.append(m)
        else:
            partial_matches.append(m)

    # Agar aynan yoki butun so'z mosligi topilsa, noto'g'ri qisman so'zlarni (Restorantni) butunlay tashlab yuboramiz!
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
