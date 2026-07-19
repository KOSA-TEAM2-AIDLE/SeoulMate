# SeoulMate Backend DSPy 최적화·배포 작업 명세서

## 1. 목적

관광지 추천의 최종 선택·답변 생성 단계를 DSPy 프로그램으로 구현하고,
최적화 결과를 SeoulMate 백엔드에서 로드하여 운영 입력에 사용할 수 있게 한다.

대상 백엔드 경로:

```text
/Users/younder/Desktop/아이티센 AIE 부트캠프/999.프로젝트/2.2차미니프로젝트/SeoulMate/backend
```

이 작업은 Query Parser, HITL, 도메인 라우팅, 검색 서비스 자체를 변경하지
않는다. DSPy의 입력은 이미 파싱·검색·Context Enrichment가 끝난
`AttractionAnswerInput`이다.

### 1.1 현재 운영 연결점과 이번 적용 범위

현재 일반 관광 추천은 다음 경로로 이미 기존 DSPy를 사용한다.

```text
POST /chat
→ TravelQuery Parser
→ AttractionSearchService
→ AttractionContextEnricher (혼잡도·날씨)
→ select_grouped_candidates
→ DomainSelectionRegistry
→ AttractionSelectionService
→ AttractionAnswerGenerator
→ 기존 optimized_program.json
→ SSE Place meta + token 답변
```

따라서 이번 작업의 목적은 **새 DSPy 실험 결과로 이 기존 단일 artifact를
교체하는 것**이다. `/chat`의 Parser·검색·Context Enrichment와 식당·카페·숙박의
선택 방식은 변경하지 않는다.

적용 대상은 아래 두 경우다.

- 단일 관광지 추천
- 관광지가 포함된 복합 추천의 관광 Task

아래 경우는 이번 범위에서 제외한다.

- 당일/다일 루트의 관광 슬롯: 현재 루트 플래너가 슬롯별 후보를 별도로 선택하며
  `AttractionSelectionService`를 거치지 않는다. 이 경로까지 적용하려면 루트 후보
  선택 계약과 별도 통합·평가가 필요하다.

기존 `AttractionAgent`와 `ReadyDomainAgentDispatcher`는 별도 도메인 실행 경로이며,
현재 일반 `/chat` 응답의 DSPy 호출 연결점으로 가정하지 않는다.

## 2. 현재 준비된 데이터셋

기존 데이터셋 위치:

```text
/Users/younder/Desktop/아이티센 AIE 부트캠프/999.프로젝트/2.2차미니프로젝트/SeoulMate/backend/data/attraction/DSPy
```

| 데이터 | Train | Dev | Test | 합계 |
| --- | ---: | ---: | ---: | ---: |
| Selection | 100 | 30 | 50 | 180 |
| Answer | 100 | 30 | 50 | 180 |
| Exception | 40 | 15 | 25 | 80 |
| 합계 | 240 | 75 | 125 | 440 |

Gold Test는 `gold_test/gold_test.jsonl`에 40개가 있다.

Answer 예제의 `expected.structured_answer`는 다음 계약을 사용한다.

```json
{
  "language": "ko",
  "recommendations": [
    {
      "place_id": "001136",
      "name": "석촌호수공원",
      "recommendation_reason": "추천 근거",
      "description_evidence": ["시설 설명 근거"],
      "review_evidence": ["리뷰 근거"],
      "congestion": {
        "status": "available | unavailable",
        "value": "string | null",
        "basis": "string | null",
        "observed_at": "ISO-8601 string | null"
      },
      "weather": {
        "status": "available | unavailable",
        "value": "string | null"
      },
      "visitor_note": "방문 참고사항"
    }
  ],
  "no_result_reason": "string | null"
}
```

`congestion` 또는 `weather`가 입력 후보에서 `null`이면 결과의 상태는 반드시
`unavailable`이고 값은 반드시 `null`이다. 없는 값을 낮은 혼잡도나 좋은 날씨로
추론하면 안 된다.

## 3. 구현 범위

### 3.1 백엔드 파일 구조

