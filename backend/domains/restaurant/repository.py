"""식당 PostgreSQL repository 경계.

현재 SQL은 회귀 위험을 줄이기 위해 ``services.rag`` 내부에 유지한다. 팀이 SQL을
분리할 때 이 클래스의 메서드 단위로 옮기면 search service 계약은 바뀌지 않는다.
"""


class RestaurantRepository:
    implemented = True

    def __init__(self) -> None:
        self.migration_note = "SQL implementation currently lives in services.rag"


__all__ = ["RestaurantRepository"]

