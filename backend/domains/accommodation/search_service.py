from domains.common.models import DomainSearchRequest, SearchCandidate
from domains.common.search_interface import DomainSearchService
from domains.accommodation.agent import search_accommodations_structured

class AccommodationSearchService:
    domain = "accommodation"
    implemented = True

    async def search(self, request: DomainSearchRequest) -> list[SearchCandidate]:
        # agent.py의 로직이 동기식일 수 있으므로, 비동기 환경에서 안전하게 호출하려면
        # 보통 asyncio.to_thread 를 사용하지만, DomainSearchService 구현체 내에서 직접 호출하거나
        # 필요 시 감쌀 수 있습니다. 현재 구조상 직접 호출합니다. (또는 필요 시 to_thread 적용)
        import asyncio
        
        # search_accommodations_structured 반환값 형식: {"candidates": [...]}
        # candidates의 각 항목: "accommodation_id", "name", "category", "lat", "lng", "score", "reason", "features", "address", 등
        result_dict = await asyncio.to_thread(search_accommodations_structured, request)
        
        raw_candidates = result_dict.get("candidates", [])
        
        candidates = []
        for raw in raw_candidates:
            candidates.append(
                SearchCandidate(
                    domain=self.domain,
                    place_id=raw["accommodation_id"],
                    task_id=request.task_id,
                    name=raw["name"],
                    category=raw.get("category") or "숙박시설",
                    latitude=raw.get("lat"),
                    longitude=raw.get("lng"),
                    base_score=float(raw.get("score", 0.0)),
                    final_score=float(raw.get("score", 0.0)),
                    evidence=[raw.get("reason", "")],
                    attributes={
                        "reason": raw.get("reason", ""),
                        "features": raw.get("features", ""),
                        "address": raw.get("address", ""),
                        "rating": raw.get("rating"),
                        "review_count": raw.get("review_count"),
                        "price": raw.get("price"),
                        "live_rating": raw.get("live_rating"),
                        "url": raw.get("url"),
                        "image": raw.get("image"),
                    },
                    signals={"source_kind": "rag" if "RAG" in raw.get("reason", "") else "mcp"}
                )
            )
            
        return candidates

__all__ = ["AccommodationSearchService"]
