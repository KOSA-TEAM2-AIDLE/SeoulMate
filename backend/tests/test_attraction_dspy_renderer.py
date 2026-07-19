import unittest

from domains.attraction.dspy.contracts import (
    AttractionAnswerContext,
    AttractionSelectionPrediction,
    AttractionStructuredAnswer,
    AttractionStructuredRecommendation,
)
from domains.attraction.dspy.renderer import render_selection_result


class AttractionDspyRendererTests(unittest.TestCase):
    def test_renderer_reuses_natural_place_reason_for_sidebar_and_chat(self):
        selection = AttractionSelectionPrediction(
            selected_place_ids=["p1"],
            forbidden_place_ids=[],
            selection_reasons={"p1": "아이와 함께 즐길 수 있는 체험 조건에 맞습니다."},
        )
        answer = AttractionStructuredAnswer(
            language="ko",
            recommendations=[
                AttractionStructuredRecommendation(
                    place_id="p1",
                    name="여의도 공원",
                    recommendation_reason="넓은 야외 공간과 프로그램이 있습니다.",
                    congestion=AttractionAnswerContext(
                        status="available", value="여유", basis="서울시 실시간 도시데이터 권역",
                        observed_at="2026-07-18T15:55:00+09:00",
                    ),
                    weather=AttractionAnswerContext(
                        status="available", value="condition=맑음; temperature_c=28",
                        basis="KMA-via-Weather-MCP",
                    ),
                )
            ],
        )

        result = render_selection_result(selection, answer, question="아이와 함께 갈 전시 추천")

        sidebar_reason = result.selections[0].selection_reason
        self.assertIn(sidebar_reason, result.answer)
        self.assertNotIn("질의 적합성:", sidebar_reason)
        self.assertNotIn("혼잡도:", sidebar_reason)
        self.assertNotIn("날씨:", sidebar_reason)
        self.assertIn("2026-07-18 15:55", sidebar_reason)
        self.assertNotIn("+09:00", sidebar_reason)

    def test_renderer_preserves_selection_reason_and_formats_answer(self):
        selection = AttractionSelectionPrediction(
            selected_place_ids=["p1"],
            forbidden_place_ids=[],
            selection_reasons={"p1": "전시 주제와 맞습니다."},
        )
        answer = AttractionStructuredAnswer(
            language="ko",
            recommendations=[
                AttractionStructuredRecommendation(
                    place_id="p1",
                    name="테스트 전시장",
                    recommendation_reason="전시 주제와 맞습니다.",
                    description_evidence=["현대미술 전시를 운영합니다."],
                    congestion=AttractionAnswerContext(status="unavailable"),
                    weather=AttractionAnswerContext(status="unavailable"),
                )
            ],
        )

        result = render_selection_result(selection, answer)

        self.assertEqual("p1", result.selections[0].place_id)
        self.assertIn("전시 주제와 맞습니다.", result.selections[0].selection_reason)
        self.assertIn("혼잡도 정보는 확인되지 않았습니다.", result.selections[0].selection_reason)
        self.assertIn("날씨 정보는 확인되지 않았습니다.", result.selections[0].selection_reason)
        self.assertIn("테스트 전시장", result.answer)
        self.assertIn("현대미술 전시", result.answer)
        self.assertIn("추천드릴게요", result.answer)
        self.assertIn("1. 테스트 전시장", result.answer)

    def test_renderer_writes_a_natural_congestion_grounded_recommendation(self):
        selection = AttractionSelectionPrediction(
            selected_place_ids=["p1"], forbidden_place_ids=[],
            selection_reasons={"p1": "아이와 함께 즐길 수 있는 체험 조건에 맞습니다."},
        )
        answer = AttractionStructuredAnswer(
            language="ko",
            recommendations=[AttractionStructuredRecommendation(
                place_id="p1", name="여의도 공원",
                recommendation_reason="넓은 공간과 프로그램이 있습니다.",
                description_evidence=["한국 전통의 숲과 잔디마당을 갖춘 시민공원입니다."],
                congestion=AttractionAnswerContext(
                    status="available", value="여유", basis="서울시 실시간 도시데이터 권역",
                    observed_at="2026-07-18T16:00:00+09:00",
                ),
                weather=AttractionAnswerContext(status="unavailable"),
            )],
        )

        result = render_selection_result(selection, answer, question="여의도에서 아이와 함께 갈 곳 추천해줘")

        self.assertIn("여의도에서 아이와 함께 갈 곳", result.answer)
        self.assertIn("현재 혼잡도는 여유 수준", result.answer)
        self.assertIn("날씨 정보는 확인되지 않았습니다.", result.answer)
        self.assertNotIn("은(는)", result.answer)
        self.assertIn("1. 여의도 공원\n", result.answer)
        self.assertNotIn("1. 여의도 공원 여의도 공원", result.answer)

    def test_renderer_keeps_a_reason_that_already_has_its_own_subject(self):
        selection = AttractionSelectionPrediction(
            selected_place_ids=["p1"], forbidden_place_ids=[], selection_reasons={"p1": "가족 방문에 적합합니다."},
        )
        answer = AttractionStructuredAnswer(
            language="ko",
            recommendations=[AttractionStructuredRecommendation(
                place_id="p1", name="더현대 서울 크리스마스 빌리지 'H-Village'",
                recommendation_reason="더현대 서울의 크리스마스 빌리지는 아이들이 즐길 수 있는 체험 전시를 제공합니다.",
                congestion=AttractionAnswerContext(status="unavailable"),
                weather=AttractionAnswerContext(status="unavailable"),
            )],
        )

        result = render_selection_result(selection, answer)

        self.assertIn("\n   가족 방문에 적합합니다.", result.answer)
        self.assertNotIn("H-Village'은 더현대 서울의", result.answer)

    def test_renderer_uses_english_place_reason_for_english_answer(self):
        selection = AttractionSelectionPrediction(
            selected_place_ids=["p1"],
            forbidden_place_ids=[],
            selection_reasons={"p1": "It fits an art-focused visit."},
        )
        answer = AttractionStructuredAnswer(
            language="en",
            recommendations=[
                AttractionStructuredRecommendation(
                    place_id="p1",
                    name="Gyeongbokgung Palace",
                    recommendation_reason="It fits an art-focused visit.",
                    congestion=AttractionAnswerContext(status="unavailable"),
                    weather=AttractionAnswerContext(status="unavailable"),
                )
            ],
        )

        result = render_selection_result(selection, answer)

        self.assertIn("It fits an art-focused visit.", result.selections[0].selection_reason)
        self.assertIn("Congestion information is unavailable.", result.selections[0].selection_reason)
        self.assertNotIn("질의 적합성", result.selections[0].selection_reason)


if __name__ == "__main__":
    unittest.main()
