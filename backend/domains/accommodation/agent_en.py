import os
import re
import math
from difflib import SequenceMatcher
import psycopg2
from psycopg2.extras import RealDictCursor

# Import external live scraper module safely
try:
    from mcp_server.booking_client import main as run_live_scraper
except ImportError:
    run_live_scraper = None

# Import core dependencies from revamped English RAG module
from domains.accommodation.search_accommodation_rrf_en import (
    get_embedding,
    extract_search_options,
    search_by_accommodation,
    search_by_review,
    fuse_and_rank,
    get_direct_semantic_similarity,
    get_best_reviews_for_hotels,
    ACC_TOP_N,
    REVIEW_POOL,
    STYLE_TERMS,
    GENERIC_WORDS,
    SEOUL_DISTRICTS,
    DB_PARAMS,
    MAX_RAG_DISTANCE_KM as MAX_ALLOWABLE_DISTANCE_KM
)

from core.config import KAKAO_REST_API_KEY

def parse_user_intent_with_kakao(user_message):
    if not user_message:
        user_message = ""

    dates = re.findall(r"\d{4}-\d{2}-\d{2}", user_message)
    checkin = dates[0] if len(dates) > 0 else None
    checkout = dates[1] if len(dates) > 1 else None

    extracted_location = "Seoul"
    location_type = "default"
    target_lat = 37.5665
    target_lng = 126.9780

    LANDMARK_CORRECTION = {
        "gyeongbokgung": "Gyeongbokgung Palace",
        "gyoungbokgung": "Gyeongbokgung Palace",
        "changdeokgung": "Changdeokgung Palace",
        "changgyeonggung": "Changgyeonggung Palace",
        "deoksugung": "Deoksugung Palace",
        "gwanghwamun": "Gwanghwamun",
        "bukchon": "Bukchon Hanok Village",
        "insadong": "Insadong",
        "ikseondong": "Ikseondong",
        "gangnam": "Gangnam Station",
        "jamsil": "Jamsil Station",
        "hongdae": "Hongdae",
        "myeongdong": "Myeongdong",
        "itaewon": "Itaewon",
        "yeouido": "Yeouido",
        "seoulstation": "Seoul Station",
        "seoul station": "Seoul Station",
        "dongdaemun": "Dongdaemun",
        "namdaemun": "Namdaemun",
        "sinchon": "Sinchon Station",
        "sinsa": "Sinsa Station",
        "apgujeong": "Apgujeong",
        "ewha": "Ewha Womans University",
        "yonsei": "Yonsei University",
        "snu": "Seoul National University",
        "lottetower": "Lotte World Tower",
        "coex": "COEX",
        "namsan": "Namsan Seoul Tower",
    }

    search_keyword = None
    msg_lower = user_message.lower()

    for token, full_name in sorted(LANDMARK_CORRECTION.items(), key=lambda x: len(x[0]), reverse=True):
        if token in msg_lower:
            search_keyword = full_name
            location_type = "landmark"
            break

    if not search_keyword:
        for district in SEOUL_DISTRICTS:
            district_clean = district.lower().replace("-gu", "")
            if district_clean in msg_lower:
                search_keyword = district
                location_type = "district"
                break

    if not search_keyword:
        search_keyword = "Seoul"
        location_type = "default"
    else:
        if search_keyword and search_keyword.lower() not in ["seoul"] and location_type != "default" and KAKAO_REST_API_KEY:
            url = "https://dapi.kakao.com/v2/local/search/keyword.json"
            headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
            params = {"query": search_keyword, "size": 1}

            try:
                import requests
                response = requests.get(url, headers=headers, params=params).json()

                if response.get("documents"):
                    doc = response["documents"][0]
                    address_name = doc["address_name"]

                    if "서울" in address_name or "Seoul" in address_name:
                        target_lng = float(doc["x"])
                        target_lat = float(doc["y"])

                        district_match = re.search(r"\b\w+구\b", address_name)
                        if district_match:
                            extracted_location = district_match.group()
                            location_type = "district"
                        else:
                            extracted_location = search_keyword
                            location_type = "landmark"
                    else:
                        location_type = "default"
            except Exception as e:
                print(f"Kakao Local API Request failed: {e}")

    target_style = None
    for term, standard_style in STYLE_TERMS.items():
        if re.search(rf"\b{re.escape(term)}\b", user_message, re.IGNORECASE):
            target_style = standard_style
            break

    return {
        "is_live_booking": checkin is not None,
        "location": extracted_location,
        "location_type": location_type,
        "checkin": checkin,
        "checkout": checkout,
        "style": target_style,
        "lat": target_lat,
        "lng": target_lng,
        "keyword": search_keyword if search_keyword else "Seoul",
    }


def clean_hotel_name_pure(raw_name):
    if not raw_name:
        return "Unnamed Accommodation"
    name = re.sub(r"#\w+", "", raw_name)
    for word in GENERIC_WORDS:
        name = re.sub(rf"(?i)\b{word}\b", "", name)
    name = re.sub(r"[A-Za-z0-9]{3,}\b", "", name)
    return re.sub(r"[\s\-,/#]+", " ", name).strip()


