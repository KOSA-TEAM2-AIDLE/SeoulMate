-- SeoulMate restaurant RAG schema
-- OPENAI_EMBED_DIM is fixed to 1536 in the application contract.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS restaurant_ko (
    id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    address TEXT,
    postal_code TEXT,
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    category TEXT,
    hours TEXT,
    description TEXT,
    image TEXT,
    link TEXT,
    review_count INTEGER CHECK (review_count IS NULL OR review_count >= 0),
    rating REAL CHECK (rating IS NULL OR rating BETWEEN 0 AND 5),
    category_kakao TEXT,
    description_kakao TEXT,
    last_order TEXT,
    kakao_place_id TEXT UNIQUE,
    kakao_place_url TEXT,
    menu_price_min INTEGER CHECK (menu_price_min IS NULL OR menu_price_min >= 0),
    menu_price_median INTEGER CHECK (menu_price_median IS NULL OR menu_price_median >= 0),
    menu_count INTEGER CHECK (menu_count IS NULL OR menu_count >= 0),
    has_parking BOOLEAN,
    has_group_seating BOOLEAN,
    has_private_room BOOLEAN,
    has_baby_chair BOOLEAN,
    has_kids_menu BOOLEAN,
    allows_pets BOOLEAN,
    has_disabled_access BOOLEAN,
    hours_source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS restaurant_en (LIKE restaurant_ko INCLUDING ALL);

CREATE TABLE IF NOT EXISTS restaurant_menu_ko (
    id BIGINT PRIMARY KEY,
    restaurant_id BIGINT NOT NULL REFERENCES restaurant_ko(id) ON DELETE CASCADE,
    menu_order INTEGER NOT NULL CHECK (menu_order > 0),
    menu_name TEXT NOT NULL,
    price_text TEXT,
    price_value INTEGER CHECK (price_value IS NULL OR price_value >= 0),
    is_main BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (restaurant_id, menu_order)
);

CREATE TABLE IF NOT EXISTS restaurant_menu_en (
    id BIGINT PRIMARY KEY,
    restaurant_id BIGINT NOT NULL REFERENCES restaurant_en(id) ON DELETE CASCADE,
    menu_order INTEGER NOT NULL CHECK (menu_order > 0),
    menu_name TEXT NOT NULL,
    price_text TEXT,
    price_value INTEGER CHECK (price_value IS NULL OR price_value >= 0),
    is_main BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (restaurant_id, menu_order)
);

CREATE TABLE IF NOT EXISTS restaurant_review_ko (
    id BIGINT PRIMARY KEY,
    restaurant_id BIGINT NOT NULL REFERENCES restaurant_ko(id) ON DELETE CASCADE,
    rating REAL NOT NULL CHECK (rating BETWEEN 0 AND 5),
    content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS restaurant_review_en (
    id BIGINT PRIMARY KEY,
    restaurant_id BIGINT NOT NULL REFERENCES restaurant_en(id) ON DELETE CASCADE,
    rating REAL NOT NULL CHECK (rating BETWEEN 0 AND 5),
    content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS restaurant_embedding_ko (
    id BIGSERIAL PRIMARY KEY,
    restaurant_id BIGINT NOT NULL UNIQUE REFERENCES restaurant_ko(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    model TEXT NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS restaurant_embedding_en (
    id BIGSERIAL PRIMARY KEY,
    restaurant_id BIGINT NOT NULL UNIQUE REFERENCES restaurant_en(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    model TEXT NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS review_embedding_ko (
    id BIGSERIAL PRIMARY KEY,
    review_id BIGINT NOT NULL UNIQUE REFERENCES restaurant_review_ko(id) ON DELETE CASCADE,
    restaurant_id BIGINT NOT NULL REFERENCES restaurant_ko(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    model TEXT NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS review_embedding_en (
    id BIGSERIAL PRIMARY KEY,
    review_id BIGINT NOT NULL UNIQUE REFERENCES restaurant_review_en(id) ON DELETE CASCADE,
    restaurant_id BIGINT NOT NULL REFERENCES restaurant_en(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    model TEXT NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS menu_embedding_ko (
    id BIGSERIAL PRIMARY KEY,
    menu_id BIGINT NOT NULL UNIQUE REFERENCES restaurant_menu_ko(id) ON DELETE CASCADE,
    restaurant_id BIGINT NOT NULL REFERENCES restaurant_ko(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    model TEXT NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS menu_embedding_en (
    id BIGSERIAL PRIMARY KEY,
    menu_id BIGINT NOT NULL UNIQUE REFERENCES restaurant_menu_en(id) ON DELETE CASCADE,
    restaurant_id BIGINT NOT NULL REFERENCES restaurant_en(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    model TEXT NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS restaurant_menu_ko_restaurant_idx ON restaurant_menu_ko (restaurant_id);
CREATE INDEX IF NOT EXISTS restaurant_menu_en_restaurant_idx ON restaurant_menu_en (restaurant_id);
CREATE INDEX IF NOT EXISTS restaurant_review_ko_restaurant_idx ON restaurant_review_ko (restaurant_id);
CREATE INDEX IF NOT EXISTS restaurant_review_en_restaurant_idx ON restaurant_review_en (restaurant_id);
CREATE INDEX IF NOT EXISTS restaurant_ko_location_idx ON restaurant_ko (lat, lng);
CREATE INDEX IF NOT EXISTS restaurant_en_location_idx ON restaurant_en (lat, lng);
CREATE INDEX IF NOT EXISTS restaurant_ko_name_trgm_idx ON restaurant_ko USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS restaurant_en_name_trgm_idx ON restaurant_en USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS review_embedding_ko_restaurant_idx ON review_embedding_ko (restaurant_id);
CREATE INDEX IF NOT EXISTS review_embedding_en_restaurant_idx ON review_embedding_en (restaurant_id);
CREATE INDEX IF NOT EXISTS menu_embedding_ko_restaurant_idx ON menu_embedding_ko (restaurant_id);
CREATE INDEX IF NOT EXISTS menu_embedding_en_restaurant_idx ON menu_embedding_en (restaurant_id);
