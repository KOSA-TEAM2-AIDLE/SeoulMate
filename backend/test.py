import asyncio

from services.congestion import CongestionService


async def main():
    service = CongestionService()
    snapshot = await service.get_congestion("POI009")

    print(snapshot.model_dump(mode="json"))


asyncio.run(main())