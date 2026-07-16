import asyncio
from domains.common.models import DomainSearchRequest
from domains.accommodation.search_service import AccommodationSearchService

async def main():
    print("=== 숙박 에이전트 독립 테스트 ===")
    
    # 프론트엔드가 /travel-query/start 로부터 받은 응답(structured_query) 모의
    structured_query = {
        "intent": "single_place_recommendation",
        "normalized_question": "성수에서 2026-07-16부터 2026-07-17까지 1박할 숙소를 추천해줘.",
        "filters": {
            "location": "성수",
            "radius_km": None
        },
        "tasks": [
            {
                "task_id": "task_1",
                "domain": "accommodation",
                "search_query": "성수 숙소",
                "themes": [],
                "desired_count": 3
            }
        ]
    }
    
    normalized_question = structured_query["normalized_question"]
    task_1 = structured_query["tasks"][0]
    
    print(f"[전달된 질문]: {normalized_question}\n")
    
    # 도메인 검색 서비스 초기화
    service = AccommodationSearchService()
    
    # 챗 라우터가 도메인 검색 서비스에 전달하는 DomainSearchRequest 객체 모의
    request = DomainSearchRequest(
        task_id=task_1["task_id"],
        domain=task_1["domain"],
        search_query=normalized_question,
        themes=task_1["themes"],
        location=structured_query["filters"].get("location", "성수동"),
        latitude=-90.0,
        longitude=-180.0,
        current_location_name="성수동",
        candidate_count=3,
        context={
            "parsed_query": structured_query,
            "task": task_1
        }
    )
    
    print("에이전트 검색 중... (로컬 DB 및 웹 스크레이퍼 연동)\n")
    candidates = await service.search(request)
    
    print(f"✅ 총 {len(candidates)}개의 추천 숙소를 찾았습니다!\n")
    for idx, c in enumerate(candidates, 1):
        print(f"[{idx}] {c.name}")
        print(f"   - 추천 융합 점수: {c.final_score:.2f}")
        print(f"   - 주소: {c.attributes.get('address')}")
        print(f"   - 카테고리: {c.category}")
        print(f"   - 평점: {c.attributes.get('rating')} (리뷰 {c.attributes.get('review_count')}개)")
        print(f"   - 실시간 라이브 평점: {c.attributes.get('live_rating')}")
        print(f"   - 실시간 가격: {c.attributes.get('price')}")
        print(f"   - 편의시설: {c.attributes.get('features')}")
        print(f"   - 예약 링크: {c.attributes.get('url')}")
        print(f"   - 선정 이유: {c.attributes.get('reason')}")
        print("-" * 60)

if __name__ == "__main__":
    asyncio.run(main())
