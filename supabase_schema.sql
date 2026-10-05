-- ============================================================
--  Supabase SQL Editor da bir marta ishga tushiring
--  (Supabase → SQL Editor → New query → Paste → Run)
-- ============================================================

-- Kinolar jadvali
CREATE TABLE IF NOT EXISTS movies (
    id              BIGSERIAL PRIMARY KEY,
    title           TEXT        NOT NULL,
    title_ru        TEXT,
    title_en        TEXT,
    year            INTEGER,
    genre           TEXT,
    description     TEXT,
    bot_code        TEXT        NOT NULL UNIQUE,
    channel_msg_id  BIGINT,
    added_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Tezkor qidirish uchun indekslar
CREATE INDEX IF NOT EXISTS idx_movies_title    ON movies (LOWER(title));
CREATE INDEX IF NOT EXISTS idx_movies_title_ru ON movies (LOWER(title_ru));
CREATE INDEX IF NOT EXISTS idx_movies_title_en ON movies (LOWER(title_en));
CREATE INDEX IF NOT EXISTS idx_movies_bot_code ON movies (bot_code);

-- Qidiruv logi jadvali
CREATE TABLE IF NOT EXISTS search_log (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT      NOT NULL,
    username    TEXT,
    full_name   TEXT,
    query       TEXT        NOT NULL,
    found       BOOLEAN     DEFAULT FALSE,
    searched_at TIMESTAMPTZ DEFAULT NOW()
);

-- Row Level Security o'chirish (bot server-side ishlaydi)
ALTER TABLE movies     DISABLE ROW LEVEL SECURITY;
ALTER TABLE search_log DISABLE ROW LEVEL SECURITY;

-- Admin boshqaruv jadvali
CREATE TABLE IF NOT EXISTS bot_admins (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT      NOT NULL UNIQUE,
    username    TEXT,
    full_name   TEXT,
    added_by    BIGINT,
    added_at    TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE bot_admins DISABLE ROW LEVEL SECURITY;

-- ============================================================
-- YANGA QO'SHILGAN FUNKSIYALAR UCHUN (V2)
-- ============================================================

-- Kinolar jadvaliga rasm manzili ustunini qo'shish (agar yo'q bo'lsa)
ALTER TABLE movies ADD COLUMN IF NOT EXISTS poster_url TEXT;
ALTER TABLE movies ADD COLUMN IF NOT EXISTS tmdb_rating TEXT;

-- Saqlangan kinolar (Watchlist) jadvali
CREATE TABLE IF NOT EXISTS favorites (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    movie_id    BIGINT NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    added_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, movie_id)
);
ALTER TABLE favorites DISABLE ROW LEVEL SECURITY;
