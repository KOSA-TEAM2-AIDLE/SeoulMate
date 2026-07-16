import unittest
from datetime import date

from pydantic import ValidationError

from core.config import settings
from domains.attraction.answer_evidence import build_attraction_answer_input
from domains.attraction.answer_models import (
    AttractionAnswerInput,
    AttractionAnswerResult,
    AttractionEvidenceCandidate,
    AttractionSelection,
)
from domains.common.models import DomainSearchRequest, SearchCandidate
from vector_db.attraction.search import AttractionVectorSearch


class AttractionDspySettingsTests(unittest.TestCase):
    def test_defaults_match_validated_notebook_environment(self):
        self.assertEqual(
            settings.attraction_dspy_model,
            "openai/gpt-4o-mini",
        )
        self.assertEqual(settings.attraction_dspy_temperature, 0.0)
        self.assertEqual(settings.attraction_dspy_max_tokens, 900)
        self.assertTrue(
            str(settings.attraction_dspy_artifact_path).endswith(
                "domains/attraction/artifacts/optimized_program.json"
            )
        )


class AttractionAnswerModelTests(unittest.TestCase):
    def _candidate(self, place_id: str) -> AttractionEvidenceCandidate:
        return AttractionEvidenceCandidate(
            place_id=place_id,
            rank=int(place_id),
            name=f"후보 {place_id}",
            category="관광지",
        )

    def test_input_accepts_at_most_ten_unique_candidates(self):
        answer_input = AttractionAnswerInput(
            question="경복궁 근처 관광지 추천해줘",
            language="ko",
            candidates=[self._candidate(str(index)) for index in range(1, 11)],
        )

        self.assertEqual(len(answer_input.candidates), 10)

        with self.assertRaises(ValidationError):
            AttractionAnswerInput(
                question="관광지 추천",
                language="ko",
                candidates=[self._candidate(str(index)) for index in range(1, 12)],
            )

        with self.assertRaises(ValidationError):
            AttractionAnswerInput(
                question="관광지 추천",
                language="ko",
                candidates=[self._candidate("1"), self._candidate("1")],
            )

    def test_result_rejects_more_than_three_or_duplicate_selections(self):
        with self.assertRaises(ValidationError):
            AttractionAnswerResult(
                answer="추천 결과입니다.",
                selections=[
                    AttractionSelection(
                        place_id=str(index), selection_reason="질문에 잘 맞습니다."
                    )
                    for index in range(1, 5)
                ],
            )

        with self.assertRaises(ValidationError):
            AttractionAnswerResult(
                answer="추천 결과입니다.",
                selections=[
                    AttractionSelection(place_id="1", selection_reason="근거 1"),
                    AttractionSelection(place_id="1", selection_reason="근거 2"),
                ],
            )

    def test_candidate_forbids_fields_outside_the_evidence_contract(self):
        with self.assertRaises(ValidationError):
            AttractionEvidenceCandidate(
                place_id="1",
                rank=1,
                name="경복궁",
                category="고궁",
                vector_similarity=0.99,
            )


class AttractionAnswerEvidenceTests(unittest.TestCase):
    def _candidate(
        self,
        place_id: str,
        *,
        kind: str = "attraction",
        end_date: str | None = None,
    ) -> SearchCandidate:
        return SearchCandidate(
            domain="attraction",
            place_id=place_id,
            task_id="task_1",
            name=f"후보 {place_id}",
            category="축제/공연/행사" if kind == "event" else "역사관광",
            base_score=0.9,
            final_score=0.8,
            evidence=[f"리뷰 {index}" for index in range(1, 7)],
            attributes={
                "kind": kind,
                "description": "검증된 장소 설명",
                "start_date": "2026-07-01" if kind == "event" else None,
                "end_date": end_date,
                "distance_km": 1.25,
            },
            signals={
                "vector_similarity": 0.99,
                "congestion_available": True,
                "congestion_level": "보통",
                "congestion_observed_at": "2026-07-16T10:00:00+09:00",
            },
        )

    def test_builds_only_allowed_evidence_and_up_to_five_reviews(self):
        result = build_attraction_answer_input(
            question="경복궁 근처 갈만한 곳 추천해줘",
            language="ko",
            location="경복궁",
            themes=["역사"],
            candidates=[self._candidate("p1")],
            today=date(2026, 7, 16),
        )

        evidence = result.candidates[0]
        self.assertEqual(evidence.rank, 1)
        self.assertEqual(evidence.distance_m, 1250.0)
        self.assertEqual(evidence.description, "검증된 장소 설명")
        self.assertEqual(evidence.reviews, [f"리뷰 {index}" for index in range(1, 6)])
        self.assertIn("보통", evidence.congestion or "")
        self.assertNotIn("vector_similarity", evidence.model_dump())

    def test_rejects_ended_event_but_keeps_event_without_end_date(self):
        with self.assertRaisesRegex(ValueError, "종료된 행사"):
            build_attraction_answer_input(
                question="축제 추천",
                language="ko",
                location=None,
                themes=[],
                candidates=[
                    self._candidate("ended", kind="event", end_date="2026-07-15")
                ],
                today=date(2026, 7, 16),
            )

        result = build_attraction_answer_input(
            question="상설 행사 추천",
            language="ko",
            location=None,
            themes=[],
            candidates=[self._candidate("ongoing", kind="event", end_date=None)],
            today=date(2026, 7, 16),
        )

        self.assertIsNone(result.candidates[0].event_end_date)


class AttractionReviewRetrievalLimitTests(unittest.TestCase):
    def test_vector_search_requests_five_reviews_per_place(self):
        class RepositoryStub:
            requested_limit: int | None = None

            def search_profiles(self, vector, *, language, as_of, limit):
                return [
                    {
                        "document_id": "profile:p1:ko",
                        "content": "Name: 경복궁\nCategory: 고궁",
                        "metadata": {
                            "place_key": "p1",
                            "kind": "attraction",
                            "lang": "ko",
                        },
                        "distance": 0.1,
                    }
                ]

            def search_reviews(
                self, vector, *, language, place_keys, limit_per_place
            ):
                self.requested_limit = limit_per_place
                return []

        repository = RepositoryStub()
        search = AttractionVectorSearch(
            repository=repository,
            embedder=lambda texts: [[0.1, 0.2]],
        )
        search.search(
            DomainSearchRequest(
                task_id="task_1",
                domain="attraction",
                search_query="경복궁",
                candidate_count=1,
            )
        )

        self.assertEqual(repository.requested_limit, 5)


if __name__ == "__main__":
    unittest.main()
