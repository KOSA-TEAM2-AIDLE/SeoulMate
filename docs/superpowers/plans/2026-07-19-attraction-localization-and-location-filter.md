# Attraction Localization and Location Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep attraction recommendations in the requested area and present one localized, natural recommendation explanation consistently in chat and the sidebar.

**Architecture:** The attraction search service resolves an explicit location before invoking its reranker. The reranker keeps its coordinate-radius behavior and adds the existing shared district-address predicate. The DSPy renderer creates one per-place prose paragraph for both the chat answer and `selection_reason`; the frontend only localizes fixed display labels.

**Tech Stack:** Python 3, unittest, Pydantic, React 19, Node built-in test runner.

## Global Constraints

- Change attraction search, attraction DSPy rendering, and display-only frontend code only.
- Do not change restaurant, cafe, or accommodation search/recommendation logic or their API contracts.
- Reuse `services.location.address_matches_search_area()`.
- Use `DomainSearchRequest.language` as the attraction locale source.
- Show observation time as `YYYY-MM-DD HH:mm`; omit unparseable values.

---

### Task 1: Enforce explicit attraction search areas

**Files:**
- Modify: `backend/domains/attraction/search_service.py`
- Modify: `backend/domains/attraction/reranker.py`
- Modify: `backend/tests/test_attraction_search_service.py`

**Interfaces:**
- Consumes: `DomainSearchRequest.location`, `latitude`, `longitude`, and `radius_km`.
- Produces: `AttractionReranker.rerank(retrieval, *, plan, required_features, excluded_features, min_rating, as_of, limit, search_location: str | None = None)`.

- [ ] **Step 1: Write failing regression tests**

```python
def test_reranker_removes_conflicting_district_candidate(self):
    ranked = AttractionReranker().rerank(
        retrieval_with_records(
            record("gyeongbokgung", "서울 종로구 사직로 161", 37.5796, 126.9770),
            record("lotte-world", "서울 송파구 올림픽로 240", 37.5110, 127.0980),
        ),
        plan=AttractionSearchPlan(
            query_text="경복궁 근처 명소", language="ko", primary_categories=(),
            secondary_categories=(), event_only=False, latitude=37.5796,
            longitude=126.9770, radius_km=30,
        ),
        required_features=[], excluded_features=[], min_rating=None,
        as_of=date(2026, 7, 19), limit=10, search_location="경복궁",
    )
    self.assertEqual(["gyeongbokgung"], [item.attraction.id for item in ranked])

def test_explicit_location_uses_geocoded_coordinates_without_client_coordinates(self):
    service = AttractionSearchService(repository=fake_repository, geocoder=lambda _: (37.5796, 126.9770, "경복궁"))
    await service.search(DomainSearchRequest(
        task_id="task-1", domain="attraction", language="ko",
        search_query="경복궁 근처 명소", location="경복궁", radius_km=3,
    ))
    self.assertEqual((37.5796, 126.9770), fake_repository.last_rerank_plan_coordinates)
```

- [ ] **Step 2: Confirm the tests fail before implementation**

Run: `cd backend && .venv/bin/python -m unittest tests.test_attraction_search_service -v`

Expected: FAIL because `rerank()` has no `search_location` argument and does not apply a district predicate.

- [ ] **Step 3: Implement the minimal filter**

```python
# search_service.py
resolved_location = request.location
if should_geocode_location(request):
    geocoded = self.geocoder(request.location)
    if geocoded:
        latitude, longitude, resolved_location = geocoded
effective_request = request.model_copy(update={"latitude": latitude, "longitude": longitude})
ranked = self.reranker.rerank(
    retrieval, plan=build_attraction_search_plan(effective_request),
    required_features=request.required_features,
    excluded_features=request.excluded_features,
    min_rating=request.min_rating, as_of=as_of,
    limit=request.candidate_count, search_location=resolved_location,
)

# reranker.py
from services.location import address_matches_search_area, haversine_km

if search_location and not address_matches_search_area(search_location, record.address):
    continue
```

Keep the existing default radius behavior: `plan.radius_km or DEFAULT_RADIUS_KM`.

