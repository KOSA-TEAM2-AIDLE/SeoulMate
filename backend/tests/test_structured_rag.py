import unittest
from datetime import date
from unittest.mock import patch

from schemas.chat import ChatRequest
from schemas.structured_query import StructuredTravelQuery
from services.query_policy import (
    build_menu_query,
    build_semantic_query,
    deduplicate_recommendation_tasks,
    derive_source_mode,
    effective_query_language,
    trusted_visit_date,
)
from services.rag import build_restaurant_search_plan, search_restaurants_structured
from services.rag import _extract_required_menu_terms


def parsed_query(
    question: str,
    *,
    search_query: str | None = None,
    themes: list[str] | None = None,
    start_date: str | None = None,
    is_active: bool | None = None,
    intent: str = "single_place_recommendation",
    tasks: list[dict] | None = None,
    language: str = "ko",
    location: str | None = "홍대",
):
    if tasks is None:
        tasks = [] if search_query is None else [{
            "task_id": "task_1",
            "domain": "restaurant",
            "search_query": search_query,
            "themes": themes or [],
            "desired_count": 1,
            "notes": None,
        }]
    return StructuredTravelQuery.model_validate({
        "language": language,
        "intent": intent,
        "original_question": question,
        "normalized_question": question,
        "tasks": tasks,
        "filters": {
            "location": location,
            "is_active": is_active,
            "start_date": start_date,
        },
        "route_context": None,
        "general_response_instruction": (
            "일반 질문에 답한다." if intent == "general_response" else None
        ),
    })


