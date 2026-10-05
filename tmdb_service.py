import os
import httpx
import logging

logger = logging.getLogger(__name__)
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")

async def fetch_movie_details(title: str, year: int = None) -> dict | None:
    """
    TMDB orqali kino rasmini va reytingini qidiradi.
    Qaytaradi: {"poster_url": "...", "tmdb_rating": "8.5", "overview": "..."}
    """
    if not TMDB_API_KEY or not title:
        return None

    try:
        url = "https://api.themoviedb.org/3/search/movie"
        params = {
            "api_key": TMDB_API_KEY,
            "query": title,
            "language": "uz-UZ",  # O'zbek tilida izlaymiz, bo'lmasa inglizcha qaytadi
            "page": 1,
            "include_adult": "true"
        }
        if year:
            params["year"] = str(year)
            params["primary_release_year"] = str(year)

        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url, params=params)
            
            if res.status_code == 200:
                data = res.json()
                results = data.get("results", [])
                
                # Agar o'zbek tilida topilmasa, inglizchasiga qaytadan izlaymiz
                if not results:
                    params["language"] = "en-US"
                    res = await client.get(url, params=params)
                    if res.status_code == 200:
                        data = res.json()
                        results = data.get("results", [])

                if results:
                    movie = results[0]  # Eng birinchi mos kelganini olamiz
                    poster_path = movie.get("poster_path")
                    poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
                    rating = str(round(movie.get("vote_average", 0), 1)) if movie.get("vote_average") else None
                    overview = movie.get("overview", "")
                    
                    return {
                        "poster_url": poster_url,
                        "tmdb_rating": rating,
                        "overview": overview
                    }
    except Exception as e:
        logger.error(f"TMDB qidiruv xatosi: {e}")

    return None
