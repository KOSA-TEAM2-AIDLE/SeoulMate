# 관광·행사 DSPy 후보 선택·답변 생성 설계

## 목표

`attraction` 도메인에서만 DSPy를 사용해, 검색·재랭킹이 완료된 최대 10개 후보 중 최종 3개를 선택하고 후보별 선정 이유와 사용자 언어의 답변을 생성한다.

`/chat` SSE 계약, `StructuredTravelQuery`, `DomainSearchRequest`, `SearchCandidate`, 식당·카페·숙소 프롬프트는 변경하지 않는다.

## 기준선과 변경 범위

```text
질문 → TravelQuery 구조화 → 위치 해석
→ Attraction Vector DB 검색
→ 카테고리·거리·리뷰·행사 기간 정적 재랭킹
→ 필요 시 후보별 혼잡도 MCP 재랭킹
→ [변경] attraction 전용 DSPy가 10개 중 3개·이유·답변 생성
```

기존 `Tourism_Agent_DSPy_Prompt_Optimization.ipynb`은 이미 선택된 3개 후보의 답변 생성 실험이다. 이를 5~10개 후보의 `place_id` 선택까지 평가하도록 확장한다.

## 운영 아키텍처

```text
SearchCandidate[<=10]
→ build_attraction_answer_input()
→ OptimizedAttractionProgram
→ validate_attraction_prediction()
→ AttractionAnswerResult
```

운영에서는 미리 최적화한 program artifact만 로드한다. artifact 로드, 모델 호출, timeout, 출력 검증이 실패하면 현재 `final_score` 순서의 상위 3개를 fallback으로 반환한다. MIPROv2는 오프라인 실험에서만 수행한다.

## 입력·출력 계약

DSPy 입력은 질문, 언어, 위치, 테마와 후보별 ID·이름·카테고리·거리·설명·리뷰 5건·행사 기간·혼잡도 관측값으로 제한한다. Vector 내부 점수는 노출하지 않는다.

```python
class AttractionSelection(BaseModel):
    place_id: str
    selection_reason: str

class AttractionAnswerResult(BaseModel):
    answer: str
    selections: list[AttractionSelection]
    used_fallback: bool = False
```

후보가 3개 이상이면 정확히 3개, 3개 미만이면 존재하는 후보만 반환한다. 미등록·중복 ID는 금지한다.

## 안전 규칙

- 질문 언어와 답변 언어를 일치시킨다.
- 후보에 없는 요금·운영시간·행사·거리·리뷰·혼잡도를 만들지 않는다.
- 혼잡도는 공식 기준 POI 구역 값이며 시설 내부 인파로 확정하지 않는다.
- 혼잡도가 없으면 한적함을 추론하거나 혼잡도로 순위를 정하지 않는다.
- 종료일이 현재 날짜보다 이전인 행사는 선택하지 않는다.
- 종료일이 없는 행사는 상시 행사일 수 있으므로 유지한다.

## 오프라인 최적화·평가

초기 데이터셋은 Train 30, Dev 10, Test 10, Blind 20건으로 구성한다. 기존 40건에 5~10개 후보와 사람이 검토한 선택 허용 ID·필수 조건·금지 주장을 추가한다.

평가는 후보 선택 40%, 근거 충실도 25%, 조건 부합 15%, 언어·구조 10%, 명료성 10%로 시작한다. 미등록·중복 ID, 근거 없는 사실, 언어 불일치, 혼잡도 부재 추론, 종료 행사 선택은 hard fail이다.

## 운영 연결과 완료 기준

`dspy>=3.2.1,<3.3`, `openai/gpt-4o-mini`, temperature 0, 최대 900 token을 기본으로 한다.

```python
result = await attraction_answer_generator.generate(
    question=parsed.original_question,
    language=parsed.language,
    location=parsed.filters.location,
    themes=task.themes,
    candidates=reranked_candidates,
)
```

`result.answer`는 SSE token, `result.selections`는 최종 `Place` 및 `selection_reason`으로 연결할 수 있다. Test·Blind hard fail 0건, 언어 일치 100%, Blind 점수가 Manual보다 낮지 않은 경우에만 artifact를 채택한다.
