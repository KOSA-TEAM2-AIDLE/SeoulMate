# 관광 DSPy 평가 데이터 준비 현황

## 목표 split

| split | 목표 수 |
|---|---:|
| Train | 30 |
| Dev | 10 |
| Test | 10 |
| Blind | 20 |

`dataset.py`는 `train.jsonl`, `dev.jsonl`, `test.jsonl`, `blind.jsonl`을 위 개수로 요구한다. split 간 `case_id`가 중복되거나 `human_review_status` 값이 `reviewed`가 아니면 최적화용으로 로드하지 않는다.

## 기존 노트북 자료 인벤토리

출처: `999.datacheck/jupyter/Tourism_Agent_DSPy_Prompt_Optimization.ipynb`이 생성한 `data/evaluation/dspy_prompt_optimization`.

| 기존 split | 수 | 라벨 상태 |
|---|---:|---|
| Train | 16 | `needs_review` 16 |
| Dev | 8 | `needs_review` 8 |
| Test | 6 | `needs_review` 6 |
| Blind | 22 | 선택 허용 ID 라벨 없음 |

기존 평가는 이미 선택된 후보의 답변 생성용이었으므로, 5~10개 후보에서 3개를 선택하는 이번 계약의 `acceptable_place_ids`를 사람이 다시 검수해야 한다. 검수가 끝나기 전에 임의의 상위 3개를 정답으로 채우지 않는다.

## JSONL 계약

각 행은 `AttractionDspyCase`이며 다음 영역을 갖는다.

- `case_id`, `source`
- `public_input`: 질문·언어·위치·테마·5~10개 후보
- `private_label`: 허용 ID·필수 조건·금지 주장·검수 상태

`reference_answer`는 선택적 private 비교용이며 DSPy optimizer와 Private Judge 입력에 전달되지 않는다.
