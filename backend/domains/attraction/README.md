# Attraction DSPy 선택·답변 경계

## 운영 흐름

```text
DomainSearchRequest
  → AttractionSearchService (Vector DB, 최대 10개)
  → final_score 정적 재랭킹
  → AttractionCongestionReranker (선택)
  → AttractionAnswerGenerator
  → AttractionAnswerResult
```

`AttractionRecommendationPipeline.recommend(request)`가 관광 도메인의 완성된 진입점이다. `/chat`과 공통 schema는 수정하지 않는다.

```python
from domains.attraction import AttractionRecommendationPipeline

result = await AttractionRecommendationPipeline(
    congestion_reranker=congestion_reranker,
).recommend(domain_search_request)
```

## 채팅 담당자 핸드오프

- `result.answer`: SSE `token` 텍스트로 전달한다.
- `result.selections`: 선택 ID 순서대로 기존 `SearchCandidate`/프론트 `Place[]`와 결합한다.
- `selection_reason`: `Place.selectionReason`에 넣는다.
- `used_fallback`: 모델·artifact·timeout·검증 실패 여부이며, `True`여도 재랭킹 상위 결과는 유지된다.

## 오프라인 실험

```bash
cd backend

# 비용 없는 평가 계획 확인
uv run python -m experiments.attraction_dspy.evaluate \
  --methods manual,dspy_baseline --split test --dry-run

# 비용 없는 MIPROv2 계획 확인
uv run python -m experiments.attraction_dspy.optimize --dry-run
```

`--dry-run`을 제거하면 OpenAI API 비용이 발생한다. MIPROv2는 운영 요청 중 실행하지 않고 `optimized_program.json`을 사전 생성한다.

## 안전 정책

- 종료된 행사는 DSPy 입력에 넣지 않는다.
- 종료일이 없는 행사는 상설 행사일 수 있어 유지한다.
- Vector 내부 점수는 프롬프트에 노출하지 않는다.
- 혼잡도는 공식 기준 구역 값이며 시설 내부 인파로 단정하지 않는다.
- 잘못된 DSPy 출력은 부분 복구하지 않고 전체 fallback한다.
