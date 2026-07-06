# mock 데이터 (1단계)

API 명세서 9장 기준 lang별 파일 규칙. RAG/MCP 연동(2단계) 전까지 아래 파일들을 두고 서비스 계층에서 읽어들인다.

| 리소스 | ko | en |
|---|---|---|
| 카페 | `cafe.json`, `cafe_review.json` | `cafe_en.json`, `cafe_review_en.json` |
| 맛집 | `restaurant.json`, `restaurant_review.json` | `restaurant_en.json`, `restaurant_review_en.json` |
| 숙소 | `accommodation.json`, `accommodation_review.json` | `accommodation_en.json`, `accommodation_review_en.json` |
| 축제 | `event.json`, `event_review.json` | `event_en.json`, `event_review_en.json` |
| 물품보관소 | `storage_locker.json` (리뷰 없음) | `storage_locker_en.json` |
| RAG 코퍼스 | `places.json` | - |
