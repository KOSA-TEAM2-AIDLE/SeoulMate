import asyncio
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.runnables import RunnableLambda
from langgraph.types import Command

from application.travel_query.graph import (
    build_initial_state,
    build_travel_query_graph,
)


SEOUL_TIMEZONE = ZoneInfo("Asia/Seoul")
REFERENCE_AT = datetime(2026, 7, 15, 12, 0, tzinfo=SEOUL_TIMEZONE)


def _day_route_extraction(inputs: dict) -> dict:
    latest_answer = inputs["latest_user_answer"]
    result = {
        "language": "ko",
        "intent": "day_trip_route",
        "normalized_question": "2026-07-16 홍대 하루 코스",
        "location": "홍대",
        "start_date": "2026-07-16",
    }
    if latest_answer != "none":
        result.update(
            {
                "pace": "normal",
                "target_places_per_day": 4,
            }
        )
    return result


async def _run_hitl_scenario() -> tuple[dict, dict]:
    graph = build_travel_query_graph(RunnableLambda(_day_route_extraction))
    config = {"configurable": {"thread_id": "travel-thread-1"}}
    initial = build_initial_state(
        "내일 홍대 하루 코스 짜줘",
        REFERENCE_AT,
    )

    interrupted = await graph.ainvoke(initial, config=config)
    resumed = await graph.ainvoke(Command(resume="보통"), config=config)
    return interrupted, resumed


class TravelQueryGraphTests(unittest.TestCase):
    def test_interrupt_and_command_resume_continue_same_thread(self) -> None:
        interrupted, resumed = asyncio.run(_run_hitl_scenario())

        self.assertIn("__interrupt__", interrupted)
        interrupt_payload = interrupted["__interrupt__"][0].value
        self.assertEqual("collecting", interrupt_payload["status"])
        self.assertEqual(
            ["route_request.target_places_per_day"],
            interrupt_payload["missing_fields"],
        )

        self.assertEqual("building", resumed["status"])
        self.assertEqual(4, resumed["collected"]["target_places_per_day"])
        self.assertEqual("normal", resumed["collected"]["pace"])
        self.assertEqual(2, len(resumed["conversation_history"]))
        self.assertEqual(
            "보통",
            resumed["conversation_history"][-1]["content"],
        )

    def test_modify_route_finishes_without_interrupt(self) -> None:
        chain = RunnableLambda(
            lambda _: {
                "language": "ko",
                "intent": "modify_route",
                "normalized_question": "첫날 카페 슬롯 교체",
            }
        )
        graph = build_travel_query_graph(chain)
        state = build_initial_state(
            "첫날 카페를 다른 곳으로 바꿔줘",
            REFERENCE_AT,
        )

        result = asyncio.run(
            graph.ainvoke(
                state,
                config={"configurable": {"thread_id": "unsupported-1"}},
            )
        )

        self.assertNotIn("__interrupt__", result)
        self.assertEqual("unsupported", result["status"])
        self.assertEqual(
            "루트 수정은 지원하지 않습니다.",
            result["assistant_message"],
        )

    def test_initial_state_requires_aware_reference_time(self) -> None:
        with self.assertRaisesRegex(ValueError, "시간대"):
            build_initial_state(
                "홍대 카페 추천",
                datetime(2026, 7, 15, 12, 0),
            )


if __name__ == "__main__":
    unittest.main()
