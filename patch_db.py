import re

with open('database.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update add_movie signature
text = re.sub(
    r'def add_movie\(title: str, bot_code: str,[\s\S]*?channel_msg_id: int = None\) -> int:',
    'def add_movie(title: str, bot_code: str, title_ru: str = None, title_en: str = None, year: int = None, genre: str = None, description: str = None, channel_msg_id: int = None, poster_url: str = None, tmdb_rating: str = None) -> int:',
    text
)
# 2. Add poster_url and tmdb_rating to data dict
text = text.replace(
    '        "channel_msg_id": channel_msg_id,\n    }',
    '        "channel_msg_id": channel_msg_id,\n        "poster_url": poster_url,\n        "tmdb_rating": tmdb_rating,\n    }'
)
# 3. Update add_movies_bulk fields
text = text.replace(
    '"description", "bot_code", "channel_msg_id")',
    '"description", "bot_code", "channel_msg_id", "poster_url", "tmdb_rating")'
)

# 4. Add Watchlist functions
watchlist_funcs = '''
def add_favorite(user_id: int, movie_id: int) -> bool:
    try:
        client = get_client()
        client.table("favorites").insert({"user_id": user_id, "movie_id": movie_id}).execute()
        return True
    except Exception as e:
        logger.error(f"add_favorite error: {e}")
        return False

def remove_favorite(user_id: int, movie_id: int) -> bool:
    try:
        client = get_client()
        client.table("favorites").delete().eq("user_id", user_id).eq("movie_id", movie_id).execute()
        return True
    except Exception as e:
        logger.error(f"remove_favorite error: {e}")
        return False

def get_user_favorites(user_id: int) -> list[dict]:
    try:
        client = get_client()
        res = client.table("favorites").select("movie_id, movies(*)").eq("user_id", user_id).execute()
        if res and res.data:
            return [row["movies"] for row in res.data if row.get("movies")]
    except Exception as e:
        logger.error(f"get_user_favorites error: {e}")
    return []
'''
text += watchlist_funcs

with open('database.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Done patching database.py")
