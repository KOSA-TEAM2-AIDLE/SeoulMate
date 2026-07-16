# 관광·행사 DSPy 후보 선택·답변 생성 구현 계획

> **Agent 작업자 안내:** `superpowers:subagent-driven-development`(권장) 또는 `superpowers:executing-plans`를 사용해 Task별로 실행한다. 단계는 체크박스(`- [ ]`)로 관리한다.

**목표:** attraction 재랭킹 후보 최대 10개에서 DSPy가 최종 3개, 선정 이유, 사용자 언어의 답변을 생성하는 attraction 전용 모듈을 구현한다.

**아키텍처:** 운영은 미리 최적화한 DSPy artifact를 로드하고 `SearchCandidate` 중 검증 근거만 전달한다. 출력은 Pydantic으로 검증하고 실패 시 재랭킹 순서로 fallback한다. 최적화은 오프라인에서만 실행한다.

**기술 스택:** Python 3.12, DSPy 3.2.1 호환 범위, Pydantic 2, OpenAI `gpt-4o-mini`, MIPROv2, unittest, JSONL.

## 전역 제약

- DSPy는 attraction에만 적용한다.
- `/chat`, SSE, 공통 schema와 다른 도메인 프롬프트를 변경하지 않는다.
- MIPROv2는 운영 요청 중 실행하지 않는다.
- 종료된 행사는 선택하지 않고 종료일이 없는 행사는 유지한다.
- DSPy 실패가 정적 검색·재랭킹 결과를 없애지 못하게 한다.

## 예정 파일

```text
backend/domains/attraction/
├─ answer_models.py
├─ answer_evidence.py
├─ answer_program.py
├─ answer_validation.py
├─ answer_generator.py
└─ artifacts/{optimized_program.json,optimization_metadata.json}

backend/experiments/attraction_dspy/
├─ dataset.py
├─ metrics.py
├─ optimize.py
├─ evaluate.py
└─ data/{train,dev,test,blind}.jsonl
```

---

### Task 1: DSPy 의존성과 attraction 설정

**파일:** `backend/pyproject.toml`, `backend/core/config.py`, `backend/tests/test_attraction_answer_contract.py`

- [x] 설정 RED 테스트를 작성한다.

```python
def test_attraction_dspy_defaults():
    self.assertEqual(settings.attraction_dspy_model, "openai/gpt-4o-mini")
    self.assertEqual(settings.attraction_dspy_temperature, 0.0)
    self.assertEqual(settings.attraction_dspy_max_tokens, 900)
```

- [x] `uv run python -m unittest tests.test_attraction_answer_contract -v`의 `AttributeError` 실패를 확인한다.
- [x] `dspy>=3.2.1,<3.3`과 다음 설정을 추가한다.

```python
attraction_dspy_model: str = "openai/gpt-4o-mini"
attraction_dspy_temperature: float = Field(default=0.0, ge=0, le=2)
attraction_dspy_max_tokens: int = Field(default=900, ge=1)
attraction_dspy_artifact_path: Path = (
    BASE_DIR / "domains" / "attraction" / "artifacts" / "optimized_program.json"
)
```

- [x] `uv lock` 후 테스트 `OK`를 확인한다.

### Task 2: 입력·출력 Pydantic 계약

**파일:** `backend/domains/attraction/answer_models.py`, `backend/tests/test_attraction_answer_contract.py`

- [x] 후보 최대 10개, 선택 최대 3개, 중복 ID 금지 RED 테스트를 작성한다.

```python
def test_result_rejects_duplicate_ids():
    with self.assertRaises(ValueError):
        AttractionAnswerResult(answer="추천", selections=[
            AttractionSelection(place_id="1", selection_reason="근거"),
            AttractionSelection(place_id="1", selection_reason="근거"),
        ])
```

- [x] `AttractionEvidenceCandidate`, `AttractionAnswerInput`, `AttractionSelection`, `AttractionAnswerResult`를 구현한다.
- [x] 후보에 ID·rank·이름·카테고리·거리·설명·리뷰·행사 기간·혼잡도 필드만 허용한다.
- [x] 계약 테스트를 통과시킨다.

### Task 3: SearchCandidate 근거 변환

