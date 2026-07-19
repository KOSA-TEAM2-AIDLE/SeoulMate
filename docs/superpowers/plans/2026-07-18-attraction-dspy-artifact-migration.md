# Attraction DSPy Artifact Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single tourism DSPy artifact with separately optimized selection and structured-answer artifacts without changing the `/chat` response contract.

**Architecture:** Preserve `/chat → select_grouped_candidates → AttractionSelectionService`. The service validates selection, passes only selected evidence to the answer program, validates its structured output, and adapts it to `CandidateSelectionResult`. Route-slot tourism is excluded.

**Tech Stack:** Python, DSPy 3.2.1, Pydantic, FastAPI, unittest, JSON artifacts.

## Global Constraints

- Do not change TravelQuery, HITL, search services, or `Place`/SSE contracts.
- Apply only to single attraction recommendations and attraction tasks in mixed recommendations.
- Do not apply the new programs to tourism route slots.
- Any artifact load, model-call, or validation failure returns the existing safe fallback.
- Train uses train only; dev chooses prompts; test and gold test are evaluation-only.

---

### Task 1: Lock the live chat integration boundary

**Files:**
- Modify: `backend/tests/test_group_selection.py`
- Create: `backend/tests/test_attraction_dspy_chat_integration.py`

**Produces:** Tests proving an attraction selector's `answer` and `selection_reason` appear in the grouped chat result, and tests proving route slots do not use that selector.

- [ ] Write a failing test with a fake attraction selector returning `answer="DSPy answer"` and `selection_reason="DSPy reason"`.
- [ ] Run: `cd backend && uv run python -m unittest tests.test_group_selection tests.test_attraction_dspy_chat_integration -v`. Expected: the new test fails before its seam exists.
- [ ] Add the minimal injection seam required to run the chat path with the fake selector; do not change the production result schema.
- [ ] Re-run the command. Expected: PASS.
- [ ] Commit: `git commit -m "test: lock attraction DSPy chat integration boundary"`.

### Task 2: Define lossless DSPy evidence and output contracts

**Files:**
- Modify: `backend/domains/attraction/answer_models.py`
- Modify: `backend/domains/attraction/answer_evidence.py`
- Create: `backend/domains/attraction/dspy/contracts.py`
- Test: `backend/tests/test_attraction_answer_contract.py`

**Produces:** Typed congestion/weather evidence preserving availability, value, basis, and observed time; typed selection and structured-answer output contracts.

- [ ] Write failing tests asserting available congestion preserves `basis` and `observed_at`, while unavailable weather has `value is None`.
- [ ] Run: `cd backend && uv run python -m unittest tests.test_attraction_answer_contract -v`. Expected: FAIL because the current model stores context as a string.
- [ ] Implement `ContextEvidence`, `SelectionPrediction`, and `StructuredAnswer` Pydantic models. Update `build_attraction_answer_input()` to preserve context fields and existing 10-candidate/5-review limits.
- [ ] Re-run the contract suite. Expected: PASS.
- [ ] Commit: `git commit -m "feat: add structured attraction DSPy evidence contracts"`.

### Task 3: Implement separate selection and answer programs

**Files:**
- Create: `backend/domains/attraction/dspy/signatures.py`
- Create: `backend/domains/attraction/dspy/programs.py`
- Create: `backend/domains/attraction/dspy/validator.py`
- Test: `backend/tests/test_attraction_dspy_contracts.py`
- Test: `backend/tests/test_attraction_dspy_validator.py`

**Produces:** A selection program, an answer program, and deterministic hard-failure validation.

- [ ] Write failing tests for unknown IDs, duplicate IDs, excluded/conflict IDs, ended events, unsupported reviews/facts, unavailable context values, and wrong language.
- [ ] Run: `cd backend && uv run python -m unittest tests.test_attraction_dspy_contracts tests.test_attraction_dspy_validator -v`. Expected: FAIL because the modules do not exist.
- [ ] Implement `TourismSelectionProgram` and `TourismAnswerProgram`. Selection receives all candidates; answer receives only validator-approved selected candidates.
- [ ] Implement validators that reject every listed hard failure rather than repairing model output.
- [ ] Re-run focused tests. Expected: PASS.
- [ ] Commit: `git commit -m "feat: split attraction DSPy selection and answer programs"`.

