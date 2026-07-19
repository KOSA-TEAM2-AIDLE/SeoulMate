import unittest

from domains.attraction.answer_models import (
    AttractionAnswerInput,
    AttractionEvidenceCandidate,
)
from domains.attraction.dspy.validator import (
    AttractionDspyValidationError,
    validate_selection_prediction,
    validate_structured_answer,
)


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
            )
        ],
    )


class AttractionDspyValidatorTests(unittest.TestCase):
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
                {
                    "language": "ko",
                    "recommendations": [
                        {
                            "place_id": "p1",
                            "name": "전시관",
                            "recommendation_reason": "전시를 관람하기 좋습니다.",
                            "congestion": {"status": "unavailable"},
                            "weather": {
                                "status": "unavailable",
                                "value": "맑음",
                            },
                        }
                    ],
                    "no_result_reason": None,
                },
            )


if __name__ == "__main__":
    unittest.main()

