import os
import re
import math
from datetime import datetime
from zoneinfo import ZoneInfo
from difflib import SequenceMatcher

import psycopg2
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# --- Hyperparameters and Model Settings ---
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIM = 1536
CHAT_MODEL = "gpt-4o-mini"

# Multi-review consistency RRF variation weights
RRF_K = 60
ACC_WEIGHT = 0.7
REVIEW_WEIGHT = 2.0
REVIEW_TOP_N = 3

# Expanded pools to prevent structural omission on semantic/conversational text queries
ACC_TOP_N = 300
REVIEW_POOL = 400

# Soft boost weights applied upon request
STYLE_BOOST = 0.015
POPULARITY_BOOST = 0.010
RATING_BOOST = 0.010

# Walking time approximation (10 min walk ≒ 0.7 km straight line)
WALK_KM_PER_MIN = 0.07

# 🛡️ [Global Safeguard] Max distance allowed for RAG search from a landmark/coordinates (5.0km)
MAX_RAG_DISTANCE_KM = 5.0

# Database connection info
DB_PARAMS = {
    "host": "localhost",
    "port": 5432,
    "user": "edu",
    "password": "1234",
    "database": "edudb",
}

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
SEOUL_TZ = ZoneInfo("Asia/Seoul")

# --- Hotel Styles and Synonyms from accommodation_en.csv ---
STYLE_TERMS = {
    "modern": "Modern",
    "contemporary": "Modern",
    "modernized": "Modern",
    "newly opened": "Modern",
    "clean": "Modern",
    "cleanliness": "Modern",
    "neat": "Modern",
    "spotless": "Modern",
    "romantic": "Romantic",
    "romance": "Romantic",
    "couples": "Romantic",
    "couple": "Romantic",
    "honeymoon": "Romantic",
    "anniversary": "Romantic",
    "charming": "Charming",
    "lovely": "Charming",
    "pretty": "Charming",
    "family": "Family",
    "kids": "Family",
    "kid": "Family",
    "children": "Family",
    "parents": "Family",
    "family trip": "Family",
    "with family": "Family",
    "great view": "Great View",
    "nice view": "Great View",
    "good view": "Great View",
    "amazing view": "Great View",
    "beautiful view": "Great View",
    "scenery": "Great View",
    "night view": "Great View",
    "rooftop": "Great View",
    "city view": "City View",
    "cityscape": "City View",
    "skyline": "City View",
    "river view": "River View",
    "han river": "River View",
    "centrally located": "Centrally Located",
    "center": "Centrally Located",
    "downtown": "Centrally Located",
    "central": "Centrally Located",
    "heart of seoul": "Centrally Located",
    "location": "Centrally Located",
    "great location": "Centrally Located",
    "accessible": "Centrally Located",
    "shopping": "Centrally Located",
    "business": "Business",
    "work": "Business",
    "biz": "Business",
    "business trip": "Business",
    "station": "Business",
    "subway": "Business",
    "convenient": "Business",
    "trendy": "Trendy",
    "hip": "Trendy",
    "popular": "Trendy",
    "hotplace": "Trendy",
    "boutique": "Boutique",
    "stylish": "Boutique",
    "design hotel": "Boutique",
    "quiet": "Quiet",
    "peaceful": "Quiet",
    "calm": "Quiet",
    "silent": "Quiet",
    "quaint": "Quaint",
    "cozy": "Quaint",
    "residential neighborhood": "Residential Neighborhood",
    "residential": "Residential Neighborhood",
    "local area": "Residential Neighborhood",
    "neighborhood": "Residential Neighborhood",
    "budget": "Budget",
    "cheap": "Budget",
    "affordable": "Budget",
    "value": "Budget",
    "good value": "Budget",
    "reasonable": "Budget",
    "cost-effective": "Budget",
    "mid-range": "Mid-range",
    "moderate": "Mid-range",
    "luxury": "Luxury",
    "luxurious": "Luxury",
    "fancy": "Luxury",
    "high-end": "Luxury",
    "premium": "Luxury",
    "5 star": "Luxury",
    "classic": "Classic",
    "traditional": "Classic",
    "antique": "Classic",
    "hidden gem": "Hidden Gem",
    "private": "Hidden Gem",
    "secret place": "Hidden Gem",
}