- [ ] **Step 4: Verify focused regressions**

Run: `cd backend && .venv/bin/python -m unittest tests.test_attraction_search_service tests.test_location -v`

Expected: PASS, including current-location and explicit-destination tests.

- [ ] **Step 5: Commit**

```bash
git add backend/domains/attraction/search_service.py backend/domains/attraction/reranker.py backend/tests/test_attraction_search_service.py
git commit -m "fix: constrain attraction results to requested area"
```

### Task 2: Render one localized attraction explanation for chat and sidebar

**Files:**
- Modify: `backend/domains/attraction/dspy/renderer.py`
- Modify: `backend/tests/test_attraction_dspy_renderer.py`

**Interfaces:**
- Consumes: `AttractionSelectionPrediction`, `AttractionStructuredRecommendation`, and `AttractionStructuredAnswer.language`.
- Produces: `render_place_recommendation_reason(query_reason, recommendation, language) -> str`.

- [ ] **Step 1: Write failing renderer tests**

```python
def test_sidebar_reason_is_the_same_place_prose_used_by_chat(self):
    result = render_selection_result(selection, korean_answer_with_available_contexts)
    self.assertIn(result.selections[0].selection_reason, result.answer)
    self.assertNotIn("질의 적합성:", result.selections[0].selection_reason)
    self.assertNotIn("혼잡도:", result.selections[0].selection_reason)

def test_renderer_formats_observed_time_without_seconds_or_offset(self):
    result = render_selection_result(selection, answer_with_observed_at("2026-07-18T16:00:45+09:00"))
    self.assertIn("2026-07-18 16:00", result.answer)
    self.assertNotIn("+09:00", result.answer)

def test_renderer_uses_english_for_english_answer(self):
    result = render_selection_result(selection, english_answer)
    self.assertIn("matches your request", result.selections[0].selection_reason)
    self.assertNotIn("질의 적합성", result.selections[0].selection_reason)
```

- [ ] **Step 2: Confirm the tests fail before implementation**

Run: `cd backend && .venv/bin/python -m unittest tests.test_attraction_dspy_renderer -v`

Expected: FAIL because `_sidebar_reason()` emits labels and `_provenance()` exposes raw ISO timestamps.

- [ ] **Step 3: Implement shared prose and compact time formatting**

```python
def render_place_recommendation_reason(query_reason, recommendation, language):
    parts = [_localized_query_sentence(query_reason, language)]
    parts.append(_localized_context_sentence("congestion", recommendation.congestion, language))
    parts.append(_localized_context_sentence("weather", recommendation.weather, language))
    return " ".join(part for part in parts if part)

def _format_observed_at(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M") if value else None
    except ValueError:
        return None
```

Use the result for `CandidateSelection.selection_reason`, and append it below the numbered name in `_natural_recommendation()`. Keep the existing language-specific unavailable-context messages.

- [ ] **Step 4: Verify renderer and SSE integration**

Run: `cd backend && .venv/bin/python -m unittest tests.test_attraction_dspy_renderer tests.test_attraction_dspy_chat_integration -v`

Expected: PASS. Each SSE selection reason is contained in the corresponding localized chat paragraph.

- [ ] **Step 5: Commit**

```bash
git add backend/domains/attraction/dspy/renderer.py backend/tests/test_attraction_dspy_renderer.py
git commit -m "feat: unify localized attraction recommendation reasons"
```

### Task 3: Localize fixed sidebar display labels on tab changes

**Files:**
- Create: `frontend/src/services/display/localizedPlaceDisplay.js`
- Create: `frontend/src/services/display/localizedPlaceDisplay.test.js`
- Modify: `frontend/src/components/sidebar/PlaceItem.jsx`
- Modify: `frontend/src/components/sidebar/PlaceRecommendTab.jsx`
- Modify: `frontend/src/pages/PlaceSidebar.jsx`

**Interfaces:**
- Consumes: `FrontendPlace.category`, `subCategory`, and `lang` from `useLangStore`.
- Produces: `getLocalizedPlaceCategory(place, lang)` and `getLocalizedPlaceSubCategory(place, lang)` without changing the stored place object.

