import re
from difflib import SequenceMatcher
from core.config import KAKAO_REST_API_KEY
from domains.accommodation.vector_search import (
    get_embedding,
    search_by_accommodation,
    search_by_review,
    fuse_and_rank,
    query_hotels_by_radius,
    get_direct_semantic_similarity,
    get_best_reviews_for_hotels,
    ACC_TOP_N,
    REVIEW_POOL
)

STYLE_TERMS = {
    "멋짐": "멋짐", "멋진": "멋짐", "멋지고": "멋짐", "인테리어": "멋짐", "디자인": "멋짐",
    "감성": "멋짐", "분위기": "멋짐", "예쁜": "멋짐", "현대식": "현대식", "현대적인": "현대식",
    "모던": "현대식", "모던한": "현대식", "신축": "현대식", "새로 오픈": "현대식", "최신식": "현대식",
    "깔끔": "현대식", "깨끗": "현대식", "쾌적": "현대식", "비지니스": "비지니스", "비즈니스": "비지니스",
    "출장": "비지니스", "업무": "비지니스", "워크샵": "비지니스", "워케이션": "비지니스", "역세권": "비지니스",
    "교통": "비지니스", "지하철역": "비지니스", "부티크": "부티크", "부띠끄": "부티크", "스타일리시": "부티크",
    "고풍스러움": "고풍스러움", "고풍스러운": "고풍스러움", "엔틱": "고풍스러움", "앤틱": "고풍스러움",
    "레트로": "고풍스러움", "클래식": "클래식", "클래식한": "클래식", "전통": "클래식", "저렴한": "저렴한",
    "가성비": "저렴한", "싼": "저렴한", "저렴": "저렴한", "저가": "저렴한", "가격대비": "저렴한",
    "합리적인": "저렴한", "싸고": "저렴한", "중간급": "중간급", "무난한": "중간급", "적당한": "중간급",
    "평범한": "중간급", "트렌디": "트렌디", "트렌디한": "트렌디", "힙한": "트렌디", "핫플레이스": "트렌디",
    "핫플": "트렌디", "로맨틱": "로맨틱", "로맨틱한": "로맨틱", "연인": "로맨틱", "커플": "로맨틱",
    "데이트": "로맨틱", "기념일": "로맨틱", "남자친구": "로맨틱", "여자친구": "로맨틱", "남친": "로맨틱",
    "여친": "로맨틱", "가족": "가족", "아이와": "가족", "부모님": "가족", "애들": "가족", "효도": "가족",
    "패밀리": "가족", "럭셔리": "럭셔리", "고급": "럭셔리", "고급지": "럭셔리", "고급스러운": "럭셔리",
    "호화": "럭셔리", "웰컴": "럭셔리", "5성급": "럭셔리", "조용함": "조용함", "조용": "조용함",
    "한적": "조용함", "힐링": "조용함", "쉬기": "조용함", "휴식": "조용함", "산책": "조용함",
    "청계천": "조용함", "주거지 인근": "주거지 인근", "주택가": "주거지 인근", "동네": "주거지 인근",
    "뛰어난 전망": "뛰어난 전망", "호캉스": "뛰어난 전망", "뷰맛집": "뛰어난 전망", "전망": "뛰어난 전망",
    "야경": "뛰어난 전망", "뷰": "뛰어난 전망", "루프탑": "뛰어난 전망", "도시 조망": "도시 조망",
    "시티뷰": "도시 조망", "빌딩뷰": "도시 조망", "강 전망": "강 전망", "리버뷰": "강 전망",
    "한강": "강 전망", "한강뷰": "강 전망", "공원 전망": "공원 전망", "파크뷰": "공원 전망",
    "숲뷰": "공원 전망", "호수 전망": "호수 전망", "레이크뷰": "호수 전망", "산 전망": "산 전망",
    "마운틴뷰": "산 전망", "남산뷰": "산 전망", "도시 중심부": "도시 중심부", "시내": "도시 중심부",
    "중심가": "도시 중심부", "위치": "도시 중심부", "명동": "도시 중심부", "중심": "도시 중심부",
    "접근성": "도시 중심부", "쇼핑": "도시 중심부", "맛집": "도시 중심부", "먹거리": "도시 중심부",
    "숨겨진 보석": "숨겨진 보석", "프라이빗": "숨겨진 보석", "나만 알고 싶은": "숨겨진 보석",
    "독특한 호텔": "독특한 호텔", "이색": "독특한 호텔", "특이한": "독특한 호텔", "친환경": "친환경",
    "에코": "친환경", "그린": "친환경",
}

