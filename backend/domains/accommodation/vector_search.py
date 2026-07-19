import math
import psycopg2
import psycopg2.extras
from openai import OpenAI
from difflib import SequenceMatcher
import re
from core.config import DB_CONFIG, OPENAI_API_KEY

EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIM = 1536

# RRF Weights
RRF_K = 60
ACC_WEIGHT = 0.7
REVIEW_WEIGHT = 2.0
REVIEW_TOP_N = 3

ACC_TOP_N = 300
REVIEW_POOL = 400

STYLE_BOOST = 0.015
POPULARITY_BOOST = 0.010
RATING_BOOST = 0.010

MAX_RAG_DISTANCE_KM = 5.0
WALK_KM_PER_MIN = 0.07

ACCOMMODATION_DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "edu",
    "password": "1234",
    "dbname": "edudb",
}

client = OpenAI(api_key=OPENAI_API_KEY)


def get_embedding(text):
    resp = client.embeddings.create(
        model=EMBEDDING_MODEL, input=text, dimensions=EMBEDDING_DIM
    )
    return resp.data[0].embedding


def haversine_km(lat1, lng1, lat2, lng2):
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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
        FROM accommodation_embedding_ko e
        JOIN accommodation_ko a ON a.id = e.accommodation_id
        {where}
        ORDER BY e.embedding <=> %s::vector
        LIMIT %s
    """
    conn = psycopg2.connect(**ACCOMMODATION_DB_CONFIG)
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
        FROM acc_review_embedding_ko e
        JOIN accommodation_ko a ON a.id = e.accommodation_id
        {where}
        ORDER BY e.embedding <=> %s::vector
        LIMIT %s
    """
    conn = psycopg2.connect(**ACCOMMODATION_DB_CONFIG)
    cur = conn.cursor()
    cur.execute(sql, params + [str(q_vec), pool])

    ranks_by_acc = {}
    for i, (aid, content) in enumerate(cur.fetchall()):
        lst = ranks_by_acc.setdefault(aid, [])
        if len(lst) < top_n:
            word_count = len(str(content).split())
            lf = 0.3 if word_count < 4 else (0.8 if word_count < 7 else 1.0)
            lst.append((i + 1, lf, content))

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
                lf / (RRF_K + rank) for rank, lf, _ in review_ranks_by_acc[aid]
            )
        base_scores[aid] = (acc_part, review_part)

    conn = psycopg2.connect(**ACCOMMODATION_DB_CONFIG)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT id, name, hotel_style, rating, review_count, address, amenities, room_features, room_types, lat, lng, image, description
        FROM accommodation_ko WHERE id = ANY(%s)
    """,
        (list(all_ids),),
    )
    info = {row["id"]: dict(row) for row in cur.fetchall()}

    cur.execute("SELECT MAX(review_count), AVG(rating) FROM accommodation_ko")
    max_reviews, global_rating = cur.fetchone().values()
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
                for chunk in re.split(r"[\s,]+", db_style_str.lower()):
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
                "best_review": review_ranks_by_acc[aid][0][2] if aid in review_ranks_by_acc and review_ranks_by_acc[aid] else None
            }
        )
        results.append(a)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def query_hotels_by_radius(target_lat, target_lng, radius_km=5.0):
    conn = psycopg2.connect(**ACCOMMODATION_DB_CONFIG)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        query = """
            SELECT id, name, hotel_style, amenities, address, rating, lat, lng, image, review_count, description,
                   (6371 * acos(
                        cos(radians(%s)) * cos(radians(lat)) * 
                        cos(radians(lng) - radians(%s)) + 
                        sin(radians(%s)) * sin(radians(lat))
                   )) AS distance
            FROM accommodation_ko
            WHERE (6371 * acos(
                        cos(radians(%s)) * cos(radians(lat)) * 
                        cos(radians(lng) - radians(%s)) + 
                        sin(radians(%s)) * sin(radians(lat))
                   )) <= %s
            ORDER BY distance ASC;
        """
        cur.execute(
            query,
            (
                target_lat,
                target_lng,
                target_lat,
                target_lat,
                target_lng,
                target_lat,
                radius_km,
            ),
        )
        return cur.fetchall()
    except Exception as e:
        print(f"edudb 반경 쿼리 실패: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_direct_semantic_similarity(q_vec, accommodation_ids):
    if not accommodation_ids:
        return {}

    conn = psycopg2.connect(**ACCOMMODATION_DB_CONFIG)
    cur = conn.cursor()

    sql = """
        SELECT accommodation_id, (1 - (embedding <=> %s::vector)) AS similarity
        FROM accommodation_embedding_ko
        WHERE accommodation_id = ANY(%s)
    """
    try:
        cur.execute(sql, (str(q_vec), list(accommodation_ids)))
        scores = {row[0]: float(row[1]) for row in cur.fetchall()}
        return scores
    except Exception as e:
        print(f"시맨틱 유사도 강제 조인 쿼리 실패: {e}")
        return {}
    finally:
        cur.close()
        conn.close()


def get_best_reviews_for_hotels(q_vec, accommodation_ids):
    if not accommodation_ids:
        return {}

    conn = psycopg2.connect(**ACCOMMODATION_DB_CONFIG)
    cur = conn.cursor()

    sql = """
        SELECT DISTINCT ON (accommodation_id) accommodation_id, content
        FROM acc_review_embedding_ko
        WHERE accommodation_id = ANY(%s)
        ORDER BY accommodation_id, embedding <=> %s::vector
    """
    try:
        cur.execute(sql, (accommodation_ids, str(q_vec)))
        return {row[0]: row[1] for row in cur.fetchall()}
    finally:
        cur.close()
        conn.close()
