import unittest

from domains.attraction.answer_models import (
    AttractionAnswerInput,
    AttractionEvidenceCandidate,
)
from domains.attraction.dspy.validator import (
    AttractionDspyValidationError,
    validate_reason_prediction,
    validate_selection_prediction,
    validate_structured_answer,
)
from domains.attraction.dspy.hydrator import hydrate_structured_answer


def _input() -> AttractionAnswerInput:
    return AttractionAnswerInput(
        question="한적한 전시 추천",
        language="ko",
        candidates=[
            AttractionEvidenceCandidate(
                place_id="p1",
                rank=1,
                name="전시관",
                category="전시",
                description="현대 미술 전시와 교육 프로그램을 운영합니다.",
                reviews=["전시 구성이 알차고 안내가 친절합니다."],
                congestion={
                    "status": "available",
                    "value": "보통",
                    "basis": "인근 권역",
                    "observed_at": "2026-07-20T12:00:00+09:00",
                },
                weather={"status": "available", "value": "condition=clear"},
            )
        ],
    )


def _answer(**overrides):
    recommendation = {
        "place_id": "p1",
        "name": "전시관",
        "recommendation_reason": "전시를 관람하기 좋습니다.",
        "description_evidence": ["현대 미술 전시와 교육 프로그램"],
        "review_evidence": ["전시 구성이 알차고 안내가 친절합니다."],
        "congestion": {
            "status": "available",
            "value": "보통",
            "basis": "인근 권역",
            "observed_at": "2026-07-20T12:00:00+09:00",
        },
        "weather": {"status": "available", "value": "condition=clear"},
    }
    recommendation.update(overrides)
    return {
        "language": "ko",
        "recommendations": [recommendation],
        "no_result_reason": None,
    }


class AttractionDspyValidatorTests(unittest.TestCase):
    def test_reason_prediction_requires_selected_ids_in_order(self):
        with self.assertRaisesRegex(AttractionDspyValidationError, "Reason ID"):
            validate_reason_prediction(
                ["p1", "p2"],
                {"recommendation_reasons": {"p2": "사유", "p1": "사유"}},
            )

    def test_hydrator_copies_candidate_evidence_and_context(self):
        reason = validate_reason_prediction(
            ["p1"], {"recommendation_reasons": {"p1": "전시 관람에 적합합니다."}},
        )

        answer = hydrate_structured_answer(_input(), ["p1"], reason)
        item = answer["recommendations"][0]

        self.assertEqual(["현대 미술 전시와 교육 프로그램을 운영합니다."], item["description_evidence"])
        self.assertEqual(["전시 구성이 알차고 안내가 친절합니다."], item["review_evidence"])
        self.assertEqual(_input().candidates[0].congestion.model_dump(), item["congestion"])
        validate_structured_answer(_input(), ["p1"], answer)

    def test_selection_rejects_unknown_and_conflicting_ids(self):
        with self.assertRaises(AttractionDspyValidationError):
            validate_selection_prediction(
                _input(),
                {
                    "selected_place_ids": ["unknown"],
                    "forbidden_place_ids": [],
                    "selection_reasons": {"unknown": "근거"},
                },
            )

    def test_answer_rejects_unavailable_weather_claim(self):
        with self.assertRaises(AttractionDspyValidationError):
            validate_structured_answer(
                _input(),
                ["p1"],
                _answer(weather={"status": "unavailable", "value": "맑음"}),
            )

    def test_answer_rejects_evidence_not_present_in_candidate(self):
        with self.assertRaisesRegex(AttractionDspyValidationError, "시설 근거"):
            validate_structured_answer(
                _input(),
                ["p1"],
                _answer(description_evidence=["입력에 없는 야간 개장 정보"]),
            )

    def test_answer_rejects_review_not_present_in_candidate(self):
        with self.assertRaisesRegex(AttractionDspyValidationError, "리뷰 근거"):
            validate_structured_answer(
                _input(),
                ["p1"],
                _answer(review_evidence=["입력에 없는 리뷰"]),
            )

    def test_answer_rejects_context_that_differs_from_candidate(self):
        with self.assertRaisesRegex(AttractionDspyValidationError, "날씨 Context"):
            validate_structured_answer(
                _input(),
                ["p1"],
                _answer(weather={"status": "available", "value": "condition=rain"}),
            )

    def test_answer_rejects_selection_answer_id_mismatch(self):
        with self.assertRaisesRegex(AttractionDspyValidationError, "선택 결과와 일치"):
            validate_structured_answer(
                _input(),
                ["p1"],
                {
                    "language": "ko",
                    "recommendations": [],
                    "no_result_reason": "조건에 맞는 관광지가 없습니다.",
                },
            )


if __name__ == "__main__":
    unittest.main()