GENERIC_WORDS = [
    "accommodation",
    "hotel",
    "hostel",
    "guesthouse",
    "pension",
    "stay",
    "place",
    "room",
    "motel",
    "inn",
]
SEOUL_DISTRICTS = [
    "Gangnam-gu",
    "Gangdong-gu",
    "Gangbuk-gu",
    "Gangseo-gu",
    "Gwanak-gu",
    "Gwangjin-gu",
    "Guro-gu",
    "Geumcheon-gu",
    "Nowon-gu",
    "Dobong-gu",
    "Dongdaemun-gu",
    "Dongjak-gu",
    "Mapo-gu",
    "Seodaemun-gu",
    "Seocho-gu",
    "Seongdong-gu",
    "Seongbuk-gu",
    "Songpa-gu",
    "Yangcheon-gu",
    "Yeongdeungpo-gu",
    "Yongsan-gu",
    "Eunpyeong-gu",
    "Jongno-gu",
    "Jung-gu",
    "Jungnang-gu",
]

LANDMARKS = {
    "Yeouido Hangang Park": (37.5285, 126.9349),
    "Gwanghwamun": (37.5759, 126.9769),
    "Jamsil Station": (37.5133, 127.1001),
    "Gangnam Station": (37.4979, 127.0276),
    "Seoul Station": (37.5547, 126.9707),
}


# 🛠️ [Ruff F821 Fix] Moved haversine_km to the top before it gets called inside fuse_and_rank
def haversine_km(lat1, lng1, lat2, lng2):
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_embedding(text):
    resp = client.embeddings.create(
        model=EMBEDDING_MODEL, input=text, dimensions=EMBEDDING_DIM
    )
    return resp.data[0].embedding


def _find_typo_match(q_low, cutoff=0.8):
    words = q_low.split()
    best = (None, None, 0.0)
    for term in STYLE_TERMS:
        if len(term) < 3:
            continue
        n = len(term.split())
        for i in range(len(words) - n + 1):
            chunk = " ".join(words[i : i + n])
            score = SequenceMatcher(None, term, chunk).ratio()
            if score >= cutoff and score > best[2]:
                best = (STYLE_TERMS[term], chunk, score)
    return best[0], best[1]


def extract_style_and_query(question):
    q_low = question.lower()
    matched = None
    for term in sorted(STYLE_TERMS, key=len, reverse=True):
        if term in q_low:
            matched = STYLE_TERMS[term]
            q_low = re.sub(re.escape(term), " ", q_low, count=1)
            break
    if matched is None:
        style, chunk = _find_typo_match(q_low)
        if style:
            matched = style
            if chunk:
                q_low = q_low.replace(chunk, " ")
    for w in sorted(GENERIC_WORDS, key=len, reverse=True):
        q_low = q_low.replace(w, " ")
    cleaned = re.sub(r"\s+", " ", q_low).strip(" ,")
    if not cleaned:
        cleaned = question
    return matched, cleaned


