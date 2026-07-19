import unittest

from pydantic import ValidationError

from domains.attraction.dspy.contracts import (
    AttractionSelectionPrediction,
    AttractionStructuredAnswer,
)
from domains.attraction.dspy.programs import (
    TourismAnswerProgram,
    TourismSelectionProgram,
)


class AttractionDspyContractTests(unittest.TestCase):
    def test_split_programs_expose_stable_contracts(self):
        selection = TourismSelectionProgram()
        answer = TourismAnswerProgram()

        self.assertEqual(
            set(selection.generate.signature.output_fields),
            {"selected_place_ids", "forbidden_place_ids", "selection_reasons_json"},
        )
        self.assertEqual(
            set(answer.generate.signature.output_fields),
            {"structured_answer_json"},
        )

    def test_selection_prediction_rejects_duplicate_ids_and_reason_mismatch(self):
        with self.assertRaises(ValidationError):
            AttractionSelectionPrediction(
                selected_place_ids=["p1", "p1"],
                forbidden_place_ids=[],
                selection_reasons={"p1": "근거"},
            )

        with self.assertRaises(ValidationError):
            AttractionSelectionPrediction(
                selected_place_ids=["p1"],
                forbidden_place_ids=[],
                selection_reasons={"p2": "다른 후보 근거"},
            )

    def test_structured_answer_requires_available_context_values(self):
        with self.assertRaises(ValidationError):
            AttractionStructuredAnswer.model_validate(
                {
                    "language": "ko",
                    "recommendations": [
                        {
                            "place_id": "p1",
                            "name": "테스트 장소",
                            "recommendation_reason": "검증된 설명",
                            "congestion": {"status": "available"},
                            "weather": {"status": "unavailable"},
                        }
                    ],
                    "no_result_reason": None,
                }
            )


if __name__ == "__main__":
    unittest.main()