- [ ] **Step 1: Write pure Node tests**

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import { getLocalizedPlaceCategory, getLocalizedPlaceSubCategory } from './localizedPlaceDisplay.js';

test('renders attraction labels in English without mutating the source place', () => {
  const place = { category: '관광지', subCategory: '궁궐' };
  assert.equal(getLocalizedPlaceCategory(place, 'en'), 'Attraction');
  assert.equal(getLocalizedPlaceSubCategory(place, 'en'), 'Palace');
  assert.equal(place.category, '관광지');
});

test('renders the same fixed category in Korean after a language toggle', () => {
  assert.equal(getLocalizedPlaceCategory({ category: 'Attraction' }, 'ko'), '관광지');
});
```

- [ ] **Step 2: Confirm the test fails before implementation**

Run: `cd frontend && node --test src/services/display/localizedPlaceDisplay.test.js`

Expected: FAIL because the display-localization module does not exist.

- [ ] **Step 3: Add pure display localization and wire it into cards**

```javascript
const CATEGORY_LABELS = {
  attraction: { ko: '관광지', en: 'Attraction' },
  restaurant: { ko: '맛집', en: 'Restaurant' },
  cafe: { ko: '카페', en: 'Cafe' },
  accommodation: { ko: '숙소', en: 'Accommodation' },
};

const CATEGORY_KEYS = {
  '관광지': 'attraction', Attraction: 'attraction',
  '맛집': 'restaurant', Restaurant: 'restaurant',
  '카페': 'cafe', Cafe: 'cafe',
  '숙소': 'accommodation', Accommodation: 'accommodation',
};
const SUBCATEGORY_LABELS = {
  '궁궐': { ko: '궁궐', en: 'Palace' }, Palace: { ko: '궁궐', en: 'Palace' },
};
export function getLocalizedPlaceCategory(place, lang) {
  const key = CATEGORY_KEYS[place.category];
  return key ? CATEGORY_LABELS[key][lang === 'en' ? 'en' : 'ko'] : place.category;
}
export function getLocalizedPlaceSubCategory(place, lang) {
  const label = SUBCATEGORY_LABELS[place.subCategory];
  return label ? label[lang === 'en' ? 'en' : 'ko'] : place.subCategory;
}
```

Read `lang` in `PlaceSidebar`, pass it through `PlaceRecommendTab` to `PlaceItem`, and render only the helper values. Do not translate `place.name`, `selectionReason`, or evidence text in the browser.

- [ ] **Step 4: Verify frontend behavior**

Run: `cd frontend && npm test && npm run lint && npm run build`

Expected: PASS. Existing tests and the new pure display test pass; production build completes.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/display/localizedPlaceDisplay.js frontend/src/services/display/localizedPlaceDisplay.test.js frontend/src/components/sidebar/PlaceItem.jsx frontend/src/components/sidebar/PlaceRecommendTab.jsx frontend/src/pages/PlaceSidebar.jsx
git commit -m "feat: localize sidebar place labels"
```

### Task 4: Full regression verification

**Files:**
- Verify: `backend/tests/test_attraction_search_service.py`
- Verify: `backend/tests/test_attraction_dspy_renderer.py`
- Verify: `backend/tests/test_attraction_dspy_chat_integration.py`
- Verify: `frontend/src/services/display/localizedPlaceDisplay.test.js`

- [ ] **Step 1: Run attraction backend regressions**

Run: `cd backend && .venv/bin/python -m unittest tests.test_attraction_search_service tests.test_attraction_dspy_renderer tests.test_attraction_dspy_chat_integration tests.test_location -v`

Expected: PASS with district filtering, language-specific common prose, and compact timestamps covered.

- [ ] **Step 2: Run frontend tests, lint, and production build**

Run: `cd frontend && npm test && npm run lint && npm run build`

Expected: PASS.

- [ ] **Step 3: Check the final change set**

Run: `git diff --check && git status --short`

Expected: no whitespace errors and no accidental non-attraction backend changes.
