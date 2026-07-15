import json
import unittest
from datetime import datetime
from unittest.mock import patch

from services.llm import (
    _candidate_payload,
    _recommendation_payload,
    _sanitize_recommendation,
    _validate_grouped_recommendation_result,
    _validate_recommendation_result,
    generate_recommendation_result,
)
from services.intent import classify_intent
from services.weather import (
    KST,
    _vilage_base_datetime,
    get_forecast_context,
    latlng_to_grid,
    resolve_weather_target,
)
from services.weather_reranker import (
    calculate_weather_fit,
    get_outdoor_confidence,
    prepare_rag_only_candidates,
    rerank_with_weather,
)
from services.rag import (
    _build_weather_menu_features,
    _category_adjustment_status,
    _normalize_unicode_text,
    extract_category,
    is_open_now,
    is_open_at,
)


class RagUnicodeTests(unittest.TestCase):
    def test_decomposed_korean_is_normalized_for_display_and_matching(self):
        decomposed = "라멘트럭랩"
        self.assertEqual(_normalize_unicode_text(decomposed), "라멘트럭랩")


class WeatherGridTests(unittest.TestCase):
    def test_seoul_city_hall_grid(self):
        self.assertEqual(latlng_to_grid(37.5665, 126.9780), (60, 127))


class FutureWeatherTests(unittest.TestCase):
    def test_tomorrow_without_time_defaults_to_dinner(self):
        now = datetime(2026, 7, 13, 10, 0, tzinfo=KST)
        target = resolve_weather_target("내일 가기 좋은 식당", now)
        self.assertEqual(target["target_at"], datetime(2026, 7, 14, 19, 0, tzinfo=KST))
        self.assertEqual(target["label"], "내일 저녁(기본 19시)")
        self.assertTrue(target["is_future"])

    def test_today_dinner_and_tomorrow_lunch(self):
        now = datetime(2026, 7, 13, 10, 0, tzinfo=KST)
        dinner = resolve_weather_target("오늘 저녁에 가기 좋은 곳", now)
        lunch = resolve_weather_target("내일 점심 맛집", now)
        self.assertEqual(dinner["target_at"].hour, 19)
        self.assertEqual(lunch["target_at"].hour, 12)

    def test_evening_seven_means_19_oclock(self):
        now = datetime(2026, 7, 13, 10, 0, tzinfo=KST)
        target = resolve_weather_target("오늘 저녁 7시에 갈 식당", now)
        self.assertEqual(target["target_at"].hour, 19)

    def test_past_today_time_uses_current_weather(self):
        now = datetime(2026, 7, 13, 20, 30, tzinfo=KST)
        target = resolve_weather_target("오늘 저녁 식당", now)
        self.assertFalse(target["is_future"])
        self.assertIn("현재 시각 기준", target["label"])

    def test_latest_published_vilage_base_time(self):
        before_release = datetime(2026, 7, 13, 20, 5, tzinfo=KST)
        after_release = datetime(2026, 7, 13, 20, 15, tzinfo=KST)
        self.assertEqual(_vilage_base_datetime(before_release).hour, 17)
        self.assertEqual(_vilage_base_datetime(after_release).hour, 20)

    @patch("services.weather._request_vilage_forecast")
    def test_forecast_is_normalized_for_target_hour(self, request_forecast):
        request_forecast.return_value = [
            {"fcstDate": "20260714", "fcstTime": "1900", "category": category, "fcstValue": value}
            for category, value in {
                "TMP": "29", "PTY": "1", "POP": "70", "PCP": "1.0mm",
                "WSD": "7.5", "REH": "85", "SKY": "4",
            }.items()
        ]
        result = get_forecast_context(
            37.5665,
            126.9780,
            datetime(2026, 7, 14, 19, 0, tzinfo=KST),
            "내일 저녁(기본 19시)",
            now=datetime(2026, 7, 13, 20, 15, tzinfo=KST),
        )
        self.assertTrue(result["is_forecast"])
        self.assertEqual(result["condition"], "rain")
        self.assertEqual(result["temperature_c"], 29.0)
        self.assertEqual(result["precipitation_probability_pct"], 70.0)
        self.assertEqual(result["sky"], "cloudy")


