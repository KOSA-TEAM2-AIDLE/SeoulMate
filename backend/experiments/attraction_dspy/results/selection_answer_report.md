# Attraction DSPy 선택·답변 평가 리포트

## 현재 상태

- 평가 runner: 구현 완료
- MIPROv2 runner: 구현 완료
- 데이터: provisional Train 30 / Dev 10 / Test 10 / Blind 20
- 유료 API 실행: `gpt-4o-mini`, 비용 절감 설정으로 1회
- artifact: provisional 채택
- dataset fingerprint: `4091c80f1174f2069e0dd51fb0a36fc507fc02e9a0a9a73c193da781d84d11bb`

사람 검수 대신 기존 재랭킹 상위 3개를 provisional 허용 ID로 사용했다. 따라서 이 artifact는 검색 순위를 재학습하는 모델보다 현재 검색 결과를 안전하게 선택·설명하는 모델로 평가한다.

## 실행 결과

| 구분 | 결과 |
|---|---:|
| MIPROv2 Dev 평균 | 95.57% |
| Test 케이스 | 10 |
| Test API 오류 / hard fail | 0 / 0 |
| Test 규칙 평균 | 0.9250 |
| Test 평균 생성 시간 | 2.648초 |
| Blind 케이스 | 20 |
| Blind API 오류 / hard fail | 0 / 0 |
| Blind 규칙 평균 | 0.9525 |
| Blind 평균 생성 시간 | 3.098초 |

지시문 후보 3개와 기본 지시문의 Dev 점수가 모두 95.57%로 동일했다. 70% 비용 상한을 지키기 위해 Manual·baseline의 Test/Blind 재생성은 생략했다.

## artifact 채택 기준

- Test·Blind 미등록/중복 ID: 0건
- 질문과 답변 언어 일치: 100%
- 혼잡도 부재 추론: 0건
- 종료 행사 선택: 0건
- hard fail: 0%
- Blind 평균: Manual 이상
- 평균 생성 시간: 10초 이하

## Blind 방법 비공개 비교

실행 후 `method` 값을 A/B/C로 치환한 본을 사람 검토자에게 제공하고, 검토가 끝난 후에만 방식명을 복원한다.