**파일:** `backend/domains/attraction/answer_evidence.py`, `backend/tests/test_attraction_answer_contract.py`

- [x] 리뷰 5건, 허용 필드, 혼잡도 signal, 종료 행사 거부 RED를 작성한다.
- [x] 종료일이 이전인 event는 실패하고, 종료일이 없는 event는 통과함을 검증한다.
- [x] 다음 함수를 구현하고 `vector_similarity`는 제외한다.

```python
def build_attraction_answer_input(
    *, question: str, language: str, location: str | None,
    themes: list[str], candidates: list[SearchCandidate], today: date | None = None,
) -> AttractionAnswerInput: ...
```

- [x] 변환 테스트를 통과시킨다.

### Task 4: DSPy Signature·Program·artifact loader

**파일:** `backend/domains/attraction/answer_program.py`, `backend/tests/test_attraction_answer_generator.py`

- [x] `selected_place_ids`, `selection_reasons_json`, `answer` 필드와 artifact 부재·손상 RED를 작성한다.
- [x] 노트북의 언어·근거·혼잡도 규칙을 Signature에 이식한다.

```python
class AttractionSelectionAnswerSignature(dspy.Signature):
    language: str = dspy.InputField()
    question: str = dspy.InputField()
    location: str = dspy.InputField()
    themes_json: str = dspy.InputField()
    selection_count: int = dspy.InputField()
    candidates_json: str = dspy.InputField()
    selected_place_ids: list[str] = dspy.OutputField()
    selection_reasons_json: str = dspy.OutputField()
    answer: str = dspy.OutputField()
```

- [x] `load_attraction_program()`은 MIPROv2를 실행하지 않고 artifact만 로드하도록 구현한다.
- [x] loader·Signature 테스트를 통과시킨다.

### Task 5: 출력 검증과 fallback

**파일:** `backend/domains/attraction/answer_validation.py`, `backend/tests/test_attraction_answer_validation.py`

- [x] 미등록·중복 ID, 선택 수 부족, 빈 이유, 혼잡도 부재 추론 RED를 작성한다.

```python
def test_unknown_id_uses_ranked_fallback():
    result = validate_attraction_prediction(answer_input(), prediction(ids=["unknown"]))
    self.assertTrue(result.used_fallback)
    self.assertEqual([item.place_id for item in result.selections], ["1", "2", "3"])
```

- [x] `validate_attraction_prediction()`과 `fallback_attraction_answer()`를 구현한다.
- [x] fallback은 재랭킹 상위 3개와 한국어·영어 안전 이유를 반환한다.
- [x] 잘못된 prediction을 부분 수정하지 않고 전체 fallback으로 전환한다.

### Task 6: AttractionAnswerGenerator 운영 진입점

**파일:** `backend/domains/attraction/answer_generator.py`, `backend/domains/attraction/__init__.py`, `backend/tests/test_attraction_answer_generator.py`

- [x] 정상 prediction, 모델 예외, artifact 부재, timeout 테스트를 작성한다.
- [x] 동기 DSPy 호출을 `asyncio.to_thread()`에서 30초 timeout으로 실행한다.

```python
prediction = await asyncio.wait_for(
    asyncio.to_thread(program, **program_inputs),
    timeout=30.0,
)
```

- [x] 모든 예외은 정적 상위 후보 fallback으로 종료하도록 구현한다.
- [x] attraction package에 lazy export를 추가하고 테스트를 통과시킨다.

### Task 7: 5~10개 후보 평가 데이터셋

**파일:** `backend/experiments/attraction_dspy/dataset.py`, `backend/experiments/attraction_dspy/data/*.jsonl`, `backend/tests/test_attraction_dspy_dataset.py`

- [ ] 기존 40건의 출처를 기록하고 5~10개 후보 스냅샷으로 확장한다.
- [ ] `public_input`과 `private_label`을 분리하고, 사람이 `acceptable_place_ids`, 필수 조건, 금지 주장을 검토한다.
- [ ] Train 30 / Dev 10 / Test 10 / Blind 20을 구성한다.
- [x] split ID 교차와 private label 입력 누수가 없는지 테스트한다.

### Task 8: Hybrid Metric

**파일:** `backend/experiments/attraction_dspy/metrics.py`, `backend/tests/test_attraction_dspy_dataset.py`

