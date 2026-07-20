import httpx

from core.config import settings
from schemas.transit import TransitPoint, TransitSegment


class TransitProviderError(RuntimeError):
    """The transit provider accepted the request but could not authorize it."""


def build_lane_map_object(map_object: str) -> str:
    return map_object if "@" in map_object else f"0:0@{map_object}"


def parse_transit_segment(
    origin: TransitPoint, destination: TransitPoint, path: dict,
) -> TransitSegment:
    info = path.get("info", {})
    walking_minutes = info.get("totalWalkTime")
    if not isinstance(walking_minutes, int) or walking_minutes < 0:
        walking_minutes = sum(
            step.get("sectionTime", 0)
            for step in path.get("subPath", [])
            if step.get("trafficType") == 3
        )
    transit_leg_count = info.get("busTransitCount", 0) + info.get("subwayTransitCount", 0)
    return TransitSegment(
        origin=origin,
        destination=destination,
        duration_minutes=info.get("totalTime"),
        fare=info.get("payment"),
        transfers=max(0, transit_leg_count - 1),
        walking_minutes=walking_minutes,
        steps=path.get("subPath", []),
        map_object=info.get("mapObj"),
    )


class TransitRouteService:
    def __init__(self):
        self._cache: dict[tuple, TransitSegment] = {}

    async def route(self, origin: TransitPoint, destination: TransitPoint, language: str = "en") -> TransitSegment:
        key = (origin.lat, origin.lng, destination.lat, destination.lng, language)
        if key in self._cache:
            return self._cache[key]
        if not settings.odsay_enabled:
            raise RuntimeError("ODsay routing is not configured")
        params = {"apiKey": settings.odsay_api_key.get_secret_value(), "SX": origin.lng, "SY": origin.lat, "EX": destination.lng, "EY": destination.lat, "lang": 1 if language == "en" else 0}
        async with httpx.AsyncClient(timeout=settings.odsay_timeout_seconds) as client:
            response = await client.get(f"{settings.odsay_api_base_url}/searchPubTransPathR", params=params)
            response.raise_for_status()
        payload = response.json()
        result = payload.get("result", {})
        paths = result.get("path", [])
        if not paths:
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("msg") or error.get("message")
            else:
                message = str(error) if error else None
            if message or result.get("errorMsg"):
                raise TransitProviderError(f"ODsay: {message or result['errorMsg']}")
            raise LookupError("No public-transit route found")
        segment = parse_transit_segment(origin, destination, paths[0])
        self._cache[key] = segment
        return segment

    async def lane_geometry(self, map_object: str) -> dict:
        if not settings.odsay_enabled:
            raise RuntimeError("ODsay routing is not configured")
        async with httpx.AsyncClient(timeout=settings.odsay_timeout_seconds) as client:
            response = await client.get(
                f"{settings.odsay_api_base_url}/loadLane",
                params={
                    "apiKey": settings.odsay_api_key.get_secret_value(),
                    "mapObject": build_lane_map_object(map_object),
                },
            )
            response.raise_for_status()
        return response.json().get("result", {})


transit_route_service = TransitRouteService()
