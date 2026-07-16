import asyncio
from application.travel_query.service import get_travel_query_service
from schemas.chat import TravelQueryStartRequest
from domains.common.models import DomainSearchRequest
from domains.accommodation.search_service import AccommodationSearchService

async def main():
    print("=== 1. TravelQueryGraph 실행 시작 ===")
    service = get_travel_query_service()
    
    # 프론트엔드가 보내는 초기 요청
    request = TravelQueryStartRequest(
        message="성수동 숙소 추천해줘.",
        language="ko",
        lat=-90.0,
        lng=-180.0,
        location_name="성수동"
    )
    
    # Graph 실행
    response = await service.start(request)
    
    query = response.structured_query
    if not query:
        print("에러: structured_query가 생성되지 않았습니다.")
        return
        
    normalized_question = query.normalized_question
    print(f"\n[추출된 질문]: {normalized_question}")
    
    if not query.tasks:
        print("에러: 추출된 task가 없습니다.")
        return
        
    task_1 = query.tasks[0]
    
    print("\n=== 2. Accommodation Agent 실행 시작 ===")
    agent = AccommodationSearchService()
    
    domain_request = DomainSearchRequest(
        task_id=task_1.task_id,
        domain=task_1.domain,
        search_query=normalized_question,
        themes=task_1.themes,
        location=query.filters.location if query.filters else "성수동",
        latitude=request.lat,
        longitude=request.lng,
        current_location_name=request.location_name,
        candidate_count=3,
        context={
            "parsed_query": query.model_dump(),
            "task": task_1.model_dump()
        }
    )
    
    candidates = await agent.search(domain_request)
    
    print(f"\n총 {len(candidates)}개의 추천 시설을 찾았습니다!\n")
    for idx, c in enumerate(candidates, 1):
        print(f"[{idx}] {c.name}")
        print(f"   - 점수: {c.final_score:.2f}")
        print(f"   - 주소: {c.attributes.get('address')}")
        print(f"   - 카테고리: {c.category}")
        print(f"   - 평점: {c.attributes.get('rating')} (리뷰 {c.attributes.get('review_count')}개)")
        print(f"   - 라이브 평점: {c.attributes.get('live_rating')}")
        print(f"   - 가격: {c.attributes.get('price')}")
        print(f"   - 편의시설: {c.attributes.get('features')}")
        print(f"   - URL: {c.attributes.get('url')}")
        print(f"   - 선정 이유: {c.attributes.get('reason')}")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())