class StructuredQueryPolicyTests(unittest.TestCase):
    @staticmethod
    def day_route_payload(task_count: int, target_count: int | None = None) -> dict:
        domains = ["attraction", "restaurant", "cafe", "attraction", "restaurant"]
        route_request = {
            "destination": "홍대",
            "period": {
                "start_date": "2026-07-16",
                "end_date": "2026-07-16",
                "nights": 0,
                "days": 1,
            },
            "max_places_per_day": 5,
        }
        if target_count is not None:
            route_request["target_places_per_day"] = target_count
        return {
            "language": "ko",
            "intent": "day_trip_route",
            "original_question": "내일 홍대 당일 루트를 짜줘",
            "normalized_question": "홍대 당일 루트",
            "tasks": [
                {
                    "task_id": f"task_{index + 1}",
                    "domain": domains[index],
                    "search_query": f"홍대 {domains[index]} {index + 1}",
                    "desired_count": 1,
                }
                for index in range(task_count)
            ],
            "filters": {"location": "홍대"},
            "route_request": route_request,
        }

    def test_single_recommendation_always_normalizes_to_three_choices(self):
        parsed = parsed_query(
            "식당 한 곳 추천해줘",
            tasks=[{
                "task_id": "1",
                "domain": "restaurant",
                "search_query": "식당",
                "desired_count": 1,
            }],
        )
        self.assertEqual(parsed.tasks[0].desired_count, 3)

    def test_day_route_accepts_exact_two_place_target(self):
        parsed = StructuredTravelQuery.model_validate(self.day_route_payload(2, 2))
        self.assertEqual(len(parsed.tasks), 2)
        self.assertEqual(parsed.route_request.target_places_per_day, 2)
        self.assertTrue(all(task.desired_count == 1 for task in parsed.tasks))

    def test_day_route_accepts_exact_five_place_target(self):
        parsed = StructuredTravelQuery.model_validate(self.day_route_payload(5, 5))
        self.assertEqual(len(parsed.tasks), 5)
        self.assertEqual(parsed.route_request.target_places_per_day, 5)

    def test_day_route_rejects_underfilled_target(self):
        with self.assertRaises(ValueError):
            StructuredTravelQuery.model_validate(self.day_route_payload(2, 5))

    def test_day_route_without_target_remains_backward_compatible(self):
        parsed = StructuredTravelQuery.model_validate(self.day_route_payload(2))
        self.assertEqual(len(parsed.tasks), 2)
        self.assertIsNone(parsed.route_request.target_places_per_day)

    def test_multi_day_missing_task_dates_split_after_accommodation(self):
        parsed = StructuredTravelQuery.model_validate({
            "language": "ko",
            "intent": "multi_day_route",
            "original_question": "내일부터 1박 2일 루트",
            "normalized_question": "서울 1박 2일 루트",
            "tasks": [
                {"task_id": "dinner", "domain": "restaurant", "search_query": "홍대 한식당"},
                {"task_id": "hotel", "domain": "accommodation", "search_query": "홍대 숙박"},
                {"task_id": "cafe", "domain": "cafe", "search_query": "성수 카페"},
            ],
            "filters": {"location": "서울"},
            "route_request": {
                "destination": "서울",
                "period": {
                    "start_date": "2026-07-16", "end_date": "2026-07-17",
                    "nights": 1, "days": 2,
                },
            },
        })
        self.assertEqual([task.day_number for task in parsed.tasks], [1, 1, 2])
        self.assertEqual(
            [str(task.visit_date) for task in parsed.tasks],
            ["2026-07-16", "2026-07-16", "2026-07-17"],
        )
        self.assertEqual(
            [task.slot_id for task in parsed.tasks],
            ["d1-restaurant-1", "d1-accommodation-1", "d2-cafe-1"],
        )

    def test_multi_day_accommodation_gets_safe_checkout_defaults(self):
        parsed = parsed_query(
            "내일부터 1박 2일 루트",
            intent="multi_day_route",
            tasks=[{
                "task_id": "hotel", "slot_id": "d1-accommodation-1",
                "domain": "accommodation", "search_query": "홍대 숙박",
                "day_number": 1, "visit_date": "2026-07-16", "start_time": "22:00",
            }],
        )
        hotel = parsed.tasks[0]
        self.assertEqual(str(hotel.end_date), "2026-07-17")
        self.assertEqual(hotel.end_time, "08:00")

    def test_weather_task_is_removed_from_place_search_tasks(self):
        parsed = parsed_query(
            "내일 홍대 날씨를 보고 식당 추천해줘",
            tasks=[
                {"task_id": "1", "domain": "restaurant", "search_query": "홍대 식당"},
                {"task_id": "2", "domain": "weather", "search_query": "내일 홍대 날씨"},
            ],
        )
        self.assertEqual([task.domain for task in parsed.tasks], ["restaurant"])

    def test_weather_conditioned_domain_duplicates_are_merged(self):
        parsed = parsed_query(
            "내일 홍대에서 조용한 저녁 식당과 비가 와도 가기 편한 카페를 추천해줘",
            tasks=[
                {"task_id": "1", "domain": "restaurant", "search_query": "조용한 저녁 식당"},
                {"task_id": "2", "domain": "cafe", "search_query": "비가 와도 가기 편한 카페"},
                {"task_id": "3", "domain": "cafe", "search_query": "비 오는 날 가기 편한 카페"},
                {"task_id": "4", "domain": "restaurant", "search_query": "비 오는 날 가기 편한 저녁 식당"},
            ],
        )
        normalized = deduplicate_recommendation_tasks(parsed)
        self.assertEqual(
            [(task.task_id, task.domain) for task in normalized.tasks],
            [("1", "restaurant"), ("2", "cafe")],
        )

    def test_specific_menu_terms_are_explicit_but_cuisine_is_not(self):
        self.assertEqual(_extract_required_menu_terms("홍대 마라탕 식당", "ko"), ("마라탕",))
        self.assertEqual(_extract_required_menu_terms("홍대 떡볶이 식당", "ko"), ("떡볶이",))
        self.assertEqual(_extract_required_menu_terms("이태원 쌀국수", "ko"), ("쌀국수",))
        self.assertEqual(_extract_required_menu_terms("홍대 중식당", "ko"), ())
        self.assertEqual(_extract_required_menu_terms("quiet ramen restaurant", "en"), ("ramen",))
        self.assertEqual(_extract_required_menu_terms("find pho nearby", "en"), ("pho",))

    def test_exact_duplicate_tasks_are_merged_without_losing_themes(self):
        parsed = parsed_query(
            "홍대에서 조용한 식당 추천해줘",
            tasks=[
                {
                    "task_id": "1", "domain": "restaurant",
                    "search_query": "홍대 조용한 식당", "themes": ["조용한"],
                    "desired_count": 1,
                },
                {
                    "task_id": "2", "domain": "restaurant",
                    "search_query": "홍대  조용한 식당!", "themes": ["대화"],
                    "desired_count": 3,
                    "filters": {"location": "홍대"},
                },
            ],
        )

        normalized = deduplicate_recommendation_tasks(parsed)

        self.assertEqual(len(normalized.tasks), 1)
        self.assertEqual(normalized.tasks[0].task_id, "1")
        self.assertEqual(normalized.tasks[0].themes, ["조용한", "대화"])
        self.assertEqual(normalized.tasks[0].desired_count, 3)

    def test_distinct_same_domain_tasks_are_not_merged(self):
        parsed = parsed_query(
            "홍대에서 한식당과 중식당을 각각 추천해줘",
            tasks=[
                {
                    "task_id": "1", "domain": "restaurant",
                    "search_query": "홍대 한식당", "desired_count": 1,
                },
                {
                    "task_id": "2", "domain": "restaurant",
                    "search_query": "홍대 중식당", "desired_count": 1,
                },
            ],
        )

        normalized = deduplicate_recommendation_tasks(parsed)

        self.assertEqual([task.task_id for task in normalized.tasks], ["1", "2"])

    def test_tomorrow_restaurant_uses_rag_mcp(self):
        parsed = parsed_query(
            "내일 갈 조용한 중식당 추천해줘",
            search_query="홍대 조용한 중식당",
            themes=["조용한"],
            start_date="2026-07-15",
        )
        self.assertEqual(derive_source_mode(parsed), "rag_mcp")

    def test_low_congestion_attraction_request_uses_rag_mcp(self):
        parsed = parsed_query(
            "경복궁 근처 한적한 문화시설 추천",
            tasks=[{
                "task_id": "1",
                "domain": "attraction",
                "search_query": "경복궁 한적한 문화시설",
                "themes": ["한적한", "문화시설"],
                "desired_count": 3,
            }],
            location="경복궁",
        )

        self.assertEqual(derive_source_mode(parsed), "rag_mcp")

    def test_undated_restaurant_uses_rag_only(self):
        parsed = parsed_query(
            "조용한 중식당 추천해줘",
            search_query="홍대 조용한 중식당",
            themes=["조용한"],
        )
        self.assertEqual(derive_source_mode(parsed), "rag_only")

    def test_weather_only_and_general_paths(self):
        weather = parsed_query(
            "내일 서울 날씨 알려줘",
            tasks=[],
            intent="weather_information",
            location="서울",
        )
        general = parsed_query(
            "파이썬 리스트와 튜플 차이",
            tasks=[],
            intent="general_response",
            location=None,
        )
        self.assertEqual(derive_source_mode(weather), "mcp_only")
        self.assertEqual(derive_source_mode(general), "general")

    def test_mixed_route_keeps_domain_tasks_separate(self):
        parsed = parsed_query(
            "내일 홍대에서 저녁을 먹고 분위기 좋은 카페도 가고 싶어",
            intent="day_trip_route",
            start_date="2026-07-15",
            tasks=[
                {
                    "task_id": "task_1",
                    "domain": "restaurant",
                    "search_query": "홍대 저녁 식사",
                    "themes": ["저녁", "식사"],
                    "desired_count": 1,
                },
                {
                    "task_id": "task_2",
                    "domain": "cafe",
                    "search_query": "홍대 분위기 좋은 카페",
                    "themes": ["분위기 좋은"],
                    "desired_count": 1,
                },
            ],
        )
        restaurant_task = next(task for task in parsed.tasks if task.domain == "restaurant")
        text = build_semantic_query(restaurant_task, parsed.filters)
        self.assertEqual(derive_source_mode(parsed), "rag_mcp")
        self.assertNotIn("카페", text)
        self.assertNotIn("홍대", text)

    def test_english_task_uses_structured_text_without_location_noise(self):
        parsed = parsed_query(
            "Find a quiet Chinese restaurant in Hongdae tomorrow",
            search_query="Hongdae quiet Chinese restaurant",
            themes=["quiet"],
            start_date="2026-07-15",
            language="en",
            location="Hongdae",
        )
        text = build_semantic_query(parsed.tasks[0], parsed.filters)
        self.assertEqual(text, "quiet Chinese restaurant")
        self.assertEqual(derive_source_mode(parsed), "rag_mcp")

    def test_explicit_weekday_overrides_wrong_parser_date_and_mode(self):
        parsed = parsed_query(
            "이번 토요일 오후 3시에 종로 식당 추천",
            search_query="종로 식당",
            location="종로",
        )
        parsed.source_mode = "rag_only"
        parsed.filters.time_window = "2026-07-16T15:00:00"
        self.assertEqual(trusted_visit_date(parsed, date(2026, 7, 14)), date(2026, 7, 18))
        self.assertEqual(derive_source_mode(parsed), "rag_mcp")
        plan = build_restaurant_search_plan(parsed, parsed.tasks[0])
        self.assertEqual(plan.target_visit_at.hour, 15)

    def test_filter_only_themes_do_not_pollute_vectors_and_menu_has_own_query(self):
        parsed = parsed_query(
            "홍대 중식당 중 평점 4.5 이상이고 3만원 이하",
            search_query="홍대 조용한 중식당",
            themes=["조용한", "평점 4.5 이상", "3만원 이하"],
        )
        semantic = build_semantic_query(parsed.tasks[0], parsed.filters)
        menu = build_menu_query(parsed.tasks[0], parsed.filters)
        self.assertEqual(semantic, "조용한 중식당")
        self.assertEqual(menu, "조용한 중식당")
        self.assertNotIn("4.5", semantic)
        self.assertNotIn("3만원", semantic)

    def test_null_lists_from_function_calling_are_normalized(self):
        parsed = StructuredTravelQuery.model_validate({
            "language": "ko",
            "intent": "single_place_recommendation",
            "original_question": "식당 추천",
            "normalized_question": "식당 추천",
            "tasks": [{
                "task_id": "1", "domain": "restaurant", "search_query": "식당",
                "themes": None, "desired_count": 1,
            }],
            "filters": {
                "transportation": None, "accessibility": None,
                "required_features": None, "excluded_features": None,
            },
        })
        self.assertEqual(parsed.tasks[0].themes, [])
        self.assertEqual(parsed.filters.required_features, [])

    def test_null_global_filters_from_function_calling_are_normalized(self):
        parsed = StructuredTravelQuery.model_validate({
            "language": "ko",
            "intent": "single_place_recommendation",
            "original_question": "식당 추천",
            "normalized_question": "식당 추천",
            "tasks": [{
                "task_id": "1", "domain": "restaurant", "search_query": "식당",
            }],
            "filters": None,
        })
        self.assertIsNone(parsed.filters.location)


