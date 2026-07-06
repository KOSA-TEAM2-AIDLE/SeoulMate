"""API 명세서 8장 참고. 실시간 잔여 칸 API 없음: locker_count는 전체 보관함 수."""
from pydantic import BaseModel


class StorageLocker(BaseModel):
    id: int
    main_location: str
    detail_location: str
    locker_count: int
    road_address: str
    jibun_address: str
    lat: float
    lng: float
    hours: str
    description: str
    fee: str
    payment_method: str
    overtime_unit: str
