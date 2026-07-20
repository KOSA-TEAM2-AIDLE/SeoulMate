import unittest
from datetime import date

from domains.attraction.repository import (
    AttractionRecord,
    AttractionRetrievalResult,
    AttractionVectorHit,
)
from domains.attraction.reranker import AttractionReranker
from domains.attraction.search_plan import AttractionSearchPlan
from domains.attraction.search_service import should_geocode_location
from domains.common.models import DomainSearchRequest


def _record(
    attraction_id: str,
    *,
    address: str,
    latitude: float,
    longitude: float,
) -> AttractionRecord:
    return AttractionRecord(
        id=attraction_id,
        source_cid=attraction_id,
        language="ko",
        kind="attraction",
        name=attraction_id,
        category="관광지",
        category_primary="attraction",
        category_secondary="",
        summary="",
        description="",
        tags="",
        address=address,
        latitude=latitude,
        longitude=longitude,
        hours="",
        fee="",
        image=None,
        link=None,
        start_date=None,
        end_date=None,
        rating=None,
        review_count=0,
        english_review_count=0,
        foreign_review_count=0,
    )


class AttractionLocationPolicyTests(unittest.TestCase):
    def test_explicit_landmark_excludes_candidates_from_conflicting_district(self):
        palace = _record(
            "gyeongbokgung",
            address="서울 종로구 사직로 161",
            latitude=37.5796,
            longitude=126.9770,
        )
        lotte_world = _record(
            "lotte-world",
            address="서울 송파구 올림픽로 240",
            latitude=37.5110,
            longitude=127.0980,
        )
        retrieval = AttractionRetrievalResult(
            query="경복궁 근처 관광지",
            language="ko",
            profile_hits=(
                AttractionVectorHit("gyeongbokgung", 1, 0.9),
                AttractionVectorHit("lotte-world", 2, 0.8),
            ),
            review_hits_by_place={},
            attractions={palace.id: palace, lotte_world.id: lotte_world},
            query_vector=(),
        )
        plan = AttractionSearchPlan(
            query_text="경복궁 근처 관광지",
            language="ko",
            primary_categories=(),
            secondary_categories=(),
            event_only=False,
            latitude=37.5796,
            longitude=126.9770,
            radius_km=30,
        )

        results = AttractionReranker().rerank(
            retrieval,
            plan=plan,
            required_features=[],
            excluded_features=[],
            min_rating=None,
            as_of=date(2026, 7, 19),
            limit=10,
            search_location="경복궁",
        )

        self.assertEqual(["gyeongbokgung"], [item.attraction.id for item in results])

    def test_current_location_alias_keeps_frontend_coordinates(self):
        request = DomainSearchRequest(
            task_id="task_1",
            domain="attraction",
            search_query="현재 내 주변 산책 장소",
            location="현재 위치",
            latitude=37.5665,
            longitude=126.978,
        )

        self.assertFalse(should_geocode_location(request))

    def test_explicit_destination_is_geocoded_when_not_current_location(self):
        request = DomainSearchRequest(
            task_id="task_1",
            domain="attraction",
            search_query="경복궁 근처 관광지",
            location="경복궁",
            latitude=37.5665,
            longitude=126.978,
        )

        self.assertTrue(should_geocode_location(request))

    def test_named_current_location_without_coordinates_is_geocoded(self):
        request = DomainSearchRequest(
            task_id="task_1",
            domain="attraction",
            search_query="여의도 아이와 함께 가기 좋은 장소",
            location="여의도",
            current_location_name="여의도",
        )

        self.assertTrue(should_geocode_location(request))


if __name__ == "__main__":
    unittest.main()