### Task 4: Replace the runtime artifact loader behind the existing service

**Files:**
- Create: `backend/domains/attraction/dspy/renderer.py`
- Create: `backend/domains/attraction/dspy/service.py`
- Modify: `backend/domains/attraction/selection_service.py`
- Test: `backend/tests/test_attraction_dspy_renderer.py`
- Test: `backend/tests/test_attraction_dspy_service.py`

**Produces:** The unchanged `CandidateSelectionResult(answer, selections, used_fallback)` interface from two artifacts.

- [ ] Write failing tests that map a structured answer to existing selections and exercise fallback when either artifact cannot load.
- [ ] Run: `cd backend && uv run python -m unittest tests.test_attraction_dspy_renderer tests.test_attraction_dspy_service -v`. Expected: FAIL because the runtime modules do not exist.
- [ ] Load `selection_v1.json`, `answer_v1.json`, and metadata together. Run selection → validate → answer → validate → renderer. Return the current ranked fallback on any failure.
- [ ] Delegate `AttractionSelectionService.select()` to this runtime while preserving its public method signature.
- [ ] Re-run focused tests plus `tests.test_group_selection`. Expected: PASS.
- [ ] Commit: `git commit -m "feat: use split DSPy artifacts for attraction selection"`.

### Task 5: Build offline datasets, evaluation, and versioned exports

**Files:**
- Modify: `backend/experiments/attraction_dspy/dataset.py`
- Modify: `backend/experiments/attraction_dspy/metrics.py`
- Modify: `backend/experiments/attraction_dspy/optimize.py`
- Modify: `backend/experiments/attraction_dspy/evaluate.py`
- Create: `backend/experiments/attraction_dspy/export_artifact.py`
- Test: `backend/tests/test_attraction_dspy_dataset.py`
- Test: `backend/tests/experiments/attraction_dspy/test_metrics.py`

**Produces:** Leakage-checked split loaders, separate metrics, evaluation reports, two versioned artifacts, and metadata.

- [ ] Write failing tests proving train/dev/test/gold IDs are disjoint and exported artifacts load into new program instances.
- [ ] Run focused dataset/metric tests. Expected: FAIL until the declared `data/attraction/DSPy` layout is supported.
- [ ] Implement separate selection/answer loaders and metrics. MIPROv2 uses train and dev only; test/gold are never passed to compile.
- [ ] Export `selection_v1.json`, `answer_v1.json`, and metadata containing DSPy version, model, optimizer, dataset fingerprint, timestamp, metrics, hard failures, and Git revision.
- [ ] Run `cd backend && uv run python -m experiments.attraction_dspy.optimize --dry-run`. Expected: no LLM call and separate program plan.
- [ ] Commit: `git commit -m "feat: export versioned attraction DSPy artifacts"`.

### Task 6: Verify release scope

**Files:**
- Modify: `backend/tests/test_attraction_dspy_chat_integration.py`
- Modify: `backend/tests/test_attraction_answer_generator.py`
- Modify: `backend/domains/attraction/dspy/AGENTS.md`

**Produces:** Proof that the new artifacts serve single/mixed attraction chat requests and never serve route slots.

- [ ] Add tests for one single-attraction chat request, one mixed-domain chat request, and one route request.
- [ ] Run: `cd backend && uv run python -m unittest tests.test_attraction_answer_contract tests.test_attraction_answer_generator tests.test_attraction_dspy_chat_integration tests.test_group_selection -v`. Expected: PASS.
- [ ] Run: `cd backend && uv run python -m unittest discover -s tests -v`. Expected: PASS.
- [ ] Add actual version, dataset fingerprint, Dev/Test/Gold metrics, hard-failure counts, and rollback artifact path to `AGENTS.md`; never record secrets or private labels.
- [ ] Commit: `git commit -m "test: verify attraction DSPy artifact migration"`.

## Self-Review

- Tasks 1–4 cover the live chat runtime and safe fallback.
- Task 5 covers offline optimization, leakage prevention, and artifact export.
- Task 6 verifies both in-scope requests and the route-slot exclusion.

