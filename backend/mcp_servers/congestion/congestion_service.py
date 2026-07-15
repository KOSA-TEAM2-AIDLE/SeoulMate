class CongestionService:
    implemented = False

    async def get_context(self, area_code: str, target_time: str | None = None):
        raise NotImplementedError
