import asyncio
import math
from time import monotonic
from urllib.parse import unquote

import httpx

from core.config import Settings, settings
from schemas.storage_lockers import (
    NearbyStorageLockersResult,
    StorageLockerCompartmentDetail,
    StorageLockerDetail,
    StorageLockerSizeAvailability,
    StorageLockerSummary,
)


class StorageLockerServiceError(Exception):
    """물품보관함 서비스 오류의 부모 클래스."""


class PublicDataApiKeyMissingError(StorageLockerServiceError):
    """공공데이터포털 인증키가 설정되지 않은 경우."""


class StorageLockerApiRequestError(StorageLockerServiceError):
    """공공데이터포털 요청에 실패한 경우."""


class StorageLockerApiResponseError(StorageLockerServiceError):
    """공공데이터포털 응답을 처리할 수 없는 경우."""


class StorageLockerNotFoundError(StorageLockerServiceError):
    """요청한 물품보관함을 찾지 못한 경우."""


class StorageLockerClient:
    INFO_PATH = "/locker_info_v2"
    DETAIL_PATH = "/locker_detail_info_v2"
    REALTIME_PATH = "/locker_realtime_use_v2"
    SUCCESS_CODE = "K0"
    MAX_PAGES = 100

    def __init__(
        self,
        config: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config or settings
        self._http_client = http_client
        self._cache: dict[
            tuple[str, str | None], tuple[float, list[dict]]
        ] = {}
        self._cache_lock = asyncio.Lock()

    def _get_api_key(self) -> str:
        secret = self._config.public_data_service_key
        if secret is None:
            raise PublicDataApiKeyMissingError(
                "PUBLIC_DATA_SERVICE_KEY가 설정되지 않았습니다."
            )
        value = secret.get_secret_value().strip()
        if not value:
            raise PublicDataApiKeyMissingError(
                "PUBLIC_DATA_SERVICE_KEY가 비어 있습니다."
            )
        # 포털의 Encoding 키를 붙여 넣어도 httpx가 이중 인코딩하지 않게 한다.
        return unquote(value)

    async def fetch_all(
        self,
        path: str,
        municipality_code: str | None = None,
    ) -> list[dict]:
        cache_key = (path, municipality_code)
        cached = self._cache.get(cache_key)
        if cached is not None and cached[0] > monotonic():
            return cached[1]

        async with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached is not None and cached[0] > monotonic():
                return cached[1]

            rows = await self._fetch_all_pages(path, municipality_code)
            expires_at = (
                monotonic() + self._config.storage_locker_cache_ttl_seconds
            )
            self._cache[cache_key] = (expires_at, rows)
            return rows

    async def _fetch_all_pages(
        self,
        path: str,
        municipality_code: str | None,
    ) -> list[dict]:
        rows: list[dict] = []
        page = 1
        while page <= self.MAX_PAGES:
            payload = await self._request_page(
                path=path,
                page=page,
                municipality_code=municipality_code,
            )
            body = _extract_body(payload)
            page_rows = _extract_items(body)
            rows.extend(page_rows)

            total_count = _to_int(body.get("totalCount"), default=len(rows))
            if not page_rows or len(rows) >= total_count:
                return rows
            page += 1

        raise StorageLockerApiResponseError(
            "물품보관함 API 페이지 수가 안전 한도를 초과했습니다."
        )

    async def _request_page(
        self,
        path: str,
        page: int,
        municipality_code: str | None,
    ) -> dict:
        params: dict[str, str | int] = {
            "serviceKey": self._get_api_key(),
            "pageNo": page,
            "numOfRows": self._config.storage_locker_api_page_size,
            "type": "JSON",
        }
        if municipality_code:
            params["stdgCd"] = municipality_code

        url = f"{self._config.storage_locker_api_base_url.rstrip('/')}{path}"
        try:
            if self._http_client is not None:
                response = await self._http_client.get(url, params=params)
            else:
                async with httpx.AsyncClient(
                    timeout=self._config.storage_locker_api_timeout_seconds
                ) as client:
                    response = await client.get(url, params=params)
            response.raise_for_status()
        except httpx.TimeoutException:
            raise StorageLockerApiRequestError(
                "물품보관함 API 요청 시간이 초과되었습니다."
            ) from None
        except httpx.HTTPStatusError as error:
            raise StorageLockerApiRequestError(
                "물품보관함 API가 HTTP 오류를 반환했습니다: "
                f"status={error.response.status_code}"
            ) from None
        except httpx.RequestError:
            raise StorageLockerApiRequestError(
                "물품보관함 API에 연결할 수 없습니다."
            ) from None

        try:
            payload = response.json()
        except ValueError:
            raise StorageLockerApiResponseError(
                "물품보관함 API 응답을 JSON으로 해석할 수 없습니다."
            ) from None
        if not isinstance(payload, dict):
            raise StorageLockerApiResponseError(
                "물품보관함 API 최상위 응답이 객체가 아닙니다."
            )
        return payload


def _extract_body(payload: dict) -> dict:
    response = payload.get("response", payload)
    if not isinstance(response, dict):
        raise StorageLockerApiResponseError(
            "물품보관함 API response 형식이 올바르지 않습니다."
        )
    header = response.get("header")
    if not isinstance(header, dict):
        raise StorageLockerApiResponseError(
            "물품보관함 API 응답에 header가 없습니다."
        )
    result_code = str(header.get("resultCode", "")).strip()
    if result_code != StorageLockerClient.SUCCESS_CODE:
        message = str(header.get("resultMsg", "알 수 없는 오류")).strip()
        raise StorageLockerApiResponseError(
            f"물품보관함 API 요청 실패: {result_code} {message}"
        )
    body = response.get("body")
    if not isinstance(body, dict):
        raise StorageLockerApiResponseError(
            "물품보관함 API 응답에 body가 없습니다."
        )
    return body


def _extract_items(body: dict) -> list[dict]:
    value = body.get("item")
    if value is None and isinstance(body.get("items"), dict):
        value = body["items"].get("item")
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(row, dict) for row in value):
        return value
    raise StorageLockerApiResponseError(
        "물품보관함 API item 형식이 올바르지 않습니다."
    )