GENERIC_WORDS = [
    "숙소", "호텔", "호스텔", "게스트하우스", "펜션", "숙박", "곳", "방", "객실", "모텔",
]

SEOUL_DISTRICTS = [
    "강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구",
    "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구",
    "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구",
]

LANDMARKS = {
    "여의도 한강공원": (37.5285, 126.9349),
    "광화문": (37.5759, 126.9769),
    "잠실역": (37.5133, 127.1001),
    "강남역": (37.4979, 127.0276),
    "서울역": (37.5547, 126.9707),
}

MAX_ALLOWABLE_DISTANCE_KM = 5.0
WALK_KM_PER_MIN = 0.07

def clean_hotel_name_pure(raw_name):
    if not raw_name:
        return "이름 없음"
    name = re.sub(r"#\w+", "", raw_name)
    for word in GENERIC_WORDS:
        name = name.replace(word, "")
    name = re.sub(r"[A-Za-z0-9]{3,}\b", "", name)
    return re.sub(r"[\s\-,/#]+", " ", name).strip()

def _find_typo_match(q_low, cutoff=0.8):
    words = q_low.split()
    best = (None, None, 0.0)
    for term in STYLE_TERMS:
        if len(term) < 2:
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
            q_low = re.sub(re.escape(term) + r"(형|급|별|식)?", " ", q_low, count=1)
            break
    if matched is None:
        style, chunk = _find_typo_match(q_low)
        if style:
            matched = style
            q_low = q_low.replace(chunk, " ")
    for w in sorted(GENERIC_WORDS, key=len, reverse=True):
        q_low = q_low.replace(w, " ")
    cleaned = re.sub(r"\s+", " ", q_low).strip()
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
        if district in semantic:
            options["district"] = district
            semantic = semantic.replace(district, " ")
            break

    for name in sorted(LANDMARKS, key=len, reverse=True):
        if name in semantic:
            options["origin_name"] = name
            options["origin_lat"], options["origin_lng"] = LANDMARKS[name]
            semantic = semantic.replace(name, " ")
            break

    m = re.search(r"평점\s*(\d(?:\.\d+)?)\s*(?:점\s*)?(?:이상|넘는|초과)(?:인)?", semantic)
    if m:
        options["min_rating"] = float(m.group(1))
        semantic = semantic.replace(m.group(0), " ")

    m = re.search(r"리뷰\s*(\d+)\s*개\s*(?:이상|넘는|초과)(?:인)?", semantic)
    if m:
        options["min_review_count"] = int(m.group(1))
        semantic = semantic.replace(m.group(0), " ")

    m = re.search(r"도보\s*(\d+)\s*분\s*(?:이내|안|거리)", semantic)
    if m:
        minutes = int(m.group(1))
        options["max_distance_km"] = round(minutes * WALK_KM_PER_MIN, 3)
        options["distance_is_walk_approx"] = True
        semantic = semantic.replace(m.group(0), " ")

    m = re.search(r"(\d+(?:\.\d+)?)\s*(km|킬로미터)\s*(?:이내|안|반경)", semantic, re.I)
    if m:
        options["max_distance_km"] = float(m.group(1))
        semantic = semantic.replace(m.group(0), " ")

    if re.search(r"인기\s*(?:많은|있는|좋은)|유명한|핫한", semantic):
        options["popularity_intent"] = True
        semantic = re.sub(r"인기\s*(?:많은|있는|좋은)|유명한|핫한", " ", semantic)

    if re.search(r"평점\s*(?:높은|좋은)|별점\s*(?:높은|좋은)", semantic):
        options["rating_intent"] = True
        semantic = re.sub(r"(?:평점|별점)\s*(?:높은|좋은)", " ", semantic)

    semantic = re.sub(
        r"(?:여기서|에\s*있는|에서|근처|이내|안에|만|찾아\s*줘|추천해\s*줘)", " ", semantic
    )
    hotel_style, cleaned = extract_style_and_query(semantic)
    options["hotel_style"] = hotel_style
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")

    if not cleaned or cleaned in GENERIC_WORDS:
        cleaned = "숙박시설"
    options["semantic_query"] = cleaned
    return options