class RagParserTests(unittest.TestCase):
    def test_category_and_suffix_are_removed_from_review_query(self):
        category, cleaned = extract_category("혼밥하기 좋은 라멘집")
        self.assertEqual(category, "일본 요리")
        self.assertEqual(cleaned, "혼밥하기 좋은")

    def test_short_bar_keyword_does_not_match_banana(self):
        category, _ = extract_category("바나나 디저트")
        self.assertIsNone(category)

    def test_overnight_hours(self):
        monday_late = __import__("datetime").datetime(2026, 7, 13, 23, 0)
        tuesday_early = __import__("datetime").datetime(2026, 7, 14, 1, 0)
        self.assertTrue(is_open_now("월 18:00~02:00", monday_late))
        self.assertTrue(is_open_now("월 18:00~02:00", tuesday_early))

    def test_english_hours_and_future_time(self):
        target = datetime(2026, 7, 15, 19, 0)
        self.assertTrue(is_open_at("Wed 11:00~22:00", target))
        self.assertFalse(is_open_at("Wed 09:00~17:00", target))

    def test_explicit_kakao_cuisine_wins_over_mixed_source_tags(self):
        meta = {"category": "중국 요리, 아시아 요리, 한국", "category_kakao": "중국요리"}
        self.assertEqual(_category_adjustment_status(meta, "한국"), "mismatch")
        self.assertEqual(_category_adjustment_status(meta, "중국 요리"), "match")

    def test_unmapped_kakao_leaf_falls_back_to_source_category(self):
        meta = {"category": "한국", "category_kakao": "칼국수"}
        self.assertEqual(_category_adjustment_status(meta, "한국"), "match")

    def test_future_restaurant_query_routes_to_rag_and_weather(self):
        self.assertEqual(classify_intent("내일 가기 좋은 곳", "ko", []), "both")
        self.assertEqual(classify_intent("오늘 저녁에 갈 식당 추천", "ko", []), "both")


