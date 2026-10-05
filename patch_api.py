with open('bot.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_append = """            safe_movies.append({
                "id": m.get("id"),
                "title": m.get("title", ""),
                "year": m.get("year", ""),
                "genre": m.get("genre", ""),
                "bot_code": str(m.get("bot_code", ""))
            })"""

new_append = """            safe_movies.append({
                "id": m.get("id"),
                "title": m.get("title", ""),
                "year": m.get("year", ""),
                "genre": m.get("genre", ""),
                "bot_code": str(m.get("bot_code", "")),
                "poster_url": m.get("poster_url", ""),
                "tmdb_rating": m.get("tmdb_rating", "")
            })"""

text = text.replace(old_append, new_append)

# Add Web App handlers for favorites
fav_handlers = """
    async def api_get_favorites(request):
        try:
            user_id = int(request.query.get('user_id', 0))
            from database import get_user_favorites
            favs = get_user_favorites(user_id)
            
            safe_favs = []
            for m in favs:
                safe_favs.append({
                    "id": m.get("id"),
                    "title": m.get("title", ""),
                    "year": m.get("year", ""),
                    "genre": m.get("genre", ""),
                    "bot_code": str(m.get("bot_code", "")),
                    "poster_url": m.get("poster_url", ""),
                    "tmdb_rating": m.get("tmdb_rating", "")
                })
            return web.json_response(safe_favs)
        except Exception:
            return web.json_response([])

    async def api_toggle_favorite(request):
        try:
            data = await request.json()
            user_id = int(data.get('user_id', 0))
            movie_id = int(data.get('movie_id', 0))
            action = data.get('action') # 'add' or 'remove'
            
            from database import add_favorite, remove_favorite
            if action == 'add':
                success = add_favorite(user_id, movie_id)
            else:
                success = remove_favorite(user_id, movie_id)
                
            return web.json_response({"success": success})
        except Exception:
            return web.json_response({"success": False})

    app.router.add_get('/api/favorites', api_get_favorites)
    app.router.add_post('/api/favorites/toggle', api_toggle_favorite)
"""

if 'api_get_favorites' not in text:
    text = text.replace("    app.router.add_post('/api/ai', api_ai)", "    app.router.add_post('/api/ai', api_ai)" + fav_handlers)

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Done Web APIs")
