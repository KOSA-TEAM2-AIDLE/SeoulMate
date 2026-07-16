# Attraction Vector Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide a tested pgvector search component that turns a normalized attraction request into active place and review evidence.

**Architecture:** `AttractionVectorSearch` builds a text query from `DomainSearchRequest`, embeds it with the existing embedder, and calls `AttractionVectorRepository` for profile and review matches. Database reads apply language, kind, and event-end-date rules before search results are merged by `place_key`.

**Tech Stack:** Python 3.12, psycopg2, PostgreSQL/pgvector, OpenAI embeddings, unittest.

## Global Constraints

- Reuse `text-embedding-3-large` with the configured 1536 dimensions.
- Preserve `search_query` and append only explicit structured constraints.
- Exclude only events whose non-empty `end_date` precedes `visit_date` (or today); retain blank end dates.
- Do not wire `/chat`, the attraction domain service, or DSPy in this phase.

---

### Task 1: Query-text builder and vector result contract

**Files:**
- Create: `backend/vector_db/attraction/search.py`
- Test: `backend/tests/attraction/test_vector_search.py`

- [x] Write failing tests for raw query retention, structured theme/location/date additions, and absent-value omission.
- [x] Run `uv run python -m unittest tests.attraction.test_vector_search -v`; import failed because `vector_db.attraction.search` did not exist.
- [x] Implement `AttractionVectorSearch.build_query_text(request) -> str` and immutable result records.
- [x] Re-run the test; PASS.

### Task 2: Repository similarity reads

**Files:**
- Modify: `backend/vector_db/attraction/repository.py`
- Test: `backend/tests/attraction/test_vector_store.py`

- [x] Write failing recording-cursor tests that assert profile SQL filters selected language, `kind IN ('attraction', 'event')`, and non-expired events while allowing blank event end dates; assert reviews are filtered by supplied `place_key` values and `kind='review'`.
- [x] Run `uv run python -m unittest tests.attraction.test_vector_store -v`; methods were absent.
- [x] Implement `search_profiles` and `search_reviews` with parameterized `%s::vector` cosine-distance SQL and bounded limits.
- [x] Re-run the test; PASS.

### Task 3: Search orchestration and evidence merge

**Files:**
- Modify: `backend/vector_db/attraction/search.py`
- Test: `backend/tests/attraction/test_vector_search.py`

- [x] Write failing tests with injected embedder/repository fakes: embed once, no expired event hit, same-place reviews only, and `candidate_count` enforcement.
- [x] Run `uv run python -m unittest tests.attraction.test_vector_search -v`; search constructor was absent.
- [x] Implement `search(request) -> list[VectorSearchHit]`, over-fetch profiles by three times the requested count, and attach up to three review excerpts per selected profile.
- [x] Run `uv run python -m unittest discover -s tests/attraction -v`; 15 tests passed.

### Task 4: Local database verification

- [x] Run the attraction test suite.
- [x] Run one read-only Korean smoke query against the configured local pgvector database.
- [x] Confirm returned events are active for the request date, query vectors are 1536-dimensional, and reviews match their profile `place_key`.