class WeatherRerankerTests(unittest.TestCase):
    def test_rag_only_never_applies_weather_or_changes_order(self):
        candidates = [
            {"restaurant_id": 1, "score": 0.900, "distance_km": 2.0},
            {"restaurant_id": 2, "score": 0.899, "distance_km": 0.2, "has_parking": True},
        ]
        weather = {"available": True, "condition": "rain", "wind_speed_mps": 9.0}

        result = rerank_with_weather(
            candidates,
            weather,
            "비 오는 날 식당 추천",
            source_mode="RAG_ONLY",
        )

        self.assertEqual([item["restaurant_id"] for item in result], [1, 2])
        self.assertEqual([item["score"] for item in result], [0.900, 0.899])
        self.assertTrue(all(item["weather_score"] is None for item in result))
        self.assertTrue(all(item["weather_reasons"] == [] for item in result))

    def test_prepare_rag_only_removes_stale_weather_values(self):
        candidates = [{
            "restaurant_id": 1,
            "score": 0.8,
            "weather_score": 0.9,
            "weather_reasons": ["이전 요청의 날씨 근거"],
            "outdoor_confidence": "high",
        }]

        result = prepare_rag_only_candidates(candidates)

        self.assertEqual(result[0]["score"], 0.8)
        self.assertEqual(result[0]["rag_score"], 0.8)
        self.assertIsNone(result[0]["weather_score"])
        self.assertEqual(result[0]["weather_reasons"], [])
        self.assertNotIn("outdoor_confidence", result[0])

    def test_rain_rewards_nearby_parking_without_overriding_rag(self):
        candidates = [
            {
                "restaurant_id": 1,
                "score": 0.90,
                "distance_km": 2.0,
                "has_parking": False,
                "evidence": {"menus": []},
            },
            {
                "restaurant_id": 2,
                "score": 0.60,
                "distance_km": 0.5,
                "has_parking": True,
                "evidence": {"menus": []},
            },
        ]
        weather = {"available": True, "condition": "rain", "feels_like": "mild"}
        result = rerank_with_weather(candidates, weather, "데이트 식당 추천")

        self.assertEqual(result[0]["restaurant_id"], 1)
        parking_candidate = next(item for item in result if item["restaurant_id"] == 2)
        plain_candidate = next(item for item in result if item["restaurant_id"] == 1)
        self.assertGreater(parking_candidate["weather_score"], plain_candidate["weather_score"])
        self.assertEqual(len(parking_candidate["weather_reasons"]), 2)

    def test_explicit_weather_intent_can_break_close_scores(self):
        candidates = [
            {
                "restaurant_id": 1,
                "score": 0.900,
                "distance_km": 2.0,
                "has_parking": False,
                "evidence": {"menus": []},
            },
            {
                "restaurant_id": 2,
                "score": 0.899,
                "distance_km": 0.5,
                "has_parking": True,
                "evidence": {"menus": []},
            },
        ]
        weather = {"available": True, "condition": "rain", "feels_like": "mild"}
        result = rerank_with_weather(candidates, weather, "비 오는 날 식당 추천")
        self.assertEqual(result[0]["restaurant_id"], 2)

    def test_weather_failure_keeps_rag_order(self):
        candidates = [
            {"restaurant_id": 1, "score": 0.9},
            {"restaurant_id": 2, "score": 0.8},
        ]
        result = rerank_with_weather(candidates, {"available": False}, "맛집")
        self.assertEqual([item["restaurant_id"] for item in result], [1, 2])
        self.assertIsNone(result[0]["weather_score"])

    def test_hot_weather_uses_full_menu_features_not_semantic_evidence(self):
        candidate = {
            "restaurant_id": 1,
            "score": 0.9,
            "evidence": {"menus": []},
            "weather_features": {
                "has_cool_menu": True,
                "has_warm_menu": False,
                "cool_menu_matches": ["물냉면"],
                "warm_menu_matches": [],
            },
        }
        score, reasons = calculate_weather_fit(
            candidate,
            {"available": True, "condition": "clear", "temperature_c": 31.0},
        )
        self.assertEqual(score, 0.65)
        self.assertIn("물냉면", reasons[0])

    def test_false_and_unknown_parking_are_both_neutral(self):
        weather = {"available": True, "condition": "rain", "temperature_c": 15.0}
        false_score, _ = calculate_weather_fit(
            {"restaurant_id": 1, "score": 1.0, "has_parking": False}, weather
        )
        unknown_score, _ = calculate_weather_fit(
            {"restaurant_id": 2, "score": 1.0, "has_parking": None}, weather
        )
        self.assertEqual(false_score, unknown_score)

    def test_rain_and_strong_wind_penalize_far_outdoor_candidate(self):
        candidate = {
            "restaurant_id": 1,
            "score": 0.9,
            "distance_km": 1.6,
            "has_parking": None,
            "description": "도심 루프탑에서 즐기는 식사",
        }
        score, reasons = calculate_weather_fit(
            candidate,
            {
                "available": True,
                "condition": "rain",
                "temperature_c": 15.0,
                "wind_speed_mps": 8.0,
            },
        )
        self.assertAlmostEqual(score, 0.15)
        self.assertEqual(len(reasons), 4)


