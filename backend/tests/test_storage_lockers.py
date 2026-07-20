import unittest

from services.storage_lockers import StorageLockerClient, StorageLockerService


class FakeStorageLockerClient:
    def __init__(self) -> None:
        self.info = [
            {
                "stdgCd": "1150000000",
                "lclgvNm": "서울특별시",
                "stlckId": "A",
                "stlckRprsPstnNm": "가까운 보관함",
                "stlckDtlPstnNm": "역 1번 출구",
                "stlckCnt": "10",
                "lat": "37.5000",
                "lot": "127.0000",
                "wkdyOperBgngTm": "050000",
                "wkdyOperEndTm": "010000",
            },
            {
                "stdgCd": "1150000000",
                "stlckId": "B",
                "stlckRprsPstnNm": "빈자리 없는 보관함",
                "stlckCnt": "4",
                "lat": "37.5001",
                "lot": "127.0000",
            },
            {
                "stdgCd": "1150000000",
                "stlckId": "C",
                "stlckRprsPstnNm": "두 번째 보관함",
                "stlckCnt": "8",
                "lat": "37.5010",
                "lot": "127.0000",
            },
            {
                "stdgCd": "1150000000",
                "stlckId": "D",
                "stlckRprsPstnNm": "세 번째 보관함",
                "stlckCnt": "6",
                "lat": "37.5020",
                "lot": "127.0000",
            },
            {
                "stdgCd": "1150000000",
                "stlckId": "E",
                "stlckRprsPstnNm": "네 번째 보관함",
                "stlckCnt": "6",
                "lat": "37.5030",
                "lot": "127.0000",
            },
        ]
        self.realtime = [
            {
                "stlckId": "A",
                "totDt": "20260715120000",
                "usePsbltyLrgszStlckCnt": "1",
                "usePsbltyMdmszStlckCnt": "2",
                "usePsbltySmlszStlckCnt": "3",
            },
            {
                "stlckId": "B",
                "totDt": "20260715120000",
                "usePsbltyLrgszStlckCnt": "0",
                "usePsbltyMdmszStlckCnt": "0",
                "usePsbltySmlszStlckCnt": "0",
            },
            *[
                {
                    "stlckId": locker_id,
                    "totDt": "20260715120000",
                    "usePsbltyLrgszStlckCnt": "1",
                    "usePsbltyMdmszStlckCnt": "0",
                    "usePsbltySmlszStlckCnt": "0",
                }
                for locker_id in ("C", "D", "E")
            ],
        ]
        self.details = [
            {
                "stlckId": "A",
                "stlckDtlId": "A_LARGE",
                "stlckKndNm": "대형",
                "stlckNm": "대형 보관함",
                "utztnCrgExpln": "2,000원",
                "stlmMnsNm": "카드",
                "addCrgUnitHr": "010000",
            }
        ]

    async def fetch_all(
        self,
        path: str,
        municipality_code: str | None = None,
    ) -> list[dict]:
        if path == StorageLockerClient.INFO_PATH:
            return self.info
        if path == StorageLockerClient.REALTIME_PATH:
            return self.realtime
        if path == StorageLockerClient.DETAIL_PATH:
            return self.details
        raise AssertionError(path)


class StorageLockerServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.service = StorageLockerService(FakeStorageLockerClient())

    async def test_nearby_returns_three_available_lockers_by_distance(self) -> None:
        result = await self.service.find_nearby_available(
            query="테스트역",
            center_name="테스트역",
            latitude=37.5,
            longitude=127.0,
            radius_meters=1_000,
        )

        self.assertEqual(["A", "C", "D"], [row.locker_id for row in result.lockers])
        self.assertEqual(6, result.lockers[0].available_count)
        self.assertEqual(4, result.lockers[0].in_use_count)

    async def test_detail_merges_basic_realtime_and_compartment_data(self) -> None:
        detail = await self.service.get_detail("A")

        self.assertEqual(10, detail.total_count)
        self.assertEqual(6, detail.available_count)
        self.assertEqual(4, detail.in_use_count)
        self.assertEqual("05:00:00-01:00:00", detail.weekday_hours)
        self.assertEqual("대형", detail.compartments[0].kind)
        self.assertEqual("01:00:00", detail.compartments[0].additional_fee_unit_time)


if __name__ == "__main__":
    unittest.main()