def query_hotels_by_radius(target_lat, target_lng, radius_km=5.0):
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        query = """
            SELECT id, name, hotel_style, amenities, address, rating, review_count, lat, lng, image, link, room_features, room_types,
                   (6371 * acos(
                        cos(radians(%s)) * cos(radians(lat)) * 
                        cos(radians(lng) - radians(%s)) + 
                        sin(radians(%s)) * sin(radians(lat))
                   )) AS distance
            FROM accommodation_en
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
        print(f"edudb radius query failed: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def find_best_db_match_pure(scraped_name, db_hotels):
    best_match = None
    highest_score = 0.0

    if not scraped_name:
        return None, 0.0

    for db_hotel in db_hotels:
        db_name = db_hotel.get("name") if db_hotel.get("name") is not None else ""
        if not db_name:
            continue

        score = SequenceMatcher(None, scraped_name.lower(), db_name.lower()).ratio()
        if (
            db_name.lower() in scraped_name.lower()
            or scraped_name.lower() in db_name.lower()
        ):
            score = min(1.0, score + 0.25)

        if score > highest_score and score >= 0.45:
            highest_score = score
            best_match = db_hotel

    return best_match, highest_score


def get_direct_semantic_similarity(q_vec, accommodation_ids):
    if not accommodation_ids:
        return {}

    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    sql = """
        SELECT accommodation_id, (1 - (embedding <=> %s::vector)) AS similarity
        FROM accommodation_embedding_en
        WHERE accommodation_id = ANY(%s)
    """
    try:
        cur.execute(sql, (str(q_vec), list(accommodation_ids)))
        scores = {row[0]: float(row[1]) for row in cur.fetchall()}
        return scores
    except Exception as e:
        print(f"Semantic direct-join similarity query failed: {e}")
        return {}
    finally:
        cur.close()
        conn.close()

def run_local_rag_en(user_question, user_lat=None, user_lng=None, top_n=30):
    options = extract_search_options(user_question, user_lat, user_lng)
    q_vec = get_embedding(options["semantic_query"])

    acc_ranks = search_by_accommodation(q_vec, options, top_n=ACC_TOP_N)
    review_ranks = search_by_review(q_vec, options, pool=REVIEW_POOL)

    candidates = fuse_and_rank(acc_ranks, review_ranks, options, top_k=top_n)
    
    formatted_candidates = []
    for c in candidates:
        amenities = c.get('amenities', '')
        amenities_sample = amenities.split(',')[0].strip() if amenities else 'Basic amenities'
        description = c.get('description')
        if description and len(description) >= 10:
            reason_text = f"💡 {description[:100]}..." if len(description) > 100 else f"💡 {description}"
        else:
            reason_text = f"Highly relevant to your preferences. (Features {amenities_sample} etc.)"

        formatted_candidates.append({
            "accommodation_id": str(c["id"]),
            "name": c["name"],
            "score": c["score"],
            "category": c.get("hotel_style", "Accommodation"),
            "address": c.get("address"),
            "rating": c.get("rating"),
            "review_count": c.get("review_count"),
            "image": c.get("image"),
            "lat": c.get("lat"),
            "lng": c.get("lng"),
            "reason": reason_text,
            "features": f"Amenities: {amenities} / Features: {c.get('room_features', '')}"
        })
        
    return {
        "candidates": formatted_candidates,
        "origin_lat": user_lat,
        "origin_lng": user_lng,
    }

def search_accommodations_structured_en(request):
    """
    Called by DomainSearchService when language is "en".
    """
    user_message = request.search_query
    current_lat = request.latitude
    current_lng = request.longitude
    top_n = request.candidate_count
    
    intent = parse_user_intent_with_kakao(user_message)
    is_valid_location = intent["location_type"] != "default"

    if not intent["is_live_booking"] and not is_valid_location:
        return run_local_rag_en(user_message, user_lat=current_lat, user_lng=current_lng, top_n=top_n)
    
    elif not intent["is_live_booking"] and is_valid_location:
        return run_local_rag_en(user_message, user_lat=intent["lat"], user_lng=intent["lng"], top_n=top_n)
    
    else:
        if not run_live_scraper:
            print("Warning: booking module not found. Falling back to RAG Mode.")
            return run_local_rag_en(user_message, user_lat=intent["lat"], user_lng=intent["lng"], top_n=top_n)
            
        scraped_result = run_live_scraper(
            intent["location"], intent["checkin"], intent["checkout"]
        )

        if not scraped_result or scraped_result.get("status") != "success" or not scraped_result.get("data"):
            return run_local_rag_en(user_message, user_lat=intent["lat"], user_lng=intent["lng"], top_n=top_n)

        if is_valid_location:
            db_hotels = query_hotels_by_radius(
                intent["lat"], intent["lng"], radius_km=MAX_ALLOWABLE_DISTANCE_KM
            )
        else:
            conn = psycopg2.connect(**DB_PARAMS)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                "SELECT id, name, hotel_style, amenities, address, rating, review_count, lat, lng, image, link, room_features, room_types, 0.0 as distance FROM accommodation_en;"
            )
            db_hotels = cur.fetchall()
            cur.close()
            conn.close()

        semantic_query = user_message
        semantic_query = re.sub(r"\d{4}-\d{2}-\d{2}", " ", semantic_query)

        if intent["keyword"].lower() != "seoul" and is_valid_location:
            semantic_query = re.sub(
                rf"(?i)\b{re.escape(intent['keyword'])}\b", " ", semantic_query
            )

        for dist in SEOUL_DISTRICTS:
            semantic_query = re.sub(rf"(?i)\b{dist}\b", " ", semantic_query)

        english_stops = [
            "near", "around", "hotel", "accommodation", "stay", "find", "recommend",
            "show", "me", "prices", "booking", "available", "from", "to", "in", "at",
            "with", "and", "for", "of", "or", "looking", "pool", "swimming", "price",
            "get", "style", "styles", "accommodations", "places", "hotels", "rooms",
            "good", "please"
        ]
        for stop in english_stops:
            semantic_query = re.sub(rf"(?i)\b{stop}\b", " ", semantic_query)

        semantic_query = re.sub(r"\s+", " ", semantic_query).strip(" ,")

        if not semantic_query or len(semantic_query) < 3:
            semantic_query = "accommodation"

        candidates_map = {}
        used_db_ids = set()

        for item in scraped_result["data"]:
            raw_title = item.get("hotel_name", "Unnamed")
            live_price = item.get("live_price", "Price N/A")
            live_rating_str = item.get("live_rating", "0.0")
            booking_url = item.get("booking_url", "#")

            cleaned_title = clean_hotel_name_pure(raw_title)
            matched_db, sim_score = find_best_db_match_pure(cleaned_title, db_hotels)

            if matched_db:
                hotel_id = matched_db["id"]

                if hotel_id in used_db_ids:
                    continue

                actual_distance = matched_db["distance"]
                if is_valid_location and actual_distance > MAX_ALLOWABLE_DISTANCE_KM:
                    continue

                used_db_ids.add(hotel_id)
                candidates_map[hotel_id] = {
                    "matched_db": matched_db,
                    "sim_score": sim_score,
                    "live_price": live_price,
                    "live_rating_str": live_rating_str,
                    "booking_url": booking_url,
                    "actual_distance": actual_distance,
                }

        q_vec = get_embedding(semantic_query)
        db_only_ids = [k for k in candidates_map.keys() if str(k).isdigit()]
        rag_similarity_scores = get_direct_semantic_similarity(q_vec, db_only_ids) if db_only_ids else {}
        best_reviews = get_best_reviews_for_hotels(q_vec, db_only_ids) if db_only_ids else {}

        valid_scores = list(rag_similarity_scores.values())
        max_sim = max(valid_scores) if valid_scores else 1.0
        min_sim = min(valid_scores) if valid_scores else 0.0
        sim_range = max_sim - min_sim if max_sim - min_sim > 0 else 1.0

        final_processed_list = []
        for hotel_id, c_data in candidates_map.items():
            matched_db = c_data["matched_db"]

            raw_sim = rag_similarity_scores.get(hotel_id, 0.0)
            norm_rag_score = (raw_sim - min_sim) / sim_range if sim_range > 0 else 0.0

            try:
                live_rating = (
                    float(c_data["live_rating_str"])
                    if c_data["live_rating_str"]
                    else 0.0
                )
                normalized_live_rating = live_rating / 2.0
            except ValueError:
                normalized_live_rating = 0.0

            distance_penalty = c_data["actual_distance"] if is_valid_location else 0.0
            rank_score = (
                normalized_live_rating
                - (distance_penalty * 0.3)
                + (norm_rag_score * 5.0)
            )

            amenities = matched_db.get('amenities', '')
            amenities_sample = amenities.split(',')[0].strip() if amenities else 'Basic amenities'
            
            description = matched_db.get('description')
            if description and len(description) >= 10:
                reason_text = f"💡 {description[:100]}..." if len(description) > 100 else f"💡 {description}"
            else:
                reason_text = f"Recommended accommodation with live availability. (Features {amenities_sample} etc.)"

            final_processed_list.append({
                "accommodation_id": str(hotel_id),
                "name": matched_db["name"],
                "score": rank_score,
                "category": matched_db.get("hotel_style", "Accommodation"),
                "address": matched_db.get("address"),
                "rating": matched_db.get("rating"),
                "review_count": matched_db.get("review_count"),
                "image": matched_db.get("image"),
                "lat": matched_db.get("lat"),
                "lng": matched_db.get("lng"),
                "price": c_data["live_price"],
                "live_rating": c_data["live_rating_str"],
                "url": c_data["booking_url"],
                "reason": reason_text,
                "features": f"Amenities: {amenities} / Features: {matched_db.get('room_features', '')}"
            })

        final_processed_list.sort(key=lambda x: x["score"], reverse=True)

        if not final_processed_list:
            return run_local_rag_en(user_message, user_lat=intent["lat"], user_lng=intent["lng"], top_n=top_n)

        return {
            "candidates": final_processed_list[:top_n],
            "origin_lat": intent["lat"],
            "origin_lng": intent["lng"],
        }