def extract_search_options(question, user_lat=None, user_lng=None):
    q = question.strip()
    semantic = q
    options = {
        "original_question": q,
        "semantic_query": None,
        "hotel_style": None,
        "district": None,
        "min_rating": None,
        "min_review_count": None,
        "origin_name": None,
        "origin_lat": user_lat,
        "origin_lng": user_lng,
        "max_distance_km": None,
        "distance_is_walk_approx": False,
        "popularity_intent": False,
        "rating_intent": False,
    }

    for district in SEOUL_DISTRICTS:
        if district.lower() in semantic.lower():
            options["district"] = district
            semantic = re.sub(district, " ", semantic, flags=re.IGNORECASE)
            break

    for name in sorted(LANDMARKS, key=len, reverse=True):
        if name.lower() in semantic.lower():
            options["origin_name"] = name
            options["origin_lat"], options["origin_lng"] = LANDMARKS[name]
            semantic = re.sub(name, " ", semantic, flags=re.IGNORECASE)
            break

    m = re.search(
        r"(?:rating|score)\s*(?:of\s*)?(?:over|above|>=|>)?\s*(\d(?:\.\d+)?)\s*(?:or higher|and above|\+)?",
        semantic,
        re.I,
    )
    if not m:
        m = re.search(r"(\d(?:\.\d+)?)\s*\+?\s*(?:rating|stars?)", semantic, re.I)
    if m:
        options["min_rating"] = float(m.group(1))
        semantic = semantic.replace(m.group(0), " ")

    m = re.search(r"(?:more than|over|>|>=)\s*(\d+)\s*reviews?", semantic, re.I)
    if not m:
        m = re.search(r"(\d+)\s*(?:\+|or more)\s*reviews?", semantic, re.I)
    if m:
        options["min_review_count"] = int(m.group(1))
        semantic = semantic.replace(m.group(0), " ")

    m = re.search(r"(?:within\s*)?(\d+)\s*(?:min|minute)s?\s*walk", semantic, re.I)
    if m:
        minutes = int(m.group(1))
        options["max_distance_km"] = round(minutes * WALK_KM_PER_MIN, 3)
        options["distance_is_walk_approx"] = True
        semantic = semantic.replace(m.group(0), " ")

    m = re.search(
        r"(?:within\s*)?(\d+(?:\.\d+)?)\s*(?:km|kilometers?)(?:\s*radius)?",
        semantic,
        re.I,
    )
    if m:
        options["max_distance_km"] = float(m.group(1))
        semantic = semantic.replace(m.group(0), " ")

    if re.search(r"popular|famous|hot|trending|well-known", semantic, re.I):
        options["popularity_intent"] = True
        semantic = re.sub(
            r"popular|famous|hot|trending|well-known",
            " ",
            semantic,
            flags=re.IGNORECASE,
        )

    if re.search(
        r"highly rated|good reviews|great reviews|best rated|top rated", semantic, re.I
    ):
        options["rating_intent"] = True
        semantic = re.sub(
            r"highly rated|good reviews|great reviews|best rated|top rated",
            " ",
            semantic,
            flags=re.IGNORECASE,
        )

    semantic = re.sub(
        r"(?:around here|near|recommend|find|show me|looking for)",
        " ",
        semantic,
        flags=re.IGNORECASE,
    )

    hotel_style, cleaned = extract_style_and_query(semantic)
    options["hotel_style"] = hotel_style
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")

    if not cleaned or cleaned.lower() in [g.lower() for g in GENERIC_WORDS]:
        cleaned = "accommodation"
    options["semantic_query"] = cleaned
    return options


def build_sql_filters(options, alias="a"):
    clauses, params = [], []
    if options.get("district"):
        clauses.append(f"{alias}.address ILIKE %s")
        params.append(f"%{options['district']}%")
    if options.get("min_rating") is not None:
        clauses.append(f"{alias}.rating >= %s")
        params.append(options["min_rating"])
    if options.get("min_review_count") is not None:
        clauses.append(f"{alias}.review_count >= %s")
        params.append(options["min_review_count"])

    lat, lng = options.get("origin_lat"), options.get("origin_lng")
    radius = (
        options.get("max_distance_km")
        if options.get("max_distance_km") is not None
        else MAX_RAG_DISTANCE_KM
    )

    if lat is not None and lng is not None:
        lat_delta = radius / 111.0
        lng_delta = radius / max(111.0 * math.cos(math.radians(lat)), 1e-6)
        clauses.extend(
            [f"{alias}.lat BETWEEN %s AND %s", f"{alias}.lng BETWEEN %s AND %s"]
        )
        params.extend(
            [lat - lat_delta, lat + lat_delta, lng - lng_delta, lng + lng_delta]
        )
    return clauses, params


def search_by_accommodation(q_vec, options, top_n=ACC_TOP_N):
    clauses, params = build_sql_filters(options, "a")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    sql = f"""
        SELECT e.accommodation_id
        FROM accommodation_embedding_en e
        JOIN accommodation_en a ON a.id = e.accommodation_id
        {where}
        ORDER BY e.embedding <=> %s::vector
        LIMIT %s
    """
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute(sql, params + [str(q_vec), top_n])
    ranks = {row[0]: i + 1 for i, row in enumerate(cur.fetchall())}
    cur.close()
    conn.close()
    return ranks


def search_by_review(q_vec, options, pool=REVIEW_POOL, top_n=REVIEW_TOP_N):
    clauses, params = build_sql_filters(options, "a")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    sql = f"""
        SELECT e.accommodation_id, e.content
        FROM acc_review_embedding_en e
        JOIN accommodation_en a ON a.id = e.accommodation_id
        {where}
        ORDER BY e.embedding <=> %s::vector
        LIMIT %s
    """
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute(sql, params + [str(q_vec), pool])

    ranks_by_acc = {}
    for i, (aid, content) in enumerate(cur.fetchall()):
        lst = ranks_by_acc.setdefault(aid, [])
        if len(lst) < top_n:
            word_count = len(str(content).split())
            lf = 0.3 if word_count < 4 else (0.8 if word_count < 7 else 1.0)
            lst.append((i + 1, lf))

    cur.close()
    conn.close()
    return ranks_by_acc