def _text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _to_int(value: object, default: int = 0) -> int:
    try:
        return max(0, int(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _to_float(value: object, field_name: str) -> float:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        raise StorageLockerApiResponseError(
            f"물품보관함 API의 {field_name} 값이 숫자가 아닙니다."
        ) from None
    if not math.isfinite(number):
        raise StorageLockerApiResponseError(
            f"물품보관함 API의 {field_name} 값이 유한하지 않습니다."
        )
    return number


def _format_time(value: object) -> str | None:
    text = _text(value)
    if text is None:
        return None
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) != 6:
        return text
    return f"{digits[:2]}:{digits[2:4]}:{digits[4:]}"


def _format_hours(start: object, end: object) -> str | None:
    formatted_start = _format_time(start)
    formatted_end = _format_time(end)
    if formatted_start is None and formatted_end is None:
        return None
    return f"{formatted_start or '?'}-{formatted_end or '?'}"


def _distance_meters(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    radius = 6_371_000.0
    lat_a = math.radians(latitude_a)
    lat_b = math.radians(latitude_b)
    delta_lat = math.radians(latitude_b - latitude_a)
    delta_lng = math.radians(longitude_b - longitude_a)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a)
        * math.cos(lat_b)
        * math.sin(delta_lng / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


def _availability(row: dict) -> StorageLockerSizeAvailability:
    return StorageLockerSizeAvailability(
        large=_to_int(row.get("usePsbltyLrgszStlckCnt")),
        medium=_to_int(row.get("usePsbltyMdmszStlckCnt")),
        small=_to_int(row.get("usePsbltySmlszStlckCnt")),
    )


def _latest_by_locker(rows: list[dict]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for row in rows:
        locker_id = _text(row.get("stlckId"))
        if locker_id is None:
            continue
        previous = result.get(locker_id)
        if previous is None or str(row.get("totDt", "")) > str(
            previous.get("totDt", "")
        ):
            result[locker_id] = row
    return result


class StorageLockerService:
    DEFAULT_RESULT_LIMIT = 3

    def __init__(self, client: StorageLockerClient | None = None) -> None:
        self._client = client or StorageLockerClient()

    async def find_nearby_available(
        self,
        query: str,
        center_name: str,
        latitude: float,
        longitude: float,
        radius_meters: float = 5_000,
    ) -> NearbyStorageLockersResult:
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("중심 좌표 범위가 올바르지 않습니다.")
        if not math.isfinite(radius_meters) or radius_meters <= 0:
            raise ValueError("검색 반경은 0보다 큰 유한한 숫자여야 합니다.")

        info_rows, realtime_rows = await asyncio.gather(
            self._client.fetch_all(StorageLockerClient.INFO_PATH),
            self._client.fetch_all(StorageLockerClient.REALTIME_PATH),
        )
        realtime_by_id = _latest_by_locker(realtime_rows)
        candidates: list[StorageLockerSummary] = []

        for info in info_rows:
            locker_id = _text(info.get("stlckId"))
            realtime = realtime_by_id.get(locker_id or "")
            if locker_id is None or realtime is None:
                continue
            available_by_size = _availability(realtime)
            available_count = (
                available_by_size.large
                + available_by_size.medium
                + available_by_size.small
            )
            if available_count <= 0:
                continue
            try:
                locker_latitude = _to_float(info.get("lat"), "lat")
                locker_longitude = _to_float(info.get("lot"), "lot")
            except StorageLockerApiResponseError:
                continue
            distance = _distance_meters(
                latitude,
                longitude,
                locker_latitude,
                locker_longitude,
            )
            if distance > radius_meters:
                continue
            total_count = _to_int(info.get("stlckCnt"))
            candidates.append(
                StorageLockerSummary(
                    locker_id=locker_id,
                    name=_text(info.get("stlckRprsPstnNm")) or locker_id,
                    main_location=_text(info.get("stlckRprsPstnNm")),
                    detail_location=_text(info.get("stlckDtlPstnNm")),
                    road_address=_text(info.get("fcltRoadNmAddr")),
                    lot_number_address=_text(info.get("fcltLotnoAddr")),
                    latitude=locker_latitude,
                    longitude=locker_longitude,
                    distance_meters=round(distance, 1),
                    total_count=total_count,
                    available_count=available_count,
                    in_use_count=max(total_count - available_count, 0),
                    available_by_size=available_by_size,
                    observed_at=_text(realtime.get("totDt")),
                )
            )

        candidates.sort(key=lambda locker: locker.distance_meters)
        return NearbyStorageLockersResult(
            query=query,
            center_name=center_name,
            center_latitude=latitude,
            center_longitude=longitude,
            radius_meters=radius_meters,
            lockers=candidates[: self.DEFAULT_RESULT_LIMIT],
        )

    async def get_detail(self, locker_id: str) -> StorageLockerDetail:
        normalized_id = locker_id.strip()
        if not normalized_id:
            raise ValueError("조회할 물품보관함 ID가 필요합니다.")

        info_rows = await self._client.fetch_all(StorageLockerClient.INFO_PATH)
        info = next(
            (
                row
                for row in info_rows
                if _text(row.get("stlckId")) == normalized_id
            ),
            None,
        )
        if info is None:
            raise StorageLockerNotFoundError(
                f"물품보관함을 찾을 수 없습니다: {normalized_id}"
            )

        municipality_code = _text(info.get("stdgCd"))
        detail_rows, realtime_rows = await asyncio.gather(
            self._client.fetch_all(
                StorageLockerClient.DETAIL_PATH,
                municipality_code,
            ),
            self._client.fetch_all(
                StorageLockerClient.REALTIME_PATH,
                municipality_code,
            ),
        )
        matching_details = [
            row
            for row in detail_rows
            if _text(row.get("stlckId")) == normalized_id
        ]
        realtime = _latest_by_locker(realtime_rows).get(normalized_id)
        availability = _availability(realtime) if realtime is not None else None
        available_count = None
        if availability is not None:
            available_count = (
                availability.large + availability.medium + availability.small
            )
        total_count = _to_int(info.get("stlckCnt"))

        return StorageLockerDetail(
            locker_id=normalized_id,
            municipality_code=municipality_code,
            municipality_name=_text(info.get("lclgvNm")),
            name=_text(info.get("stlckRprsPstnNm")) or normalized_id,
            main_location=_text(info.get("stlckRprsPstnNm")),
            detail_location=_text(info.get("stlckDtlPstnNm")),
            road_address=_text(info.get("fcltRoadNmAddr")),
            lot_number_address=_text(info.get("fcltLotnoAddr")),
            latitude=_to_float(info.get("lat"), "lat"),
            longitude=_to_float(info.get("lot"), "lot"),
            total_count=total_count,
            available_count=available_count,
            in_use_count=(
                max(total_count - available_count, 0)
                if available_count is not None
                else None
            ),
            available_by_size=availability,
            observed_at=_text(realtime.get("totDt")) if realtime else None,
            weekday_hours=_format_hours(
                info.get("wkdyOperBgngTm"), info.get("wkdyOperEndTm")
            ),
            saturday_hours=_format_hours(
                info.get("satOperBgngTm"), info.get("satOperEndTm")
            ),
            holiday_hours=_format_hours(
                info.get("lhldyOperBgngTm"), info.get("lhldyOperEndTm")
            ),
            free_usage_time=_format_time(info.get("freeUtztnHr")),
            installed_on=_text(info.get("instlYmd")),
            customer_center_phone=_text(info.get("custCntrTelno")),
            managing_organization=_text(info.get("mngInstNm")),
            managing_organization_phone=_text(info.get("mngInstTelno")),
            compartments=[_build_compartment(row) for row in matching_details],
        )


def _build_compartment(row: dict) -> StorageLockerCompartmentDetail:
    return StorageLockerCompartmentDetail(
        detail_id=_text(row.get("stlckDtlId")),
        kind=_text(row.get("stlckKndNm")),
        name=_text(row.get("stlckNm")),
        width=_text(row.get("stlckWdthLenExpln")),
        depth=_text(row.get("stlckDpthExpln")),
        height=_text(row.get("stlckHgtExpln")),
        fee=_text(row.get("utztnCrgExpln")),
        payment_method=_text(row.get("stlmMnsNm")),
        additional_fee_unit_time=_format_time(row.get("addCrgUnitHr")),
        additional_fee=_text(row.get("addCrgExpln")),
        control_method=_text(row.get("cntrlMthSeNm")),
        usage_method=_text(row.get("useMthdExpln")),
        restricted_items=_text(row.get("kpngLmtCmdtyExpln")),
    )
