import math

import httpx
from pydantic import ValidationError

from core.config import Settings, settings
from schemas.location import KakaoPlaceDocument


class KakaoLocalServiceError(Exception):
    """Kakao Local API에서 발생하는 모든 오류의 부모 클래스."""


class KakaoApiKeyMissingError(KakaoLocalServiceError):
    """Kakao REST API 키가 없거나 비어 있을 때 발생."""


class KakaoLocalRequestError(KakaoLocalServiceError):
    """Kakao Local API 연결, timeout, HTTP 요청 실패 시 발생."""


class KakaoLocalResponseError(KakaoLocalServiceError):
    """Kakao Local API 응답 구조가 올바르지 않을 때 발생."""


class KakaoLocalClient:
    KEYWORD_SEARCH_PATH = "/v2/local/search/keyword.json"
    MAX_RESULT_LIMIT = 15
    MAX_RADIUS_METERS = 20_000

    def __init__(
        self,
        config: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config or settings
        self._http_client = http_client

    def _get_api_key(self) -> str:
        secret = self._config.kakao_rest_api_key
        if secret is None:
            raise KakaoApiKeyMissingError(
                "KAKAO_REST_API_KEY가 설정되지 않았습니다."
            )

        api_key = secret.get_secret_value().strip()
        if not api_key:
            raise KakaoApiKeyMissingError(
                "KAKAO_REST_API_KEY가 비어 있습니다."
            )
        return api_key

    @staticmethod
    def _validate_coordinate(value: float, name: str) -> float:
        try:
            coordinate = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name}은 숫자여야 합니다.") from None

        if not math.isfinite(coordinate):
            raise ValueError(f"{name}은 유한한 숫자여야 합니다.")
        return coordinate

    def _build_params(
        self,
        query: str,
        center_latitude: float | None,
        center_longitude: float | None,
        radius_meters: int | None,
        limit: int | None,
    ) -> dict[str, str | int | float]:
        normalized_query = str(query).strip()
        if not normalized_query:
            raise ValueError("검색할 장소명이 필요합니다.")

        selected_limit = (
            self._config.kakao_place_result_limit
            if limit is None
            else limit
        )
        if (
            isinstance(selected_limit, bool)
            or not isinstance(selected_limit, int)
            or not 1 <= selected_limit <= self.MAX_RESULT_LIMIT
        ):
            raise ValueError("검색 결과 수는 1~15 사이의 정수여야 합니다.")

        has_latitude = center_latitude is not None
        has_longitude = center_longitude is not None
        if has_latitude != has_longitude:
            raise ValueError(
                "center_latitude와 center_longitude는 함께 입력해야 합니다."
            )
        if radius_meters is not None and not has_latitude:
            raise ValueError("검색 반경을 사용하려면 중심 좌표가 필요합니다.")

        params: dict[str, str | int | float] = {
            "query": normalized_query,
            "size": selected_limit,
        }

        if has_latitude and has_longitude:
            latitude = self._validate_coordinate(
                center_latitude,
                "center_latitude",
            )
            longitude = self._validate_coordinate(
                center_longitude,
                "center_longitude",
            )
            if not -90 <= latitude <= 90:
                raise ValueError("center_latitude 범위가 올바르지 않습니다.")
            if not -180 <= longitude <= 180:
                raise ValueError("center_longitude 범위가 올바르지 않습니다.")

            params.update(
                {
                    "x": longitude,
                    "y": latitude,
                    "sort": "distance",
                }
            )

            if radius_meters is not None:
                if (
                    isinstance(radius_meters, bool)
                    or not isinstance(radius_meters, int)
                    or not 0 <= radius_meters <= self.MAX_RADIUS_METERS
                ):
                    raise ValueError(
                        "검색 반경은 0~20000 사이의 정수여야 합니다."
                    )
                params["radius"] = radius_meters

        return params

    async def search_places(
        self,
        query: str,
        center_latitude: float | None = None,
        center_longitude: float | None = None,
        radius_meters: int | None = None,
        limit: int | None = None,
    ) -> list[KakaoPlaceDocument]:
        params = self._build_params(
            query=query,
            center_latitude=center_latitude,
            center_longitude=center_longitude,
            radius_meters=radius_meters,
            limit=limit,
        )
        headers = {
            "Authorization": f"KakaoAK {self._get_api_key()}",
            "Accept": "application/json",
        }
        url = (
            f"{self._config.kakao_local_api_base_url}"
            f"{self.KEYWORD_SEARCH_PATH}"
        )

        try:
            if self._http_client is not None:
                response = await self._http_client.get(
                    url,
                    headers=headers,
                    params=params,
                )
            else:
                async with httpx.AsyncClient(
                    timeout=self._config.kakao_local_api_timeout_seconds,
                ) as client:
                    response = await client.get(
                        url,
                        headers=headers,
                        params=params,
                    )
            response.raise_for_status()
        except httpx.TimeoutException:
            raise KakaoLocalRequestError(
                "Kakao Local API 요청 시간이 초과되었습니다."
            ) from None
        except httpx.HTTPStatusError as error:
            raise KakaoLocalRequestError(
                "Kakao Local API가 HTTP 오류를 반환했습니다: "
                f"status={error.response.status_code}"
            ) from None
        except httpx.RequestError:
            raise KakaoLocalRequestError(
                "Kakao Local API에 연결할 수 없습니다."
            ) from None

        try:
            payload = response.json()
        except ValueError:
            raise KakaoLocalResponseError(
                "Kakao Local API 응답을 JSON으로 해석할 수 없습니다."
            ) from None

        documents = payload.get("documents") if isinstance(payload, dict) else None
        if not isinstance(documents, list):
            raise KakaoLocalResponseError(
                "Kakao Local API 응답에 documents 목록이 없습니다."
            )

        try:
            return [
                KakaoPlaceDocument.model_validate(document)
                for document in documents
            ]
        except ValidationError:
            raise KakaoLocalResponseError(
                "Kakao Local API 장소 응답 구조가 예상과 다릅니다."
            ) from None
