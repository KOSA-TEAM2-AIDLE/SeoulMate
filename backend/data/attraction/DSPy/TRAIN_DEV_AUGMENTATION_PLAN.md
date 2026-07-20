# Attraction DSPy train/dev augmentation plan

## 목적

현재 gold 평가는 **최종 비교 전용**이다. 따라서 이 파일과
`gold_test/gold_test.jsonl`의 사례는 train/dev에 직접 복사하지 않는다. gold에서
드러난 실패 양상을 바탕으로, 별도의 후보·질문·정답 사례를 만들어 사람 검수 후에만
학습 데이터로 반영한다.

## 반영 순서

1. `gold_test/REVIEW_QUEUE.md`에서 질문이 후보 근거만으로 정답을 구분하는지와 기대
   후보 ID가 맞는지를 검수한다.
2. 검수 결과 중 모호하거나 후보/정답이 틀린 사례는 gold에서 제외하거나 수정한다.
   이 단계는 평가 데이터의 품질을 위한 것이며 학습 반영이 아니다.
3. 각 실패 유형에 대해 gold와 **후보 ID, 원문 source_place_cid, split_group이 모두
   겹치지 않는** 새 사례를 만든다. 새 사례에도 `review_status: pending`을 둔다.
4. 사람이 `reviewed`로 승인한 새 사례만 train 또는 dev에 배치한다. dev에는 전체의
   약 20%를 두어 재최적화 선택에 사용하고, 나머지는 train에 둔다.
5. split artifact를 재최적화한 뒤, 기존 artifact와 독립 gold에서 다시 비교한다.
   gold exact match와 오류 수가 기존 단일 artifact보다 좋아질 때만 교체 후보로
   승인한다.

## 우선 보강 유형

| 유형 | 목표 수 | selection에 주는 신호 | answer에 주는 신호 |
| --- | ---: | --- | --- |
| 다후보 구분 | 12 | 서로 비슷한 후보 중 근거 일치 후보만 선택 | 선택 근거를 자연스러운 추천 이유로 변환 |
| 제외 조건 | 8 | 날짜·요금·실내/실외 등 불일치 후보 배제 | 제외 사유를 사실처럼 단정하지 않음 |
| 문맥 근거 | 8 | 설명/리뷰의 세부 사실을 정답 근거로 연결 | 후보 설명과 충돌하지 않는 답변 |
| 결과 없음 | 4 | 조건을 만족하는 후보가 없으면 빈 선택 | `no_result_reason`을 명확하게 작성 |

총 32개를 초안으로 만들며, 26개 train / 6개 dev를 목표로 한다. 이는 gold 40개와
별개의 사례 집합이다.

## 금지 규칙

- `gold_test`의 질문, candidate ID, `source_place_cid`, `split_group`을 train/dev에
  재사용하지 않는다.
- `pending` 또는 `rejected` 사례를 optimizer 입력으로 전달하지 않는다.
- 사람 검수 없이 LLM이 만든 기대 ID를 정답으로 확정하지 않는다.
- gold 결과가 나쁘다는 이유만으로 prompt/artifact를 즉시 교체하지 않는다. 반드시
  train/dev 재최적화와 gold 재평가를 거친다.

## Artifact 반영 기준

새 `selection_v1.json`과 `answer_v1.json`은 다음 모두를 만족할 때만 현재 artifact를
대체한다.

1. train/dev의 계약 검증과 회귀 테스트 통과
2. 기존 단일 artifact보다 gold exact match가 높거나 같고, 오류 수는 더 적음
3. 사람이 검수한 gold의 각 유형에서 명백한 퇴행이 없음