def parse_user_intent_with_kakao(user_message):
    if not user_message:
        user_message = ""

    dates = re.findall(r"\d{4}-\d{2}-\d{2}", user_message)
    checkin = dates[0] if len(dates) > 0 else None
    checkout = dates[1] if len(dates) > 1 else None

    extracted_location = "서울"
    location_type = "default"
    target_lat = 37.5665
    target_lng = 126.9780

    clean_msg = re.sub(r"\d{4}-\d{2}-\d{2}", "", user_message)
    clean_msg = re.sub(r"[A-Za-z0-9]", "", clean_msg)
    words = re.findall(r"[가-힣]{2,6}", clean_msg)

    stop_words = [
        "근처", "주변", "그넟", "근방", "숙소", "호텔", "추천", "알아봐줘", "알려줘",
        "가격", "예약", "가능한", "부터", "까지", "에", "에서",
    ]
    valid_words = [w for w in words if w not in stop_words and w not in STYLE_TERMS]
    raw_keyword = valid_words[0] if valid_words else ""

    LANDMARK_CORRECTION = {
        "경북궁": "경복궁", "경복궁역": "경복궁", "광화문역": "광화문",
        "강남역": "강남역", "잠실역": "잠실역", "홍대입구": "홍대", "홍대역": "홍대",
    }
    search_keyword = LANDMARK_CORRECTION.get(raw_keyword, raw_keyword)

    if search_keyword and KAKAO_REST_API_KEY:
        url = "https://dapi.kakao.com/v2/local/search/keyword.json"
        headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
        params = {"query": search_keyword, "size": 1}

        try:
            import requests
            response = requests.get(url, headers=headers, params=params).json()

            if response.get("documents"):
                doc = response["documents"][0]
                address_name = doc["address_name"]

                if "서울" in address_name:
                    target_lng = float(doc["x"])
                    target_lat = float(doc["y"])

                    district_match = re.search(r"\b\w+구\b", address_name)
                    if district_match:
                        extracted_location = district_match.group()
                        location_type = "district"
                    else:
                        location_type = "landmark"
                else:
                    location_type = "default"
        except Exception as e:
            print(f"카카오 로컬 API 통신 실패: {e}")

    target_style = None
    for term, standard_style in STYLE_TERMS.items():
        if term in user_message:
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
        "keyword": search_keyword if search_keyword else "서울",
    }

def find_best_db_match_pure(scraped_name, db_hotels):
    best_match = None
    highest_score = 0.0

    if not scraped_name:
        return None, 0.0

    for db_hotel in db_hotels:
        db_name = db_hotel.get("name") if db_hotel.get("name") is not None else ""
        if not db_name:
            continue

        base_score = SequenceMatcher(None, scraped_name, db_name).ratio()
        if db_name in scraped_name or scraped_name in db_name:
            base_score = min(1.0, base_score + 0.25)

        if base_score > highest_score and base_score >= 0.45:
            highest_score = base_score
            best_match = db_hotel

    return best_match, highest_score

def run_local_rag(user_question, user_lat=None, user_lng=None, top_n=30):
    options = extract_search_options(user_question, user_lat, user_lng)
    q_vec = get_embedding(options["semantic_query"])

    acc_ranks = search_by_accommodation(q_vec, options, top_n=ACC_TOP_N)
    review_ranks = search_by_review(q_vec, options, pool=REVIEW_POOL)

    candidates = fuse_and_rank(acc_ranks, review_ranks, options, top_k=top_n)
    
    formatted_candidates = []
    for c in candidates:
        amenities = c.get('amenities', '')
        if amenities:
            features_list = [f.strip() for f in amenities.split(',') if f.strip()]
            best_feature = features_list[0] if features_list else '다양한 편의시설'
        else:
            best_feature = '편안한 객실'
        
        description = c.get('description')
        if description and len(description) >= 10:
            reason_text = f"💡 {description[:100]}..." if len(description) > 100 else f"💡 {description}"
        else:
            reason_text = f"{c['name']}은(는) {best_feature} 등을 갖추고 있어 일정 중 머무르기 좋은 추천 숙소입니다."

        formatted_candidates.append({
            "accommodation_id": str(c["id"]),
            "name": c["name"],
            "score": c["score"],
            "category": c.get("hotel_style", "숙박시설"),
            "address": c.get("address"),
            "rating": c.get("rating"),
            "review_count": c.get("review_count"),
            "image": c.get("image"),
            "lat": c.get("lat"),
            "lng": c.get("lng"),
            "reason": reason_text,
            "features": f"편의시설: {amenities} / 특징: {c.get('room_features', '')}"
        })
        
    return {
        "candidates": formatted_candidates,
        "origin_lat": user_lat,
        "origin_lng": user_lng,
    }

