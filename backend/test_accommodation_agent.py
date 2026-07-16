import asyncio
import requests
from domains.common.models import DomainSearchRequest
from domains.accommodation.search_service import AccommodationSearchService

async def main():
    print("=== 1. /travel-query/start API 호출 ===")
    payload = {
        "message": "성수동 숙소 추천해줘.",
        "language": "ko",
        "reference_at": "2026-07-16T01:41:57.089Z",
        "lat": -90,
        "lng": -180,
        "location_name": "성수동"
    }
    try:
        response = requests.post("http://localhost:8000/travel-query/start", json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"API 호출 실패! 로컬 서버가 켜져 있는지 확인하세요.\n에러: {e}")
        return

    structured_query = data.get("structured_query")
    if not structured_query:
        print("API 응답에 structured_query가 없습니다.")
        return
    
    normalized_question = structured_query.get("normalized_question")
    tasks = structured_query.get("tasks", [])
    if not tasks:
        print("API 응답에 추출된 task가 없습니다.")
        return
        
    task_1 = tasks[0]
    print(f"\n[추출된 질문]: {normalized_question}")
    
    print("\n=== 2. 숙박 에이전트 직접 호출 ===")
    service = AccommodationSearchService()
    
    request = DomainSearchRequest(
        task_id=task_1.get("task_id", "task_1"),
        domain="accommodation",
        search_query=normalized_question,
        themes=task_1.get("themes", []),
        location=structured_query.get("filters", {}).get("location", "성수동"),
        latitude=-90.0,
        longitude=-180.0,
        current_location_name="성수동",
        candidate_count=3,
        context={
            "parsed_query": structured_query,
            "task": task_1
        }
    )
    
    candidates = await service.search(request)
    
    print(f"\n총 {len(candidates)}개의 추천 시설을 찾았습니다!\n")
    for idx, c in enumerate(candidates, 1):
        print(f"[{idx}] {c.name}")
        print(f"   - 점수: {c.final_score:.2f}")
        print(f"   - 주소: {c.attributes.get('address')}")
        print(f"   - 카테고리: {c.category}")
        print(f"   - 평점: {c.attributes.get('rating')} (리뷰 {c.attributes.get('review_count')}개)")
        print(f"   - 라이브 평점: {c.attributes.get('live_rating')}")
        print(f"   - 가격: {c.attributes.get('price')}")
        print(f"   - 편의시설/특징: {c.attributes.get('features')}")
        print(f"   - 링크: {c.attributes.get('url')}")
        print(f"   - 선정 이유: {c.attributes.get('reason')}")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())