```text
backend/
├── data/
│   └── attraction/
│       └── DSPy/
│           ├── selection/
│           │   ├── train.jsonl
│           │   ├── dev.jsonl
│           │   └── test.jsonl
│           ├── answer/
│           │   ├── train.jsonl
│           │   ├── dev.jsonl
│           │   └── test.jsonl
│           ├── exception/
│           │   ├── train.jsonl
│           │   ├── dev.jsonl
│           │   └── test.jsonl
│           ├── gold_test/
│           │   └── gold_test.jsonl
│           ├── normalized/
│           ├── schemas/
│           ├── README.md
│           ├── generation_report.md
│           └── validation_report.json
│
├── experiments/
│   └── attraction_dspy/
│       ├── config.py
│       ├── dataset_loader.py
│       ├── metrics.py
│       ├── optimize.py
│       ├── evaluate.py
│       ├── compare_baseline.py
│       ├── export_artifact.py
│       ├── data/                 # 실행 중간 산출물만
│       └── results/
│           ├── baseline/
│           ├── optimized/
│           └── reports/
│
├── domains/
│   └── attraction/
│       ├── dspy/
│       │   ├── __init__.py
│       │   ├── contracts.py
│       │   ├── signatures.py
│       │   ├── programs.py
│       │   ├── adapter.py
│       │   ├── validator.py
│       │   ├── renderer.py
│       │   └── service.py
│       └── artifacts/
│           ├── selection_v1.json
│           ├── answer_v1.json
│           └── metadata.json
│
├── application/
│   └── recommendation/
│       └── selection_registry.py        # attraction 전용 selector 등록
│
└── tests/
    ├── domains/
    │   └── attraction/
    │       ├── test_dspy_contracts.py
    │       ├── test_dspy_validator.py
    │       ├── test_dspy_renderer.py
    │       └── test_dspy_service.py
    └── experiments/
        └── attraction_dspy/
            ├── test_metrics.py
            ├── test_dataset_loader.py
            └── test_evaluate.py
```

### 3.2 Selection DSPy

`SelectionSignature`는 다음 입력을 받는다.

```text
question, language, location, themes, candidates
```

출력은 JSON 호환 구조로 고정한다.

```json
{
  "selected_place_ids": ["..."],
  "forbidden_place_ids": ["..."],
  "selection_reasons": {"place_id": "근거"}
}
```

규칙:

- 후보에 없는 `place_id`는 선택할 수 없다.
- `excluded + conflict` 후보는 선택할 수 없다.
- 결과 없음이면 `selected_place_ids=[]`로 반환한다.
- 최대 추천 수는 3개다.
- rank만으로 선택하지 않는다.

### 3.3 Answer DSPy

`AnswerSignature`는 선택된 후보의 근거만 사용하여 위의
`structured_answer` 계약을 출력한다.

반드시 지킬 규칙:

- `place_id`는 입력 후보에 존재해야 한다.
- `recommendation_reason`은 후보 description, category, constraint 또는
  제공된 Context를 근거로 작성한다.
- `review_evidence`는 입력의 `reviews` 목록에서만 선택·요약한다.
- 거리 값이 없으면 가까움/거리 수치를 주장하지 않는다.
- 혼잡도·날씨가 없으면 `unavailable`로 반환한다.
- 혼잡도 값이 권역 기준이면 `basis`와 `observed_at`을 보존하고, 시설 내부
  관측값처럼 표현하지 않는다.
- `language="ko"`면 모든 설명은 한국어, `language="en"`이면 영어로 출력한다.
- 후보가 없거나 조건을 만족하는 후보가 없으면 `recommendations=[]`와
  언어에 맞는 `no_result_reason`을 반환한다.

### 3.4 렌더러

`renderer.py`는 structured JSON을 서비스의 최종 응답 문장/DTO로 변환한다.
모델이 자유 문장 형식을 결정하게 하지 않는다.

권장 사용자 표시 순서:

```text
장소명
추천 사유
시설 근거
리뷰 근거 (있는 경우만)
혼잡도 (available인 경우 basis·observed_at 포함)
날씨 (available인 경우만)
방문 참고사항
```

`unavailable`인 혼잡도·날씨는 기본적으로 숨기거나 “정보 없음”으로 표시한다.
둘 중 어느 UX를 쓸지는 renderer의 단일 설정으로 관리한다.

## 4. Optimizer 구현

### 4.1 데이터 로딩

백엔드의 `optimizer.py`는 데이터셋 경로를 환경 변수 또는 설정으로 받는다.

```text
TOURISM_DSPY_DATASET_DIR=/Users/younder/Desktop/아이티센 AIE 부트캠프/999.프로젝트/2.2차미니프로젝트/SeoulMate/backend/data/attraction/DSPy
```

학습에는 Train만 사용한다. Dev는 Optimizer/프롬프트 후보 선택에만 사용한다.
Test와 Gold Test는 최종 비교 전까지 절대 학습에 사용하지 않는다.

### 4.2 Metric

Selection과 Answer의 Metric을 분리한다.

Selection Metric:

- selected ID 정확성 30%
- forbidden 후보 배제 20%
- 필수 조건 20%
- theme/category 10%
- 위치/거리 10%
- 리뷰·실시간 Context 10%

Answer Metric:

- 선택 장소 정확성 25%
- 시설 근거 일치 20%
- 리뷰 근거 일치 15%
- 사용자 조건 반영 15%
- 거리·혼잡도·날씨 정확성 10%
- 답변 구조 10%
- 문장 품질 5%

아래 Hard Failure는 즉시 0점이다.

```text
후보 외 장소
존재하지 않는 리뷰
근거 없는 거리
근거 없는 혼잡도
근거 없는 날씨
근거 없는 시설 사실
종료 행사 현재 추천
excluded conflict 후보 추천
출력 언어 불일치
structured_answer 계약 위반
```

### 4.3 최적화 실행