def fuse_and_rank(acc_ranks, review_ranks_by_acc, options, top_k=20):
    all_ids = set(acc_ranks) | set(review_ranks_by_acc)
    if not all_ids:
        return []

    base_scores = {}
    for aid in all_ids:
        acc_part = ACC_WEIGHT / (RRF_K + acc_ranks[aid]) if aid in acc_ranks else 0.0
        review_part = 0.0
        if aid in review_ranks_by_acc:
            review_part = REVIEW_WEIGHT * sum(
                lf / (RRF_K + rank) for rank, lf in review_ranks_by_acc[aid]
            )
        base_scores[aid] = (acc_part, review_part)

    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, hotel_style, rating, review_count, address, amenities, room_features, room_types, lat, lng, image, link
        FROM accommodation_en WHERE id = ANY(%s)
    """,
        (list(all_ids),),
    )
    cols = [d[0] for d in cur.description]
    info = {row[0]: dict(zip(cols, row)) for row in cur.fetchall()}

    cur.execute("SELECT MAX(review_count), AVG(rating) FROM accommodation_en")
    max_reviews, global_rating = cur.fetchone()
    cur.close()
    conn.close()

    max_reviews = max(max_reviews or 1, 1)
    global_rating = float(global_rating or 0)
    results = []

    for aid, (acc_part, review_part) in base_scores.items():
        a = info.get(aid)
        if not a:
            continue

        distance_km = None
        lat, lng = options.get("origin_lat"), options.get("origin_lng")
        if (
            lat is not None
            and lng is not None
            and a["lat"] is not None
            and a["lng"] is not None
        ):
            distance_km = haversine_km(lat, lng, a["lat"], a["lng"])

            allowed_max_km = (
                options.get("max_distance_km")
                if options.get("max_distance_km") is not None
                else MAX_RAG_DISTANCE_KM
            )
            if distance_km > allowed_max_km:
                continue
        elif options.get("max_distance_km") is not None:
            continue

        style_part = 0.0
        req_style = options.get("hotel_style")
        db_style_str = a.get("hotel_style")

        if req_style and db_style_str:
            if req_style.lower() in db_style_str.lower():
                style_part = STYLE_BOOST
            else:
                for chunk in re.split(r"[\s,;/]+", db_style_str.lower()):
                    if SequenceMatcher(None, req_style.lower(), chunk).ratio() >= 0.65:
                        style_part = STYLE_BOOST
                        break

        popularity_norm = math.log1p(a["review_count"] or 0) / math.log1p(max_reviews)
        if options.get("popularity_intent"):
            popularity_part = POPULARITY_BOOST * popularity_norm
        else:
            popularity_part = (POPULARITY_BOOST * 0.4) * popularity_norm

        count = a["review_count"] or 0
        m = 50
        adjusted_rating = (count / (count + m)) * (a["rating"] or 0) + (
            m / (count + m)
        ) * global_rating
        rating_norm = max(0.0, min(1.0, adjusted_rating / 5.0))

        if options.get("rating_intent"):
            rating_part = RATING_BOOST * rating_norm
        else:
            rating_part = (RATING_BOOST * 0.4) * rating_norm

        a.update(
            {
                "acc_rrf": acc_part,
                "review_rrf": review_part,
                "style_boost": style_part,
                "popularity_boost": popularity_part,
                "rating_boost": rating_part,
                "adjusted_rating": adjusted_rating,
                "distance_km": distance_km,
                "score": acc_part
                + review_part
                + style_part
                + popularity_part
                + rating_part,
            }
        )
        results.append(a)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def get_supporting_reviews(q_vec, accommodation_ids, per_accommodation=3):
    if not accommodation_ids:
        return {}
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT accommodation_id, content FROM (
            SELECT e.accommodation_id, e.content,
                   ROW_NUMBER() OVER (
                       PARTITION BY e.accommodation_id
                       ORDER BY e.embedding <=> %s::vector
                   ) AS rn
            FROM acc_review_embedding_en e
            WHERE e.accommodation_id = ANY(%s)
        ) t
        WHERE rn <= %s
    """,
        (str(q_vec), accommodation_ids, per_accommodation),
    )

    result = {}
    for aid, content in cur.fetchall():
        result.setdefault(aid, []).append({"content": content})
    cur.close()
    conn.close()
    return result