- [x] 선택 40%, 근거 25%, 조건 15%, 언어·구조 10%, 명료성 10% 점수 RED를 작성한다.
- [x] 미등록·중복 ID, 근거 없는 사실, 언어 불일치, 혼잡도 부재 추론, 종료 행사를 hard fail 0점으로 구현한다.
- [x] 기존 노트북처럼 규칙 40% + Private DSPy Judge 60%로 구성한다.
- [x] Reference answer와 private label이 optimizer input에 섞이지 않는지 테스트한다.

### Task 9: Manual·DSPy baseline 비교 runner

**파일:** `backend/experiments/attraction_dspy/evaluate.py`

- [x] `manual`, `dspy_baseline`, `dspy_optimized` CLI와 API 미호출 `--dry-run`을 구현한다.
- [x] JSONL에 case ID, 방식, 선택 ID, 이유, 답변, 시간, 오류를 저장한다.

```bash
cd backend
uv run python -m experiments.attraction_dspy.evaluate \
  --methods manual,dspy_baseline --split test --dry-run
```

- [ ] `cases=10`, `methods=2`, dataset fingerprint를 확인한 후 API 비용 승인을 받아 실행한다.

### Task 10: MIPROv2 오프라인 최적화

**파일:** `backend/experiments/attraction_dspy/optimize.py`, `backend/domains/attraction/artifacts/*`

- [x] Train/Dev만 읽고 Test/Blind ID와 교차하지 않는지 검사한다.
- [x] `num_candidates=5`, `num_trials=5`, demo 0, thread 1, seed 42로 `--dry-run`을 먼저 실행한다.
- [ ] API 비용 승인 후 MIPROv2를 실행한다.
- [ ] artifact와 DSPy 버전, 모델, temperature, token, dataset hash, split 수, seed, 소요 시간 metadata를 저장한다.

### Task 11: Test·Blind 평가와 artifact 채택

**파일:** `backend/experiments/attraction_dspy/evaluate.py`, `backend/experiments/attraction_dspy/results/selection_answer_report.md`

- [ ] Manual / baseline / optimized를 Test·Blind에서 재생성하고 방식명을 숨긴 리포트를 생성한다.
- [ ] 미등록·중복 ID 0건, 언어 100%, 혼잡도 부재 추론 0건, 종료 행사 0건, hard fail 0%를 검증한다.
- [ ] Blind 평균이 Manual 이상이고 평균 생성 10초 이하인 artifact만 채택한다.

### Task 12: attraction 통합 경계와 핸드오프

**파일:** `backend/domains/attraction/agent.py` 또는 신규 orchestration, `backend/domains/attraction/README.md`, `backend/tests/test_attraction_answer_generator.py`

- [x] 검색 → 정적 재랭킹 → 혼잡도 재랭킹 → DSPy 순서를 통합 테스트한다.
- [x] `/chat`을 수정하지 않고 attraction 진입점만 완성한다.
- [x] README에 호출법과 `answer → SSE token`, `selections → Place[]`의 채팅 핸드오프 계약을 기록한다.

### Task 13: 최종 회귀 검증

- [x] attraction DSPy 집중 테스트를 실행한다.

```bash
cd backend
uv run python -m unittest \
  tests.test_attraction_answer_contract \
  tests.test_attraction_answer_validation \
  tests.test_attraction_answer_generator \
  tests.test_attraction_dspy_dataset -v
```

- [x] TravelQuery·도메인·채팅 공통 회귀 테스트를 실행한다.
- [x] `uv run python -m unittest discover -s tests`로 전체 테스트를 실행하고 기존 무관 실패를 분리 보고한다.
- [ ] `git diff --check`와 핵심 import 검사를 통과시킨다.
- [x] 실제 Vector DB 후보 스냅샷 1건으로 입력·출력·fallback을 읽기 전용으로 확인한다.

## 최종 산출물

```text
AttractionAnswerGenerator / AttractionAnswerResult
최적화 DSPy artifact와 metadata
Train / Dev / Test / Blind 데이터셋과 hash
Manual / baseline / optimized 블라인드 리포트
안전 fallback과 채팅 담당자 호출 계약
```

본 계획 실행 단계에서는 채팅·프론트 파일을 변경하지 않는다.
