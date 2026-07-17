import unittest

from application.recommendation.selection_models import (
    CandidateSelectionResult,
)
from domains.attraction.answer_models import (
    AttractionAnswerResult,
    AttractionSelection,
)
from domains.attraction.selection_service import AttractionSelectionService
from domains.common.models import DomainSearchRequest, SearchCandidate


def _request() -> DomainSearchRequest:
    return DomainSearchRequest(
        task_id="task_1",
        domain="attraction",
        language="ko",
        search_query="경복궁 근처 고즈넉한 관광지 추천",
        themes=["역사", "고즈넉한"],
        location="경복궁",
    )


def _candidates() -> list[SearchCandidate]:
    return [
        SearchCandidate(
            domain="attraction",
            place_id=place_id,
            task_id="task_1",
            name=name,
            category="역사관광",
            base_score=score,
            final_score=score,
            evidence=[f"{name} 검증 근거"],
        )
        for place_id, name, score in (
            ("palace-1", "경복궁", 0.91),
            ("palace-2", "창덕궁", 0.87),
            ("palace-3", "덕수궁", 0.82),
            ("palace-4", "창경궁", 0.78),
        )
    ]


class AttractionSelectionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_and_ranked_candidates_are_forwarded_to_generator(self):
        class Generator:
            async def generate(self, **values):
                self.values = values
                return AttractionAnswerResult(
                    answer="고즈넉한 궁궐 세 곳을 추천합니다.",
                    selections=[
                        AttractionSelection(
                            place_id="palace-2",
                            selection_reason="역사적인 분위기가 잘 맞습니다.",
                        ),
                        AttractionSelection(
                            place_id="palace-1",
                            selection_reason="검증된 관광 근거가 충분합니다.",
                        ),
                        AttractionSelection(
                            place_id="palace-3",
                            selection_reason="접근성과 역사성이 좋습니다.",
                        ),
                    ],
                )

        generator = Generator()
        result = await AttractionSelectionService(
            answer_generator=generator,
        ).select(_request(), list(reversed(_candidates())))

        self.assertIsInstance(result, CandidateSelectionResult)
        self.assertEqual(generator.values["question"], _request().search_query)
        self.assertEqual(generator.values["language"], "ko")
        self.assertEqual(generator.values["location"], "경복궁")
        self.assertEqual(generator.values["themes"], ["역사", "고즈넉한"])
        self.assertEqual(
            [item.place_id for item in generator.values["candidates"]],
            ["palace-1", "palace-2", "palace-3", "palace-4"],
        )
        self.assertEqual(
            [item.place_id for item in result.selections],
            ["palace-2", "palace-1", "palace-3"],
        )
        self.assertFalse(result.used_fallback)

    async def test_unknown_id_falls_back_to_verified_ranked_candidates(self):
        class InvalidGenerator:
            async def generate(self, **values):
                return AttractionAnswerResult(
                    answer="존재하지 않는 장소를 추천합니다.",
                    selections=[
                        AttractionSelection(
                            place_id="invented-id",
                            selection_reason="모델이 만든 근거",
                        )
                    ],
                )

        result = await AttractionSelectionService(
            answer_generator=InvalidGenerator(),
        ).select(_request(), _candidates())

        self.assertTrue(result.used_fallback)
        self.assertEqual(
            [item.place_id for item in result.selections],
            ["palace-1", "palace-2", "palace-3"],
        )
        self.assertNotIn("invented-id", result.answer)

    async def test_rejects_non_attraction_request(self):
        request = _request().model_copy(update={"domain": "cafe"})

        with self.assertRaisesRegex(ValueError, "관광 도메인"):
            await AttractionSelectionService().select(request, _candidates())

    async def test_input_conversion_error_uses_raw_ranked_fallback(self):
        class ConversionFailureGenerator:
            async def generate(self, **values):
                raise ValueError("올바르지 않은 start_date 형식")

        result = await AttractionSelectionService(
            answer_generator=ConversionFailureGenerator(),
        ).select(_request(), _candidates())

        self.assertTrue(result.used_fallback)
        self.assertEqual(
            [item.place_id for item in result.selections],
            ["palace-1", "palace-2", "palace-3"],
        )
        self.assertIn("경복궁", result.answer)


if __name__ == "__main__":
    unittest.main()
