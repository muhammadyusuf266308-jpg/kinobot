with open('bot.py', 'r', encoding='utf-8') as f:
    text = f.read()

if 'from tmdb_service import fetch_movie_details' not in text:
    text = text.replace('from database import ', 'from tmdb_service import fetch_movie_details\nfrom database import ')

old_block = """        add_movie(**{k: parsed[k] for k in
                     ["title", "bot_code", "title_ru", "title_en",
                      "year", "genre", "description", "channel_msg_id"]})"""

new_block = """        # TMDB dan qidiramiz
        tmdb_data = await fetch_movie_details(parsed.get("title"), parsed.get("year"))
        if tmdb_data:
            parsed["poster_url"] = tmdb_data.get("poster_url")
            parsed["tmdb_rating"] = tmdb_data.get("tmdb_rating")
            
        add_movie(**{k: parsed.get(k) for k in
                     ["title", "bot_code", "title_ru", "title_en",
                      "year", "genre", "description", "channel_msg_id", 
                      "poster_url", "tmdb_rating"]})"""

text = text.replace(old_block, new_block)

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Done")
