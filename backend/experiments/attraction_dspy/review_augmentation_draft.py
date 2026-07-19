"""Fact-check pending augmentation cases against the live SeoulMate attraction DB."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import dspy
import psycopg2

from core.config import DB_CONFIG, settings


ROOT = Path(__file__).parents[2] / "data" / "attraction" / "DSPy" / "augmentation_draft"


def source_cid_matches_place_id(source_cid: str, place_id: str) -> bool:
    """DB source IDs may add a provider prefix such as `KOP` to a candidate ID."""

    return source_cid == place_id or source_cid.endswith(place_id)


class DatabaseFactCheckSignature(dspy.Signature):
    """Approve only questions whose expected candidate is uniquely supported by DB evidence."""

    language: str = dspy.InputField()
    question: str = dspy.InputField()
    expected_place_ids_json: str = dspy.InputField()
    candidates_db_evidence_json: str = dspy.InputField()
    decision_json: str = dspy.OutputField(
        desc='JSON only: {"decision":"reviewed"|"needs_revision", "reason":"short factual reason"}. '
        "Use only supplied DB evidence. Approve only when the expected selection is supported and distinguishable."
    )


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_db_evidence(place_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    patterns = [f"%{place_id}" for place_id in place_ids]
    evidence: dict[str, list[dict[str, Any]]] = {place_id: [] for place_id in place_ids}
    with psycopg2.connect(**DB_CONFIG) as connection:
        connection.set_session(readonly=True)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT source_cid, name, summary, description
                FROM attraction_ko
                WHERE source_cid LIKE ANY(%s)
                UNION ALL
                SELECT source_cid, name, summary, description
                FROM attraction_en
                WHERE source_cid LIKE ANY(%s)
                """,
                (patterns, patterns),
            )
            for source_cid, name, summary, description in cursor.fetchall():
                for place_id in place_ids:
                    if source_cid_matches_place_id(str(source_cid), place_id):
                        evidence[place_id].append({
                            "source_cid": source_cid,
                            "name": name,
                            "summary": summary or "",
                            "description": description or "",
                        })
            cursor.execute(
                """
                SELECT a.source_cid, r.content
                FROM attraction_review_ko r JOIN attraction_ko a ON a.id = r.attraction_id
                WHERE a.source_cid LIKE ANY(%s)
                UNION ALL
                SELECT a.source_cid, r.content
                FROM attraction_review_en r JOIN attraction_en a ON a.id = r.attraction_id
                WHERE a.source_cid LIKE ANY(%s)
                """,
                (patterns, patterns),
            )
            reviews: dict[str, list[str]] = {place_id: [] for place_id in place_ids}
            for source_cid, content in cursor.fetchall():
                for place_id in place_ids:
                    if source_cid_matches_place_id(str(source_cid), place_id) and content:
                        reviews[place_id].append(str(content))
    for place_id, records in evidence.items():
        for record in records:
            record["reviews"] = reviews[place_id][:5]
    return evidence


def _decision(prediction: Any) -> tuple[str, str]:
    try:
        payload = json.loads(prediction.decision_json)
    except (AttributeError, TypeError, json.JSONDecodeError):
        return "needs_revision", "DB evidence judge did not return valid JSON."
    decision = payload.get("decision")
    if decision not in {"reviewed", "needs_revision"}:
        return "needs_revision", "DB evidence judge returned an invalid decision."
    return decision, str(payload.get("reason") or "No reason supplied.")


def main() -> int:
    path = ROOT / "augmentation_draft.jsonl"
    rows = _rows(path)
    key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 필요합니다.")
    lm = dspy.LM(settings.attraction_dspy_model, api_key=key, temperature=0, max_tokens=180)
    report: list[dict[str, Any]] = []
    with dspy.context(lm=lm):
        judge = dspy.Predict(DatabaseFactCheckSignature)
        for row in rows:
            candidates = row["input"]["candidates"]
            place_ids = [candidate["place_id"] for candidate in candidates]
            evidence = _load_db_evidence(place_ids)
            missing = [place_id for place_id, records in evidence.items() if not records]
            expected = row["expected"]["selected_place_ids"]
            if missing:
                decision, reason = "needs_revision", f"DB 장소 원문 없음: {', '.join(missing)}"
            elif not expected:
                decision, reason = "reviewed", "All candidates exist in DB and each has an explicit conflict constraint."
            else:
                prediction = judge(
                    language=row["input"]["language"], question=row["input"]["question"],
                    expected_place_ids_json=json.dumps(expected, ensure_ascii=False),
                    candidates_db_evidence_json=json.dumps(evidence, ensure_ascii=False),
                )
                decision, reason = _decision(prediction)
            row["review_status"] = decision
            row["review_notes"] = f"DB fact check ({decision}): {reason}"
            row["metadata"]["db_fact_check"] = {
                "database": "seoulmate", "candidate_count": len(place_ids),
                "matched_candidate_count": len(place_ids) - len(missing), "decision": decision,
            }
            report.append({
                "example_id": row["example_id"], "decision": decision, "reason": reason,
                "matched_place_ids": sorted(place_id for place_id, records in evidence.items() if records),
                "missing_place_ids": missing,
            })
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    (ROOT / "DB_FACT_CHECK_REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