class WeatherMenuFeatureTests(unittest.TestCase):
    def test_korean_features_use_all_menus_and_avoid_tangsuyuk_false_positive(self):
        rows = [
            {"restaurant_id": 1, "menu_name": "갈비탕", "is_main": True, "menu_order": 1},
            {"restaurant_id": 1, "menu_name": "물냉면", "is_main": False, "menu_order": 2},
            {"restaurant_id": 2, "menu_name": "탕수육", "is_main": True, "menu_order": 1},
            {"restaurant_id": 3, "menu_name": "닭한마리", "is_main": True, "menu_order": 1},
            {"restaurant_id": 4, "menu_name": "불고기샐러드피자", "is_main": True, "menu_order": 1},
            {"restaurant_id": 5, "menu_name": "초계탕", "is_main": True, "menu_order": 1},
        ]
        features = _build_weather_menu_features(rows, [1, 2, 3, 4, 5], "ko")

        self.assertTrue(features[1]["has_warm_menu"])
        self.assertTrue(features[1]["has_cool_menu"])
        self.assertEqual(features[1]["warm_menu_matches"], ["갈비탕"])
        self.assertEqual(features[1]["cool_menu_matches"], ["물냉면"])
        self.assertFalse(features[2]["has_warm_menu"])
        self.assertTrue(features[3]["has_warm_menu"])
        self.assertFalse(features[3]["has_cool_menu"])
        self.assertFalse(features[4]["has_cool_menu"])
        self.assertFalse(features[5]["has_warm_menu"])
        self.assertTrue(features[5]["has_cool_menu"])

    def test_english_features_are_separate(self):
        rows = [
            {"restaurant_id": 1, "menu_name": "Beef noodle soup", "is_main": True, "menu_order": 1},
            {"restaurant_id": 1, "menu_name": "Cold noodles", "is_main": True, "menu_order": 2},
        ]
        features = _build_weather_menu_features(rows, [1], "en")
        self.assertTrue(features[1]["has_warm_menu"])
        self.assertTrue(features[1]["has_cool_menu"])

    def test_generic_salad_is_not_a_hot_weather_cool_menu(self):
        rows = [
            {"restaurant_id": 1, "menu_name": "치킨 시저 샐러드", "is_main": True, "menu_order": 1},
            {"restaurant_id": 2, "menu_name": "Chicken Caesar salad", "is_main": True, "menu_order": 1},
        ]
        ko = _build_weather_menu_features(rows[:1], [1], "ko")
        en = _build_weather_menu_features(rows[1:], [2], "en")
        self.assertFalse(ko[1]["has_cool_menu"])
        self.assertFalse(en[2]["has_cool_menu"])

    def test_only_strong_description_terms_mark_outdoor_high(self):
        self.assertEqual(
            get_outdoor_confidence({"description": "한강이 보이는 루프탑 바"}),
            "high",
        )
        self.assertEqual(
            get_outdoor_confidence({"description": "도심 정원 뷰와 넓은 통창"}),
            "unknown",
        )
        self.assertEqual(
            get_outdoor_confidence({"description": "현재 테라스는 운영하지 않습니다."}),
            "unknown",
        )
        self.assertEqual(
            get_outdoor_confidence({"description": "No outdoor seating is available."}),
            "unknown",
        )

    def test_cold_or_stir_fried_udon_is_not_a_warm_menu(self):
        rows = [
            {"restaurant_id": 1, "menu_name": "닭다리살 야끼우동", "is_main": True, "menu_order": 1},
            {"restaurant_id": 2, "menu_name": "냉우동", "is_main": True, "menu_order": 1},
            {"restaurant_id": 3, "menu_name": "Yaki udon", "is_main": True, "menu_order": 1},
        ]
        ko = _build_weather_menu_features(rows[:2], [1, 2], "ko")
        en = _build_weather_menu_features(rows[2:], [3], "en")
        self.assertFalse(ko[1]["has_warm_menu"])
        self.assertFalse(ko[2]["has_warm_menu"])
        self.assertTrue(ko[2]["has_cool_menu"])
        self.assertFalse(en[3]["has_warm_menu"])

    def test_llm_payload_contains_weather_menu_evidence(self):
        payload = _candidate_payload([{
            "restaurant_id": 1,
            "name": "테스트 식당",
            "score": 0.8,
            "weather_score": 0.65,
            "weather_reasons": ["더운 날 어울리는 시원한 메뉴가 있음 (물냉면)"],
            "weather_features": {
                "warm_menu_matches": [],
                "cool_menu_matches": ["물냉면"],
            },
            "evidence": {"menus": [], "reviews": []},
        }])
        self.assertEqual(payload[0]["weather_suitable_menus"], ["물냉면"])
        self.assertNotIn("description", payload[0])

    def test_llm_payload_contains_only_confirmed_filter_evidence(self):
        payload = _candidate_payload([{
            "restaurant_id": 1,
            "name": "테스트 식당",
            "score": 0.8,
            "category": "한국",
            "category_kakao": "한식",
            "open_status": True,
            "open_status_basis": "requested_time",
            "menu_price_min": 9000,
            "menu_price_median": 18000,
            "has_parking": True,
            "has_private_room": True,
            "allows_pets": None,
            "has_group_seating": False,
            "evidence": {"menus": [], "reviews": []},
        }], include_weather=False)
        item = payload[0]
        self.assertTrue(item["opening_status"])
        self.assertEqual(item["opening_status_basis"], "requested_time")
        self.assertEqual(item["menu_price_median_krw"], 18000)
        self.assertEqual(item["confirmed_features"], ["parking", "private_room"])
        self.assertNotIn("pets_allowed", item["confirmed_features"])

    def test_llm_payload_hides_unrequested_current_open_status(self):
        payload = _candidate_payload([{
            "restaurant_id": 1,
            "name": "테스트 식당",
            "score": 0.8,
            "open_status": True,
            "open_status_basis": None,
            "evidence": {"menus": [], "reviews": []},
        }], include_weather=False)
        self.assertNotIn("opening_status", payload[0])
        self.assertNotIn("opening_status_basis", payload[0])

    def test_llm_payload_hides_inactive_weather_menus(self):
        payload = _candidate_payload([{
            "restaurant_id": 1,
            "name": "테스트 식당",
            "score": 0.8,
            "weather_reasons": ["비나 눈이 올 때 편리한 주차 가능"],
            "weather_features": {
                "warm_menu_matches": ["우동"],
                "cool_menu_matches": ["냉면"],
            },
            "evidence": {"menus": [], "reviews": []},
        }])
        self.assertEqual(payload[0]["weather_suitable_menus"], [])
        self.assertNotIn("rag_score", payload[0])
        self.assertNotIn("weather_score", payload[0])

    def test_rag_only_final_payload_contains_no_weather_data(self):
        candidate = {
            "restaurant_id": 1,
            "name": "테스트 식당",
            "score": 0.8,
            "weather_reasons": ["이전 요청의 날씨 근거"],
            "weather_features": {"cool_menu_matches": ["냉면"]},
            "evidence": {"menus": [], "reviews": []},
        }

        payload = _recommendation_payload(
            "조용한 식당 추천",
            "ko",
            [candidate],
            weather={"available": True, "condition": "rain"},
            source_mode="RAG_ONLY",
        )

        self.assertNotIn("weather", payload)
        self.assertNotIn("weather_reasons", payload["candidates"][0])
        self.assertNotIn("weather_suitable_menus", payload["candidates"][0])

    def test_recommendation_payload_keeps_structured_request(self):
        candidate = {
            "restaurant_id": 1,
            "name": "테스트 식당",
            "score": 0.8,
            "evidence": {"menus": [], "reviews": []},
        }
        context = {
            "intent": "single_place_recommendation",
            "task": {"desired_count": 1},
            "filters": {"party_size": 4},
        }
        payload = _recommendation_payload(
            "식당 추천",
            "ko",
            [candidate],
            source_mode="RAG_ONLY",
            structured_context=context,
        )
        self.assertEqual(payload["structured_request"], context)

    def test_llm_output_sanitizes_internal_terms_and_empty_fields(self):
        text = """후보 데이터에 명시된 항목만 골라 추천합니다.
- 메뉴(후보 데이터): (메뉴 필드 비어있음)
- weather_reasons 기준 추천
원하시면 예약 가능 여부와 길 안내를 찾아드릴게요."""
        sanitized = _sanitize_recommendation(text)
        self.assertNotIn("후보 데이터", sanitized)
        self.assertNotIn("weather_reasons", sanitized)
        self.assertNotIn("메뉴 필드", sanitized)
        self.assertNotIn("예약 가능", sanitized)
        self.assertIn("예산이나 분위기", sanitized)

    def test_llm_output_naturalizes_internal_facility_identifiers(self):
        sanitized = _sanitize_recommendation(
            "개인실 보유(confirmed_features: private_room, parking)로 편리합니다."
        )
        self.assertNotIn("confirmed_features", sanitized)
        self.assertNotIn("private_room", sanitized)
        self.assertIn("개인실", sanitized)
        self.assertIn("주차", sanitized)

    def test_llm_output_naturalizes_standalone_private_room_identifier(self):
        sanitized = _sanitize_recommendation(
            "개인룸(private_room)을 갖춘 조용한 식당입니다."
        )
        self.assertNotIn("private_room", sanitized)
        self.assertIn("개인실", sanitized)

    def test_llm_selection_rejects_unknown_and_duplicate_ids_then_fills_to_three(self):
        candidates = [
            {
                "restaurant_id": restaurant_id,
                "name": f"식당 {restaurant_id}",
                "category": "한식",
                "score": 1.0 / restaurant_id,
                "evidence": {"menus": [], "reviews": []},
            }
            for restaurant_id in range(1, 11)
        ]
        raw = """```json
        {"answer":"추천 결과", "selections":[
          {"restaurant_id":"3", "selection_reason":"요청과 잘 맞음"},
          {"restaurant_id":"3", "selection_reason":"중복"},
          {"restaurant_id":"999", "selection_reason":"없는 후보"}
        ]}
        ```"""

        result = _validate_recommendation_result(raw, candidates, include_weather=False)

        ids = [str(item["candidate"]["restaurant_id"]) for item in result["selections"]]
        self.assertEqual(ids, ["3", "1", "2"])
        self.assertEqual(len(set(ids)), 3)
        self.assertNotEqual(result["answer"], "추천 결과")

    def test_single_recommendation_candidate_returns_exactly_one(self):
        candidates = [{
            "restaurant_id": 77,
            "name": "유일한 식당",
            "category": "한식",
            "score": 1.0,
            "evidence": {"menus": [], "reviews": []},
        }]
        raw = '{"answer":"한 곳 추천","selections":[{"restaurant_id":"999","selection_reason":"가짜"}]}'
        result = _validate_recommendation_result(raw, candidates, include_weather=False)
        self.assertEqual(len(result["selections"]), 1)
        self.assertEqual(str(result["selections"][0]["candidate"]["restaurant_id"]), "77")
        self.assertNotIn("가짜", result["selections"][0]["selection_reason"])

    def test_single_recommendation_llm_failure_keeps_ranked_candidate(self):
        candidates = [{
            "restaurant_id": 77,
            "name": "유일한 식당",
            "category": "한식",
            "score": 1.0,
            "evidence": {"menus": [], "reviews": []},
        }]
        with patch("services.llm._client", side_effect=RuntimeError("offline")):
            result = generate_recommendation_result(
                "한 곳 추천", "ko", candidates, source_mode="rag_only"
            )
        self.assertEqual(len(result["selections"]), 1)
        self.assertEqual(result["selections"][0]["candidate"]["restaurant_id"], 77)
        self.assertTrue(result["llm_fallback_used"])

    def test_empty_candidates_skip_llm_and_return_clear_no_result(self):
        with patch("services.llm._client") as client:
            result = generate_recommendation_result(
                "아이와 갈 식당", "ko", [], source_mode="rag_only"
            )
        client.assert_not_called()
        self.assertEqual(result["selections"], [])
        self.assertTrue(result["no_candidates"])
        self.assertIn("찾지 못했습니다", result["answer"])

    def test_recommendation_payload_requests_three_from_top_ten(self):
        candidates = [
            {
                "restaurant_id": restaurant_id,
                "name": f"식당 {restaurant_id}",
                "score": 1.0,
                "evidence": {"menus": [], "reviews": []},
            }
            for restaurant_id in range(1, 13)
        ]
        payload = _recommendation_payload(
            "식당 추천", "ko", candidates, source_mode="RAG_ONLY"
        )
        self.assertEqual(payload["selection_count"], 3)
        self.assertEqual(len(payload["candidates"]), 10)

    def test_grouped_selection_cannot_mix_domains_and_fills_each_group(self):
        groups = []
        for task_id, domain, prefix in (("r1", "restaurant", "r"), ("c1", "cafe", "c")):
            groups.append({
                "task_id": task_id,
                "domain": domain,
                "candidates": [
                    {
                        "place_id": f"{prefix}{index}",
                        "name": f"{domain} {index}",
                        "fallback_reason": "순위 보충",
                    }
                    for index in range(1, 6)
                ],
            })
        raw = json.dumps({
            "answer": "잘못 섞인 결과",
            "task_results": [
                {
                    "task_id": "r1", "domain": "restaurant",
                    "selections": [
                        {"place_id": "c1", "selection_reason": "다른 도메인"},
                        {"place_id": "r2", "selection_reason": "정상"},
                        {"place_id": "r2", "selection_reason": "중복"},
                    ],
                },
                {
                    "task_id": "c1", "domain": "restaurant",
                    "selections": [{"place_id": "c3", "selection_reason": "도메인 오류"}],
                },
            ],
        }, ensure_ascii=False)

        result = _validate_grouped_recommendation_result(raw, groups)

        restaurant_ids = [
            item["candidate"]["place_id"]
            for item in result["task_results"][0]["selections"]
        ]
        cafe_ids = [
            item["candidate"]["place_id"]
            for item in result["task_results"][1]["selections"]
        ]
        self.assertEqual(restaurant_ids, ["r2", "r1", "r3"])
        self.assertEqual(cafe_ids, ["c1", "c2", "c3"])


if __name__ == "__main__":
    unittest.main()