초기 구현은 현재 프로젝트에 설치된 DSPy 버전에 맞는 `MIPROv2`를 사용한다.
DSPy 버전을 올릴 경우 GEPA 사용 가능 여부와 API 차이를 확인한 뒤 변경한다.

최적화 결과는 버전별 파일로 저장한다.

```text
artifacts/selection_v1.json
artifacts/answer_v1.json
artifacts/metadata.json
```

`metadata.json`에는 아래를 기록한다.

```json
{
  "artifact_version": "v1",
  "dspy_version": "...",
  "model": "...",
  "optimizer": "MIPROv2",
  "dataset_version": "...",
  "trained_at": "ISO-8601",
  "dev_metrics": {},
  "test_metrics": {},
  "git_commit": "optional"
}
```

## 5. 운영 로딩 및 기존 artifact 교체

운영 서버는 Optimizer나 Train/Dev 데이터셋을 실행하지 않는다.

```python
dspy.configure(lm=runtime_lm)

selection = TourismSelectionProgram()
selection.load(artifact_path / "selection_v1.json")

answer = TourismAnswerProgram()
answer.load(artifact_path / "answer_v1.json")
```

기존 운영 경로는 `AttractionSelectionService`가 `AttractionAnswerGenerator`를 통해
단일 `optimized_program.json`을 읽는다. 새 구현은 이 서비스의 내부 호출을 아래처럼
교체한다.

```text
기존: optimized_program.json 1개
새로: selection_v1.json → answer_v1.json → structured_answer 검증
```

호출자(`select_grouped_candidates`)의 공통 반환 계약은 유지한다.

```text
CandidateSelectionResult
  - selections[].place_id
  - selections[].selection_reason
  - answer
  - used_fallback
```

즉 Selection DSPy 결과의 ID·이유는 기존 `Place.selection_reason`에 연결되고,
Answer DSPy의 렌더링 결과는 기존 SSE `token` 답변으로 전달된다. 프론트엔드의
`Place`/SSE 계약은 이번 작업에서 변경하지 않는다.

요청 흐름:

```text
AttractionSearchService 후보
→ AttractionContextEnricher의 최신 혼잡도·날씨
→ AttractionAnswerInput
→ Selection DSPy
→ Answer DSPy
→ structured_answer 검증
→ renderer/adapter
→ CandidateSelectionResult
→ 기존 /chat SSE Place meta + token 답변
```

운영에서도 DSPy 런타임, Signature/Program 코드, 동일 또는 호환되는 DSPy 버전,
그리고 LLM API 설정은 필요하다. JSON artifact만 단독으로는 실행되지 않는다.

## 6. 테스트와 완료 기준

다음을 테스트로 보장한다.

1. 실제 `AttractionAnswerInput`을 adapter가 변경 없이 입력으로 받는다.
2. 후보 수는 10 이하, 후보당 리뷰는 5 이하이다.
3. Selection 결과의 모든 ID는 입력 후보에 존재한다.
4. Answer 결과의 모든 recommendation ID는 선택 후보에 존재한다.
5. `unavailable` Context에 값/주장을 넣으면 검증 실패한다.
6. available 혼잡도에는 basis와 observed_at이 유지된다.
7. 한글/영문 출력 정책을 검증한다.
8. Gold Test 40개를 평가하고 Hard Failure 수를 보고한다.
9. artifact를 save한 뒤 새 프로그램 인스턴스에서 load하여 동일한 구조의 결과를 낸다.
10. 일반 단일 관광 추천과 관광 포함 복합 추천의 `/chat` 통합 테스트에서 새
    artifact가 실제 호출되고, 선택 ID·추천 이유·SSE 답변에 반영됨을 검증한다.
11. 루트/일정의 관광 슬롯은 이번 artifact 적용 및 평가 대상에서 제외됨을
    회귀 테스트로 보장한다.

완료 산출물:

- 실행 가능한 Selection/Answer DSPy 프로그램
- 최적화 실행 스크립트
- 버전 관리된 artifact JSON 2개와 metadata
- Dev/Test/Gold Test 평가 리포트
- 백엔드 통합 테스트
- renderer/adapter를 거친 기존 `CandidateSelectionResult`, `Place`, SSE 응답

## 7. 주의사항

- 원본 데이터셋은 수정하지 않는다.
- 실제 운영 혼잡도·날씨는 요청 시점의 Enricher 결과를 사용한다. 학습용
  synthetic_context를 운영의 고정 사실로 사용하지 않는다.
- API 키·모델 식별자·개인정보가 artifact 또는 로그에 저장되지 않도록 한다.
- 기존 백엔드의 패키지명·설정 체계·Pydantic 모델을 먼저 조사하고 그 관례를
  우선한다.
- 기존 단일 artifact를 새 두 artifact로 교체하기 전에는, 두 artifact와 metadata를
  모두 load할 수 있는지 확인한다. 하나라도 load·검증에 실패하면 새 artifact를
  부분 적용하지 않고 기존의 안전 fallback을 사용한다.
- 루트/일정의 관광 슬롯에는 이번 작업의 Selection/Answer DSPy를 호출하지 않는다.
