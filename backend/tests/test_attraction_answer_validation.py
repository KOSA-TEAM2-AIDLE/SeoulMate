import unittest
from types import SimpleNamespace
from unittest.mock import patch

from domains.attraction.answer_models import (
    AttractionAnswerInput,
    AttractionEvidenceCandidate,
)
from domains.attraction.answer_validation import (
    fallback_attraction_answer,
    validate_attraction_prediction,
)


def answer_input(*, language: str = "ko", congestion: str | None = None):
    return AttractionAnswerInput(
        question="경복궁 근처 추천해줘",
        language=language,
        candidates=[
            AttractionEvidenceCandidate(
                place_id=str(index),
                rank=index,
                name=f"후보 {index}",
                category="관광지",
                description=f"검증된 설명 {index}",
                congestion=congestion,
            )
            for index in range(1, 5)
        ],
    )


def prediction(
    ids=None,
    *,
    reasons=None,
    answer="질문에 맞는 세 곳을 추천합니다.",
):
    ids = ids or ["1", "2", "3"]
    reasons = reasons or {place_id: f"검증된 근거 {place_id}" for place_id in ids}
    import json

    return SimpleNamespace(
        selected_place_ids=ids,
        selection_reasons_json=json.dumps(reasons, ensure_ascii=False),
        answer=answer,
    )


class AttractionAnswerValidationTests(unittest.TestCase):
    def test_valid_prediction_is_returned_without_fallback(self):
        result = validate_attraction_prediction(answer_input(), prediction())

        self.assertFalse(result.used_fallback)
        self.assertEqual([item.place_id for item in result.selections], ["1", "2", "3"])

    def test_unknown_duplicate_or_too_few_ids_use_complete_ranked_fallback(self):
        invalid_predictions = [
            prediction(["unknown", "2", "3"]),
            prediction(["1", "1", "2"]),
            prediction(["1", "2"]),
        ]

        for invalid in invalid_predictions:
            with self.subTest(ids=invalid.selected_place_ids):
                result = validate_attraction_prediction(answer_input(), invalid)
                self.assertTrue(result.used_fallback)
                self.assertEqual(
                    [item.place_id for item in result.selections],
                    ["1", "2", "3"],
                )

    def test_invalid_or_empty_reasons_use_fallback(self):
        invalid_predictions = [
            SimpleNamespace(
                selected_place_ids=["1", "2", "3"],
                selection_reasons_json="{broken",
                answer="추천합니다.",
            ),
            prediction(reasons={"1": "", "2": "근거", "3": "근거"}),
            prediction(reasons={"1": " null ", "2": "근거", "3": "근거"}),
        ]

        for invalid in invalid_predictions:
            with self.subTest(prediction=invalid):
                self.assertTrue(
                    validate_attraction_prediction(
                        answer_input(), invalid
                    ).used_fallback
                )

    def test_string_null_answer_uses_ranked_fallback(self):
        result = validate_attraction_prediction(
            answer_input(),
            prediction(answer=" NULL "),
        )

        self.assertTrue(result.used_fallback)
        self.assertEqual(
            ["1", "2", "3"],
            [item.place_id for item in result.selections],
        )

    def test_absent_congestion_cannot_be_used_as_quietness_evidence(self):
        invalid = prediction(
            reasons={"1": "한적해서 추천", "2": "근거", "3": "근거"},
            answer="한적한 장소를 추천합니다.",
        )

        self.assertTrue(
            validate_attraction_prediction(answer_input(), invalid).used_fallback
        )

    def test_answer_cannot_replace_selected_candidate_with_another_name(self):
        invalid = prediction(
            ["1", "2", "3"],
            answer="후보 1, 후보 2, 후보 4를 추천합니다.",
        )

        result = validate_attraction_prediction(answer_input(), invalid)

        self.assertTrue(result.used_fallback)
        self.assertEqual(
            ["1", "2", "3"],
            [item.place_id for item in result.selections],
        )

    def test_fallback_uses_available_count_and_requested_language(self):
        korean = fallback_attraction_answer(answer_input())
        english_input = answer_input(language="en").model_copy(
            update={"candidates": answer_input(language="en").candidates[:2]}
        )
        english = fallback_attraction_answer(english_input)

        self.assertIn("재랭킹", korean.selections[0].selection_reason)
        self.assertEqual(len(english.selections), 2)
        self.assertIn("reranking", english.selections[0].selection_reason)

    def test_recommendation_limit_is_controlled_by_one_setting(self):
        with patch(
            "domains.attraction.answer_validation.settings."
            "attraction_recommendation_limit",
            2,
        ):
            result = fallback_attraction_answer(answer_input())

        self.assertEqual(["1", "2"], [item.place_id for item in result.selections])


if __name__ == "__main__":
    unittest.main()
