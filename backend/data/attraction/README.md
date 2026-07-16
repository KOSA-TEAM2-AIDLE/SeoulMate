# 관광지·행사 데이터 파이프라인

`raw/`에는 Visit Seoul 원본 CSV, `processed/`, `documents/`, `manifests/`는
`scripts.attraction.build_documents`를 통해 생성되는 파생 파일

행사 종료일이 기준일보다 이전이면 제외합니다. 종료일이 비어 있는 행사는 상시 행사 후보로
포함하며, 날짜 형식이 올바르지 않은 종료일은 `events_quarantine.csv`에 기록합니다.
상시 관광지는 포함합니다.

```bash
uv run python -m scripts.attraction.build_documents --as-of 2026-07-16
uv run python -m scripts.attraction.build_documents --as-of 2026-07-16 --dry-run
uv run python -m scripts.attraction.load_vectors --batch-size 100
```
