import unittest
from datetime import date

from domains.common.models import DomainSearchRequest
from vector_db.attraction.search import AttractionVectorSearch


class AttractionVectorSearchQueryTextTests(unittest.TestCase):
    def test_build_query_text_preserves_question_and_adds_explicit_conditions(self):
        request = DomainSearchRequest(
            task_id="task-1",
            domain="attraction",
            language="ko",
            search_query="조용한 전시 추천해줘",
            themes=["전시", "실내"],
            location="강남구",
            visit_date=date(2026, 7, 18),
            required_features=["휠체어 접근 가능"],
            excluded_features=["야외"],
        )

        query = AttractionVectorSearch.build_query_text(request)

        self.assertEqual(
            "조용한 전시 추천해줘 | 테마: 전시, 실내 | 위치: 강남구 | 방문일: 2026-07-18 "
            "| 필수 조건: 휠체어 접근 가능 | 제외 조건: 야외",
            query,
        )

    def test_build_query_text_omits_missing_optional_conditions(self):
        request = DomainSearchRequest(
            task_id="task-2",
            domain="attraction",
            search_query="아이와 갈 곳",
        )

        query = AttractionVectorSearch.build_query_text(request)

        self.assertEqual("아이와 갈 곳", query)


class _FakeRepository:
    def __init__(self):
        self.profile_call = None
        self.review_call = None

    def search_profiles(self, vector, *, language, as_of, limit):
        self.profile_call = (vector, language, as_of, limit)
        return [
            {
                "document_id": "event:expired:ko",
                "content": "Name: 종료 행사",
                "metadata": {"place_key": "expired", "kind": "event", "end_date": "2026-07-15"},
                "distance": 0.01,
            },
            {
                "document_id": "attraction:100:ko",
                "content": "Name: 국립미술관",
                "metadata": {"place_key": "100", "kind": "attraction", "end_date": ""},
                "distance": 0.10,
            },
            {
                "document_id": "event:200:ko",
                "content": "Name: 상시 행사",
                "metadata": {"place_key": "200", "kind": "event", "end_date": ""},
                "distance": 0.20,
            },
        ]

    def search_reviews(self, vector, *, language, place_keys, limit_per_place):
        self.review_call = (vector, language, place_keys, limit_per_place)
        return [
            {
                "document_id": "review:100:r1:ko",
                "content": "조용하고 좋았습니다.",
                "metadata": {"place_key": "100", "kind": "review"},
                "distance": 0.05,
            },
            {
                "document_id": "review:other:r2:ko",
                "content": "다른 장소 리뷰",
                "metadata": {"place_key": "other", "kind": "review"},
                "distance": 0.02,
            },
        ]


class AttractionVectorSearchTests(unittest.TestCase):
    def test_search_merges_matching_reviews_and_keeps_only_active_requested_hits(self):
        repository = _FakeRepository()
        embedded_inputs = []

        def embedder(texts):
            embedded_inputs.append(texts)
            return [[0.1, 0.2]]

        request = DomainSearchRequest(
            task_id="task-3",
            domain="attraction",
            language="ko",
            search_query="미술관 추천",
            visit_date=date(2026, 7, 16),
            candidate_count=1,
        )

        hits = AttractionVectorSearch(repository=repository, embedder=embedder).search(request)

        self.assertEqual([["미술관 추천 | 방문일: 2026-07-16"]], embedded_inputs)
        self.assertEqual(["100"], [hit.place_key for hit in hits])
        self.assertEqual(["조용하고 좋았습니다."], [review.content for review in hits[0].reviews])
        self.assertEqual(["100"], repository.review_call[2])
        self.assertEqual(3, repository.review_call[3])