class StructuredRestaurantPlanTests(unittest.TestCase):
    @patch("services.rag.geocode_kakao")
    def test_task_local_location_overrides_global_location(self, geocode):
        geocode.return_value = (37.4979, 127.0276, "강남")
        parsed = parsed_query(
            "홍대 식당과 강남 식당",
            location="홍대",
            tasks=[{
                "task_id": "gangnam_restaurant",
                "domain": "restaurant",
                "search_query": "강남 중식당",
                "filters": {"location": "강남", "radius_km": 2},
            }],
        )
        plan = build_restaurant_search_plan(parsed, parsed.tasks[0])
        self.assertEqual(plan.location_name, "강남")
        self.assertEqual(plan.origin_lat, 37.4979)
        self.assertNotIn("강남", plan.retrieval_query)

    @patch("services.rag.geocode_kakao")
    def test_location_is_recovered_from_task_query_when_task_filters_are_null(self, geocode):
        geocode.return_value = (37.5563, 126.9236, "홍대")
        parsed = parsed_query(
            "홍대 식당과 강남 카페",
            location="서울",
            tasks=[{
                "task_id": "hongdae_restaurant",
                "domain": "restaurant",
                "search_query": "홍대 식당",
                "filters": None,
            }],
        )
        plan = build_restaurant_search_plan(parsed, parsed.tasks[0])
        self.assertEqual(plan.location_name, "홍대")
        self.assertNotIn("홍대", plan.retrieval_query)

    def test_plan_extracts_cuisine_from_task_not_original_question(self):
        parsed = parsed_query(
            "내일 갈 곳을 추천해줘",
            search_query="홍대 조용한 중식당",
            themes=["조용한"],
            start_date="2026-07-15",
        )
        plan = build_restaurant_search_plan(
            parsed,
            parsed.tasks[0],
            current_lat=37.5563,
            current_lng=126.9236,
        )
        self.assertEqual(plan.requested_category, "중국 요리")
        self.assertNotIn("홍대", plan.retrieval_query)
        self.assertIn("조용한", plan.review_query)
        self.assertTrue(plan.include_weather_features)
        self.assertFalse(plan.open_now)

    def test_rag_only_skips_weather_menu_feature_query(self):
        parsed = parsed_query(
            "조용한 중식당 추천",
            search_query="홍대 조용한 중식당",
            themes=["조용한"],
        )
        plan = build_restaurant_search_plan(parsed, parsed.tasks[0])
        self.assertFalse(plan.include_weather_features)

    def test_future_is_active_does_not_become_open_now(self):
        future = parsed_query(
            "내일 저녁 영업하는 식당",
            search_query="홍대 저녁 식당",
            start_date="2026-07-15",
            is_active=True,
        )
        current = parsed_query(
            "지금 영업 중인 식당",
            search_query="홍대 영업 중인 식당",
            is_active=True,
            start_date="2026-07-14",
        )
        self.assertFalse(build_restaurant_search_plan(future, future.tasks[0]).open_now)
        self.assertTrue(build_restaurant_search_plan(current, current.tasks[0]).open_now)

    def test_hallucinated_radius_and_time_window_are_ignored(self):
        parsed = StructuredTravelQuery.model_validate({
            "language": "ko",
            "intent": "single_place_recommendation",
            "source_mode": "rag_mcp",
            "original_question": "내일 갈 조용한 중식당 추천해줘",
            "normalized_question": "내일 조용한 중식당",
            "tasks": [{
                "task_id": "1",
                "domain": "restaurant",
                "search_query": "조용한 중식당",
                "themes": [],
                "desired_count": 1,
            }],
            "filters": {
                "location": "홍대",
                "radius_km": 5.0,
                "time_window": "lunch",
                "start_date": "2026-07-15",
                "party_size": 2,
                "budget_min_krw": 0,
                "budget_max_krw": 100000,
            },
        })
        plan = build_restaurant_search_plan(parsed, parsed.tasks[0])
        self.assertEqual(plan.radius_km, 2.0)
        self.assertIsNone(plan.target_time_window)
        self.assertIsNone(plan.target_visit_at)
        self.assertIsNone(plan.budget_min_krw)
        self.assertIsNone(plan.budget_max_krw)

    def test_explicit_visit_time_and_budget_are_applied(self):
        parsed = StructuredTravelQuery.model_validate({
            "language": "ko",
            "intent": "single_place_recommendation",
            "original_question": "2026-07-15 저녁 3만원 이하의 단체석 있는 식당 추천",
            "normalized_question": "2026-07-15 저녁 3만원 이하 단체 식당",
            "tasks": [{
                "task_id": "1", "domain": "restaurant",
                "search_query": "단체석 있는 식당", "desired_count": 1,
            }],
            "filters": {
                "location": "홍대",
                "start_date": "2026-07-15",
                "time_window": "evening",
                "budget_max_krw": 30000,
                "required_features": ["단체석"],
            },
        })
        with patch("services.rag.geocode_kakao", return_value=None):
            plan = build_restaurant_search_plan(parsed, parsed.tasks[0])
        self.assertEqual(plan.target_visit_at, __import__("datetime").datetime(2026, 7, 15, 19, 0))
        self.assertEqual(plan.budget_max_krw, 30000)
        self.assertIn("has_group_seating", plan.required_feature_fields)

    def test_explicit_radius_is_kept_even_if_model_value_differs(self):
        parsed = StructuredTravelQuery.model_validate({
            "language": "ko",
            "intent": "single_place_recommendation",
            "original_question": "반경 3km 안의 한식당 추천",
            "normalized_question": "3km 한식당",
            "tasks": [{
                "task_id": "1", "domain": "restaurant",
                "search_query": "홍대 한식당", "desired_count": 1,
            }],
            "filters": {"location": "홍대", "radius_km": 5.0},
        })
        plan = build_restaurant_search_plan(parsed, parsed.tasks[0])
        self.assertEqual(plan.radius_km, 3.0)

    def test_rating_pet_and_english_cuisine_are_recovered(self):
        pet = parsed_query(
            "평점 4.5 이상이고 반려동물 동반 가능한 식당 추천해줘",
            search_query="평점 4.5 이상이고 반려동물 동반 가능한 식당",
        )
        pet.filters.required_features = ["반려동물 동반 가능"]
        pet_plan = build_restaurant_search_plan(pet, pet.tasks[0])
        self.assertEqual(pet_plan.min_rating, 4.5)
        self.assertIn("allows_pets", pet_plan.required_feature_fields)
        self.assertNotIn("4.5", pet_plan.retrieval_query)
        self.assertTrue(pet_plan.retrieval_query.startswith("반려동물"))

        english = parsed_query(
            "Find a quiet Chinese restaurant in Hongdae tomorrow evening",
            search_query="quiet Chinese restaurant",
            themes=["quiet"],
            start_date="2026-07-15",
            language="en",
            location="Hongdae",
        )
        en_plan = build_restaurant_search_plan(english, english.tasks[0])
        self.assertEqual(en_plan.requested_category, "중국 요리")

    def test_explicit_facilities_are_recovered_when_parser_puts_them_in_text(self):
        pet = parsed_query(
            "성수에서 반려동물과 함께 갈 수 있는 식당",
            search_query="조용한 식당",
            themes=["반려동물 허용"],
            location="성수",
        )
        group = parsed_query(
            "을지로에서 단체석과 룸이 모두 있는 식당",
            search_query="단체석과 룸이 있는 식당",
            location="을지로",
        )
        optional = parsed_query(
            "주차는 없어도 괜찮아. 서울 태국 음식점 추천",
            search_query="태국 음식점",
            location="서울",
        )
        with patch("services.rag.geocode_kakao", return_value=None):
            pet_plan = build_restaurant_search_plan(pet, pet.tasks[0])
            group_plan = build_restaurant_search_plan(group, group.tasks[0])
            optional_plan = build_restaurant_search_plan(optional, optional.tasks[0])
        self.assertIn("allows_pets", pet_plan.required_feature_fields)
        self.assertIn("has_group_seating", group_plan.required_feature_fields)
        self.assertIn("has_private_room", group_plan.required_feature_fields)
        self.assertNotIn("has_parking", optional_plan.required_feature_fields)

    def test_english_language_and_category_are_recovered_from_original_question(self):
        parsed = parsed_query(
            "Find a quiet Chinese restaurant in Hongdae",
            search_query="quiet Chinese restaurant",
            language="ko",
            location="Hongdae",
        )
        self.assertEqual(effective_query_language(parsed), "en")
        with patch("services.rag.geocode_kakao", return_value=None):
            plan = build_restaurant_search_plan(parsed, parsed.tasks[0])
        self.assertEqual(plan.requested_category, "중국 요리")

    def test_specific_chinese_dish_constrains_category_but_keeps_menu_query(self):
        parsed = parsed_query(
            "홍대에서 마라탕 먹고 싶어. 대화하기 편한 식당이면 좋겠어.",
            search_query="마라탕",
            themes=["대화하기 편한"],
        )
        with patch("services.rag.geocode_kakao", return_value=None):
            plan = build_restaurant_search_plan(parsed, parsed.tasks[0])
        self.assertEqual(plan.requested_category, "중국 요리")
        self.assertEqual(plan.review_query, "대화하기 편한")
        self.assertEqual(plan.menu_query, "마라탕")

    def test_explicit_group_dinner_recovers_group_seating_filter(self):
        parsed = parsed_query(
            "강남에서 단체 회식 가능한 고깃집 추천해줘",
            search_query="고깃집",
            location="강남",
        )
        with patch("services.rag.geocode_kakao", return_value=None):
            plan = build_restaurant_search_plan(parsed, parsed.tasks[0])
        self.assertIn("has_group_seating", plan.required_feature_fields)

    def test_qualitative_high_rating_request_becomes_sort_preference_not_fake_threshold(self):
        parsed = parsed_query(
            "서울에서 평점 좋은 태국 음식점 추천",
            search_query="평점 좋은 태국 음식점",
            location="서울",
        )
        with patch("services.rag.geocode_kakao", return_value=None):
            plan = build_restaurant_search_plan(parsed, parsed.tasks[0])
        self.assertTrue(plan.prefer_high_rating)
        self.assertIsNone(plan.min_rating)

    def test_star_rating_and_accessibility_are_applied(self):
        korean = parsed_query(
            "별점 4.5 이상이고 휠체어 접근 가능한 식당",
            search_query="휠체어 접근 가능한 식당",
        )
        korean.filters.accessibility = ["휠체어 접근 가능"]
        plan = build_restaurant_search_plan(korean, korean.tasks[0])
        self.assertEqual(plan.min_rating, 4.5)
        self.assertIn("has_disabled_access", plan.required_feature_fields)

        english = parsed_query(
            "Find a restaurant rated 4.7 or higher",
            search_query="highly rated restaurant",
            language="en",
            location=None,
        )
        self.assertEqual(build_restaurant_search_plan(english, english.tasks[0]).min_rating, 4.7)

    def test_structured_entrypoint_passes_plan_to_existing_rrf(self):
        parsed = parsed_query(
            "조용한 중식당 추천",
            search_query="홍대 조용한 중식당",
            themes=["조용한"],
        )
        with patch("services.rag.search_restaurants", return_value={"candidates": []}) as search:
            result = search_restaurants_structured(
                parsed,
                parsed.tasks[0],
                current_lat=37.5563,
                current_lng=126.9236,
            )
        plan = search.call_args.kwargs["_structured_plan"]
        self.assertEqual(plan.task_id, "task_1")
        self.assertFalse(plan.include_weather_features)
        self.assertTrue(result["structured_input"])
        self.assertEqual(result["source_mode"], "rag_only")

    def test_different_target_location_never_uses_wrong_current_coordinates(self):
        parsed = parsed_query(
            "강남에서 조용한 중식당 추천",
            search_query="강남 조용한 중식당",
            location="강남",
        )
        with patch("services.rag.geocode_kakao", return_value=None):
            plan = build_restaurant_search_plan(
                parsed,
                parsed.tasks[0],
                current_lat=37.5563,
                current_lng=126.9236,
                current_location_name="홍대",
            )
        self.assertIsNone(plan.origin_lat)
        self.assertIsNone(plan.origin_lng)

    def test_target_location_is_geocoded_when_current_location_name_is_missing(self):
        parsed = parsed_query(
            "홍대에서 조용한 중식당 추천",
            search_query="홍대 조용한 중식당",
            location="홍대",
        )
        with patch(
            "services.rag.geocode_kakao",
            return_value=(37.5569, 126.9238, "홍대입구역"),
        ) as geocode:
            plan = build_restaurant_search_plan(
                parsed,
                parsed.tasks[0],
                current_lat=37.5665,
                current_lng=126.9780,
                current_location_name=None,
            )
        geocode.assert_called_once_with("홍대")
        self.assertAlmostEqual(plan.origin_lat, 37.5569)
        self.assertAlmostEqual(plan.origin_lng, 126.9238)

    def test_language_variant_uses_english_table(self):
        parsed = parsed_query(
            "Find a Chinese restaurant in Hongdae",
            search_query="Hongdae Chinese restaurant",
            language="en-US",
            location="Hongdae",
        )
        with patch("services.rag.geocode_kakao", return_value=None), patch(
            "services.rag._embedding", return_value=[0.0]
        ), patch("services.rag._connection") as connection:
            cursor = connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchall.return_value = []
            search_restaurants_structured(parsed, parsed.tasks[0], top_n=5)
        first_sql = cursor.execute.call_args_list[0].args[0]
        self.assertIn("restaurant_embedding_en", first_sql)

    def test_chat_request_accepts_fixed_json_without_source_mode(self):
        parsed = parsed_query(
            "내일 조용한 중식당 추천",
            search_query="홍대 조용한 중식당",
            start_date="2026-07-15",
        )
        body = ChatRequest(message=parsed.original_question, parsed_query=parsed)
        self.assertIsNone(body.source_mode)
        self.assertEqual(derive_source_mode(body.parsed_query), "rag_mcp")

    def test_structured_filter_ranges_are_validated(self):
        with self.assertRaises(ValueError):
            StructuredTravelQuery.model_validate({
                "intent": "single_place_recommendation",
                "original_question": "식당 추천",
                "normalized_question": "식당 추천",
                "tasks": [{
                    "task_id": "1", "domain": "restaurant",
                    "search_query": "식당", "desired_count": 1,
                }],
                "filters": {"budget_min_krw": 50000, "budget_max_krw": 10000},
            })

    def test_at_most_five_unique_tasks_are_accepted(self):
        base = {
            "intent": "single_place_recommendation",
            "original_question": "여러 장소 추천",
            "normalized_question": "여러 장소 추천",
            "filters": {},
        }
        five = [
            {"task_id": str(index), "domain": "restaurant", "search_query": "식당"}
            for index in range(5)
        ]
        self.assertEqual(
            len(StructuredTravelQuery.model_validate({**base, "tasks": five}).tasks), 5
        )
        with self.assertRaises(ValueError):
            StructuredTravelQuery.model_validate({
                **base,
                "tasks": [*five, {"task_id": "6", "domain": "cafe", "search_query": "카페"}],
            })
        with self.assertRaises(ValueError):
            StructuredTravelQuery.model_validate({**base, "tasks": [five[0], five[0]]})


if __name__ == "__main__":
    unittest.main()
