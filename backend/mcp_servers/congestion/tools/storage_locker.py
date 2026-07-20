from mcp.server.fastmcp import FastMCP

from services.kakao_local import KakaoLocalServiceError
from services.place_resolver import PlaceResolver
from services.storage_lockers import (
    StorageLockerNotFoundError,
    StorageLockerService,
    StorageLockerServiceError,
)


def register_storage_locker_tools(
    mcp: FastMCP,
    resolver: PlaceResolver,
    service: StorageLockerService,
) -> None:
    @mcp.tool()
    async def find_nearby_available_storage_lockers(
        location: str,
        radius_meters: float = 5_000,
    ) -> dict:
        """장소 반경 내에서 현재 사용 가능한 물품보관함을 최대 3개 반환한다."""
        try:
            resolution = await resolver.resolve(query=location)
            if resolution.selected is None:
                if resolution.candidates:
                    names = ", ".join(
                        candidate.place_name
                        for candidate in resolution.candidates[:5]
                    )
                    raise ValueError(
                        "장소를 하나로 특정할 수 없습니다. 더 구체적으로 "
                        f"입력해 주세요. 후보: {names}"
                    )
                raise ValueError(
                    f"서울에서 장소를 찾을 수 없습니다: {location}"
                )
            selected = resolution.selected
            result = await service.find_nearby_available(
                query=location,
                center_name=selected.place_name,
                latitude=selected.latitude,
                longitude=selected.longitude,
                radius_meters=radius_meters,
            )
        except ValueError:
            raise
        except KakaoLocalServiceError as error:
            raise RuntimeError(str(error)) from None
        except StorageLockerServiceError as error:
            raise RuntimeError(str(error)) from None
        return result.model_dump(mode="json")

    @mcp.tool()
    async def get_storage_locker_detail(locker_id: str) -> dict:
        """물품보관함 ID로 위치, 운영시간, 잔여 수량과 요금을 반환한다."""
        try:
            result = await service.get_detail(locker_id)
        except ValueError:
            raise
        except StorageLockerNotFoundError as error:
            raise ValueError(str(error)) from None
        except StorageLockerServiceError as error:
            raise RuntimeError(str(error)) from None
        return result.model_dump(mode="json")


__all__ = ["register_storage_locker_tools"]