def search_accommodations_structured(request):
    """
    DomainSearchService 에서 호출될 인터페이스.
    """
    user_message = request.search_query
    current_lat = request.latitude
    current_lng = request.longitude
    top_n = request.candidate_count
    
    intent = parse_user_intent_with_kakao(user_message)
    
    # LLM이 날짜를 추출해 task나 filters에 넣었을 수 있으므로 모든 곳에서 날짜를 찾아본다.
    visit_date_val = request.visit_date
    task = request.context.get("task")
    parsed_query = request.context.get("parsed_query")

    if task and not visit_date_val:
        visit_date_val = task.get("visit_date") if isinstance(task, dict) else getattr(task, "visit_date", None)
    if parsed_query and not visit_date_val:
        filters = parsed_query.get("filters") if isinstance(parsed_query, dict) else getattr(parsed_query, "filters", None)
        if filters:
            visit_date_val = filters.get("start_date") if isinstance(filters, dict) else getattr(filters, "start_date", None)

    end_date_val = None
    if task:
        end_date_val = task.get("end_date") if isinstance(task, dict) else getattr(task, "end_date", None)
    if not end_date_val and parsed_query:
        filters = parsed_query.get("filters") if isinstance(parsed_query, dict) else getattr(parsed_query, "filters", None)
        if filters:
            end_date_val = filters.get("end_date") if isinstance(filters, dict) else getattr(filters, "end_date", None)
            
    if visit_date_val:
        # 문자열인 경우 그대로 사용, date 객체인 경우 isoformat() 호출
        intent["checkin"] = visit_date_val if isinstance(visit_date_val, str) else visit_date_val.isoformat()
        if end_date_val:
            intent["checkout"] = end_date_val if isinstance(end_date_val, str) else end_date_val.isoformat()
        else:
            from datetime import timedelta, date
            if isinstance(visit_date_val, str):
                try:
                    from datetime import datetime
                    v_date = datetime.strptime(visit_date_val, "%Y-%m-%d").date()
                    intent["checkout"] = (v_date + timedelta(days=1)).isoformat()
                except ValueError:
                    pass
            else:
                intent["checkout"] = (visit_date_val + timedelta(days=1)).isoformat()
        
        if intent.get("checkout"):
            intent["is_live_booking"] = True

    is_valid_location = intent["location_type"] != "default"

    if not intent["is_live_booking"] and not is_valid_location:
        return run_local_rag(user_message, user_lat=current_lat, user_lng=current_lng, top_n=top_n)
    
    elif not intent["is_live_booking"] and is_valid_location:
        return run_local_rag(user_message, user_lat=intent["lat"], user_lng=intent["lng"], top_n=top_n)
    
    else:
        try:
            print(f"[DEBUG AccommodationSearchService] Calling run_live_scraper with: location={intent['location']}, checkin={intent['checkin']}, checkout={intent['checkout']}")
            from mcp_server.booking_client import main as run_live_scraper
            scraped_result = run_live_scraper(
                intent["location"], intent["checkin"], intent["checkout"]
            )
            print(f"[DEBUG AccommodationSearchService] run_live_scraper result status: {scraped_result.get('status')}, data length: {len(scraped_result.get('data', []))}")
        except Exception as e:
            print(f"Warning: booking 모듈 불러오기 실패 ({e}). RAG 모드로 Fallback")
            return run_local_rag(user_message, user_lat=intent["lat"], user_lng=intent["lng"], top_n=top_n)

        if not scraped_result or scraped_result.get("status") != "success" or not scraped_result.get("data"):
            print(f"[DEBUG AccommodationSearchService] Scraper failed or returned no data. Falling back to RAG.")
            return run_local_rag(user_message, user_lat=intent["lat"], user_lng=intent["lng"], top_n=top_n)

        if is_valid_location:
            db_hotels = query_hotels_by_radius(
                intent["lat"], intent["lng"], radius_km=MAX_ALLOWABLE_DISTANCE_KM
            )
        else:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
                from domains.accommodation.vector_search import ACCOMMODATION_DB_CONFIG
                conn = psycopg2.connect(**ACCOMMODATION_DB_CONFIG)
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("SELECT id, name, hotel_style, amenities, address, rating, lat, lng, image, review_count, 0.0 as distance FROM accommodation_ko;")
                db_hotels = cur.fetchall()
                cur.close()
                conn.close()
            except Exception as e:
                print(f"DB fallback fetch failed: {e}")
                db_hotels = []

        semantic_query = user_message
        semantic_query = re.sub(r"\d{4}-\d{2}-\d{2}", " ", semantic_query)
        if intent["keyword"] != "서울":
            semantic_query = semantic_query.replace(intent["keyword"], " ")

        semantic_query = re.sub(
            r"\b\w+(부터|까지|에서|으로|보다|해서|하게|하고|하며|에|와|과|랑|을|를|의|은|는|이|가)\b", " ", semantic_query
        )
        semantic_query = re.sub(r"\b(부터|까지|에|에서|랑|와|과)\b", " ", semantic_query)
        domain_stops = ["근처", "주변", "예약", "가능한", "알아봐줘", "추천해줘", "알려줘", "가격", "숙소", "호텔", "있는", "가기", "좋은", "같은", "보석"]
        for stop in domain_stops:
            semantic_query = re.sub(rf"\b{stop}\w*\b", " ", semantic_query)
        semantic_query = re.sub(r"\s+", " ", semantic_query).strip()

        if not semantic_query or len(semantic_query) < 2:
            semantic_query = "숙박시설"

        candidates_map = {}
        used_db_ids = set()
        fallback_counter = 1

        for item in scraped_result["data"]:
            raw_title = item.get("hotel_name", "이름 없음")
            live_price = item.get("live_price", "가격 정보 없음")
            live_rating_str = item.get("live_rating", "0.0")
            booking_url = item.get("booking_url", "#")
            image_url = item.get("image", "")

            cleaned_title = clean_hotel_name_pure(raw_title)
            matched_db, sim_score = find_best_db_match_pure(cleaned_title, db_hotels)

            if matched_db:
                hotel_id = matched_db["id"]
                if hotel_id in used_db_ids: continue

                actual_distance = matched_db["distance"]
                if is_valid_location and actual_distance > MAX_ALLOWABLE_DISTANCE_KM: continue

                used_db_ids.add(hotel_id)
                candidates_map[hotel_id] = {
                    "matched_db": matched_db,
                    "sim_score": sim_score,
                    "live_price": live_price,
                    "live_rating_str": live_rating_str,
                    "booking_url": booking_url,
                    "actual_distance": actual_distance,
                }
            else:
                hotel_id = f"live_{fallback_counter}"
                fallback_counter += 1
                candidates_map[hotel_id] = {
                    "matched_db": {
                        "name": raw_title,
                        "hotel_style": "숙박시설",
                        "address": "서울특별시",
                        "rating": float(live_rating_str) if live_rating_str and live_rating_str != "0.0" else 0.0,
                        "review_count": 0,
                        "image": image_url,
                        "lat": intent["lat"],
                        "lng": intent["lng"],
                        "amenities": "",
                        "room_features": "",
                    },
                    "sim_score": 0.5,
                    "live_price": live_price,
                    "live_rating_str": live_rating_str,
                    "booking_url": booking_url,
                    "actual_distance": 0.0,
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
                live_rating = float(c_data["live_rating_str"]) if c_data["live_rating_str"] else 0.0
                normalized_live_rating = live_rating / 2.0
            except ValueError:
                normalized_live_rating = 0.0

            distance_penalty = c_data["actual_distance"] if is_valid_location else 0.0
            rank_score = normalized_live_rating - (distance_penalty * 0.3) + (norm_rag_score * 5.0)

            amenities = matched_db.get('amenities', '')
            if amenities:
                features_list = [f.strip() for f in amenities.split(',') if f.strip()]
                best_feature = features_list[0] if features_list else '다양한 편의시설'
            else:
                best_feature = '편안한 객실'
                
            description = matched_db.get('description')
            if description and len(description) >= 10:
                reason_text = f"💡 {description[:100]}..." if len(description) > 100 else f"💡 {description}"
            else:
                reason_text = f"{matched_db['name']}은(는) {best_feature} 등을 갖추고 있어 여행 중 편안하게 휴식하기 좋은 곳입니다."

            final_processed_list.append({
                "accommodation_id": str(hotel_id),
                "name": matched_db["name"],
                "score": rank_score,
                "category": matched_db.get("hotel_style", "숙박시설"),
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
                "features": f"편의시설: {amenities} / 특징: {matched_db.get('room_features', '')}"
            })

        final_processed_list.sort(key=lambda x: x["score"], reverse=True)

        if not final_processed_list:
            return run_local_rag(user_message, user_lat=intent["lat"], user_lng=intent["lng"], top_n=top_n)

        return {
            "candidates": final_processed_list[:top_n],
            "origin_lat": intent["lat"],
            "origin_lng": intent["lng"],
        }

from domains.common.agent import DomainAgentDispatchResult
from schemas.travel_query_api import TravelQueryApiResponse
from domains.common.models import DomainSearchRequest
import json

class AccommodationAgent:
    domain = "accommodation"

    async def execute(
        self,
        response: TravelQueryApiResponse,
    ) -> DomainAgentDispatchResult:
        query = response.structured_query
        task_ids = (
            [task.task_id for task in query.tasks if task.domain == self.domain]
            if query is not None
            else []
        )
        
        # 실제 검색을 위해 SearchService 사용
        from domains.accommodation.search_service import AccommodationSearchService
        service = AccommodationSearchService()
        
        if query and query.tasks:
            for task in query.tasks:
                if task.domain == self.domain:
                    # DomainSearchRequest 구성
                    request = DomainSearchRequest(
                        task_id=task.task_id,
                        domain=task.domain,
                        language=getattr(query, 'language', 'ko'),
                        search_query=query.normalized_question,
                        themes=task.themes,
                        location=query.filters.location if query.filters else "서울",
                        latitude=37.5665,  # 기본값
                        longitude=126.9780,
                        current_location_name="서울",
                        candidate_count=task.desired_count or 3,
                        context={
                            "parsed_query": query.model_dump(),
                            "task": task.model_dump()
                        }
                    )
                    
                    try:
                        candidates = await service.search(request)
                        if getattr(query, 'language', 'ko') == 'en':
                            print(f"\n✅ [AccommodationAgent] '{query.normalized_question}' Search Results:")
                            for idx, c in enumerate(candidates, 1):
                                print(f"[{idx}] {c.name}")
                                print(f"   - Recommended Fusion Score: {c.final_score:.2f}")
                                print(f"   - Category: {c.category}")
                                print(f"   - Address: {c.attributes.get('address')}")
                                print(f"   - Rating: {c.attributes.get('rating')} (Reviews: {c.attributes.get('review_count')})")
                                print(f"   - Price: {c.attributes.get('price')}")
                                print(f"   - Amenities: {c.attributes.get('features')}")
                                print(f"   - Link: {c.attributes.get('url')}")
                                print(f"   - Reason: {c.attributes.get('reason')}")
                                print("-" * 60)
                        else:
                            print(f"\n✅ [AccommodationAgent] '{query.normalized_question}' 검색 결과 콘솔 출력:")
                            for idx, c in enumerate(candidates, 1):
                                print(f"[{idx}] {c.name}")
                                print(f"   - 추천 융합 점수: {c.final_score:.2f}")
                                print(f"   - 카테고리: {c.category}")
                                print(f"   - 주소: {c.attributes.get('address')}")
                                print(f"   - 평점: {c.attributes.get('rating')} (리뷰 {c.attributes.get('review_count')}개)")
                                print(f"   - 가격: {c.attributes.get('price')}")
                                print(f"   - 편의시설: {c.attributes.get('features')}")
                                print(f"   - 링크: {c.attributes.get('url')}")
                                print(f"   - 선정 이유: {c.attributes.get('reason')}")
                                print("-" * 60)
                        print("=" * 60)
                    except Exception as e:
                        print(f"[AccommodationAgent] 검색 실패 (Search failed): {e}")
        
        return DomainAgentDispatchResult(
            domain=self.domain,
            task_ids=task_ids,
            assistant_message="accommodation 에이전트가 정상적으로 검색을 완료하고 콘솔에 출력했습니다.",
        )
