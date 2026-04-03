# Dynamic Keyword Learning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a phased dynamic keyword learning and command routing system for device intents, while preserving current device-control stability and confirmation safety.

**Architecture:** Extend the existing Django `comms` pipeline with a `LearnedKeyword` model, keyword loader cache, optional normalizer, and guarded history-learning flow that only learns from confirmed successful device interactions.

**Tech Stack:** Python, Django, MySQL, asyncio, existing LLM integration, optional Ollama/Gemini normalizer

---

## Model Layering

This plan intentionally separates model responsibilities into two layers instead of chaining two equivalent AI parsers:

- `Lightweight model`: used only by `normalizer.py`
  Responsibility: normalize English, colloquial, or mixed-language device commands into short standard Chinese phrases that are easier for heuristics to parse.
- `Primary model`: existing device-intent AI parser
  Responsibility: handle complex, ambiguous, multi-intent, or heuristic-miss cases after heuristic parsing and optional normalization have both failed.

Expected execution order:

1. heuristic parse first
2. lightweight normalization only when routing says it is needed
3. heuristic parse again on normalized text
4. primary model only as final fallback

Guardrail:

- the lightweight model is a preprocessing layer, not a second full semantic parser
- the primary model remains the only final semantic authority for difficult cases

---

## Scope and Guardrails

- Keep current Chinese heuristic commands working without regression.
- Do not lower confirmation requirements for ambiguous or high-risk controls.
- Ship in phases so each phase can be rolled out and rolled back independently.
- Do not enable history-based learning until static keywords, cache loading, and metrics are stable.

---

## File Plan

| File | Change Type | Responsibility |
|------|-------------|----------------|
| `backend/apps/comms/models.py` | Modify | Add `LearnedKeyword` model |
| `backend/apps/comms/migrations/0008_learnedkeyword.py` | Create | Persist keyword model schema |
| `backend/apps/comms/keyword_loader.py` | Create | Load and merge global/user keyword caches |
| `backend/apps/comms/initial_keywords.py` | Create | Seed bilingual system keywords |
| `backend/apps/comms/device_intent.py` | Modify | Use dynamic keywords in heuristic parsing |
| `backend/apps/comms/device_command_service.py` | Modify | Consume structured keyword payload hints safely |
| `backend/apps/comms/command_router.py` | Create | Classify whether to skip, parse heuristically, normalize, or use AI |
| `backend/apps/comms/normalizer.py` | Create | Small-model normalization with timeout and fallback |
| `backend/apps/comms/keyword_learner.py` | Create | Learn keywords from confirmed successful device interactions |
| `backend/apps/comms/tasks.py` | Modify/Create | Schedule refresh and learning jobs |
| `backend/apps/comms/services.py` | Modify | Integrate router into message flow |
| `backend/apps/comms/tests.py` | Modify | Add regression and feature coverage |
| `backend/.env.example` | Modify | Add normalizer and keyword config |

---

### Task 1: Add Persistent Keyword Model

**Files:**
- Modify: `backend/apps/comms/models.py`
- Create: `backend/apps/comms/migrations/0008_learnedkeyword.py`
- Modify: `backend/apps/comms/tests.py`

- [ ] **Step 1: Add model tests first**

Cover:
- user-scoped keyword creation
- global keyword creation
- duplicate prevention using normalized keyword
- inactive keyword filtering expectations

- [ ] **Step 2: Implement `LearnedKeyword` model**

Required fields:
- `account`
- `keyword`
- `normalized_keyword`
- `canonical`
- `canonical_payload`
- `category`
- `source`
- `confidence`
- `usage_count`
- `last_used_at`
- `learned_at`
- `is_active`

Required constraints:
- unique constraint for user scope: `(account, normalized_keyword, category)`
- unique constraint for global scope where `account is null`

- [ ] **Step 3: Create and review migration**

Run:

```bash
cd backend && uv run python manage.py makemigrations comms
```

Expected:
- migration number continues from current chain
- constraint names are explicit and readable

- [ ] **Step 4: Run model-focused tests**

Run:

```bash
cd backend && uv run pytest apps/comms/tests.py -k "keyword or learned"
```

Expected: PASS

---

### Task 2: Build Static Keyword Seed and Loader

**Files:**
- Create: `backend/apps/comms/initial_keywords.py`
- Create: `backend/apps/comms/keyword_loader.py`
- Modify: `backend/apps/comms/tests.py`

- [ ] **Step 1: Define system keyword seed set**

Include:
- bilingual action keywords
- bilingual room keywords
- bilingual device keywords
- colloquial trigger words
- structured payloads for non-trivial phrases such as `warmer`, `cooler`, `brighter`, `dimmer`

- [ ] **Step 2: Implement `KeywordLoader` cache structure**

Cache should expose:

```python
{
    "devices": set(),
    "rooms": set(),
    "controls": set(),
    "actions": set(),
    "colloquial": set(),
    "mapping": {},
    "payloads": {},
}
```

- [ ] **Step 3: Implement merge behavior**

Rules:
- global keywords load at startup and refresh on interval
- user keywords load on demand
- user keywords override global `mapping`
- user keywords override global `payloads`
- set-like categories merge by union

- [ ] **Step 4: Add loader tests**

Cover:
- global-only load
- global + user merged load
- inactive keyword ignored
- payload override precedence

- [ ] **Step 5: Verify tests**

Run:

```bash
cd backend && uv run pytest apps/comms/tests.py -k "loader or initial_keyword"
```

Expected: PASS

---

### Task 3: Refactor Heuristic Parsing to Use Dynamic Keywords

**Files:**
- Modify: `backend/apps/comms/device_intent.py`
- Modify: `backend/apps/comms/device_command_service.py`
- Modify: `backend/apps/comms/tests.py`

- [ ] **Step 1: Introduce keyword-aware helpers into `device_intent.py`**

Refactor:
- device hint detection
- room matching
- device matching
- control alias matching
- colloquial signal detection

- [ ] **Step 2: Keep current hardcoded defaults as fallback**

Requirement:
- if dynamic loader fails or cache is empty, current built-in behavior must still work

- [ ] **Step 3: Map payload-backed phrases into structured intent fields**

Examples:
- `a bit warmer` -> `control_key=temperature`, `value=+1`
- `brighter` -> `control_key=brightness`, `value=+10%`
- `turn on` -> `control_key=power`, `value=True`

- [ ] **Step 4: Extend resolver compatibility in `device_command_service.py`**

Requirement:
- structured payload hints can assist resolution
- existing high-risk confirmation and ambiguity logic must remain unchanged

- [ ] **Step 5: Add regression tests**

Cover:
- existing Chinese commands still parse
- English action phrases hit heuristic path
- no regression for vehicle query examples
- payload-backed control values resolve correctly

- [ ] **Step 6: Verify tests**

Run:

```bash
cd backend && uv run pytest apps/comms/tests.py -k "device_intent or resolver"
```

Expected: PASS

---

### Task 4: Add Command Router Without Enabling Normalizer Yet

**Files:**
- Create: `backend/apps/comms/command_router.py`
- Modify: `backend/apps/comms/services.py`
- Modify: `backend/apps/comms/tests.py`

- [ ] **Step 1: Implement lightweight router classification**

Supported outputs:
- `standard`
- `try_heuristic`
- `try_heuristic_then_normalize`
- `needs_normalize`
- `needs_full_ai`
- `skip_device`

- [ ] **Step 2: Wire router into `services.py`**

Requirement:
- router decides whether device intent path should run
- when normalizer is disabled, normalize-related routes fall back safely to existing AI path

- [ ] **Step 3: Add router tests**

Cover:
- standard Chinese device command
- obvious non-device chat
- English command requiring normalization
- multi-intent command going straight to full AI

- [ ] **Step 4: Verify tests**

Run:

```bash
cd backend && uv run pytest apps/comms/tests.py -k "router or service"
```

Expected: PASS

---

### Task 5: Add Optional Small-Model Normalizer

**Files:**
- Create: `backend/apps/comms/normalizer.py`
- Modify: `backend/apps/comms/services.py`
- Modify: `backend/.env.example`
- Modify: `backend/apps/comms/tests.py`

- [ ] **Step 1: Implement provider abstraction**

Support:
- Ollama
- Gemini
- timeout fallback to original message

- [ ] **Step 2: Keep normalizer gated by config**

Requirement:
- if provider config is missing or disabled, system behavior remains unchanged

- [ ] **Step 3: Re-run heuristic parse after normalization**

Requirement:
- normalized output must be fed back into the heuristic parser before calling full AI

- [ ] **Step 4: Add tests with mocked normalizer**

Cover:
- English command normalized then parsed heuristically
- timeout returns original message
- non-device input remains non-device

- [ ] **Step 5: Verify tests**

Run:

```bash
cd backend && uv run pytest apps/comms/tests.py -k "normalizer or normalization"
```

Expected: PASS

---

### Task 6: Implement Safe Learning Pipeline

**Files:**
- Create: `backend/apps/comms/keyword_learner.py`
- Modify/Create: `backend/apps/comms/tasks.py`
- Modify: `backend/apps/comms/tests.py`

- [ ] **Step 1: Implement confirmed-sample collector**

Only collect from:
- `Mission` records tied to confirmed successful `DEVICE_CONTROL`
- `DeviceOperationContext` entries with `DEVICE_CONTROL` or `DEVICE_QUERY`
- user-side `ChatMessage` text associated with those successful interactions

- [ ] **Step 2: Exclude unsafe learning samples**

Must exclude:
- `CHAT`
- `UNSUPPORTED_COMMAND`
- clarification missions
- failed controls
- generic environment descriptions without device action

- [ ] **Step 3: Implement learner persistence**

Behavior:
- normalize extracted keywords before upsert
- increment usage count on repeat observation
- update confidence conservatively
- allow `is_active=False` kill switch for bad keywords

- [ ] **Step 4: Add scheduled tasks**

Phased rollout:
- refresh cache task
- user learning task
- global learning task

- [ ] **Step 5: Add learner tests**

Cover:
- successful sample ingestion
- failed sample exclusion
- duplicate upsert behavior
- inactive keyword not returned by loader after learning

- [ ] **Step 6: Verify tests**

Run:

```bash
cd backend && uv run pytest apps/comms/tests.py -k "learner or learning"
```

Expected: PASS

---

### Task 7: Add Metrics, Logging, and Rollout Controls

**Files:**
- Modify: `backend/apps/comms/services.py`
- Modify: `backend/apps/comms/device_intent.py`
- Modify: `backend/.env.example`
- Modify: `backend/apps/comms/tests.py`

- [ ] **Step 1: Add observability fields**

Track:
- router decision
- heuristic hit/miss
- normalizer invoked or skipped
- learned keyword hit
- fallback to full AI

- [ ] **Step 2: Add feature flags**

Suggested flags:
- `ENABLE_DYNAMIC_KEYWORDS`
- `ENABLE_COMMAND_NORMALIZER`
- `ENABLE_HISTORY_KEYWORD_LEARNING`

- [ ] **Step 3: Add rollout safety tests**

Cover:
- all features disabled -> old behavior preserved
- dynamic keywords enabled, learning disabled -> static + DB keywords work
- learning enabled -> loader only returns active keywords

- [ ] **Step 4: Verify tests**

Run:

```bash
cd backend && uv run pytest apps/comms/tests.py
```

Expected: PASS

---

## Release Sequence

- [ ] **Phase 1 Release:** ship `LearnedKeyword`, static seeds, loader, and heuristic integration with feature flag off by default
- [ ] **Phase 2 Release:** enable dynamic keywords for internal accounts, monitor false positives and resolver ambiguity rate
- [ ] **Phase 3 Release:** enable normalizer for English and colloquial traffic, monitor latency and fallback rate
- [ ] **Phase 4 Release:** enable history learning only after two stable releases of keyword loading and routing

---

## Acceptance Criteria

- [ ] Standard Chinese device commands still complete with zero extra model calls in the common path
- [ ] English basic device commands can complete with at most one small-model normalization call
- [ ] High-risk and ambiguous controls preserve existing confirmation behavior
- [ ] Global and user keyword records do not create duplicate rows under normal operation
- [ ] Learning pipeline does not ingest chat-only or failed-command samples
- [ ] With all feature flags disabled, current comms regression tests still pass unchanged

---

## Current Status

Implemented already:

- [x] `LearnedKeyword` model and migration
- [x] static bilingual keyword seed set in code
- [x] keyword loader merge logic for global and account scopes
- [x] dynamic heuristic parsing in `device_intent.py`
- [x] command router wiring in `services.py`
- [x] optional lightweight normalizer module with feature flag
- [x] guarded learner scaffold for device-derived aliases
- [x] scheduler integration for periodic keyword refresh and learning jobs
- [x] AI-assisted history learning from confirmed successful `DeviceOperationContext` samples
- [x] `ChatMessage` linkage back to successful device-operation contexts
- [x] router refinement with richer route taxonomy, reasons, and signal counts
- [x] observability fields for routing, heuristic hit/miss, normalization, and AI fallback
- [x] payload-aware resolver/execution refinement in `device_command_service.py`
- [x] optional idempotent DB seeding command for system keywords
- [x] regression coverage for the comms test suite
- [x] question-vs-command heuristic guard for Chinese state-check utterances
- [x] expanded Chinese colloquial query coverage such as `开没开`, `锁着没有`, `还亮着吗`
- [x] expanded English query coverage such as `is the fridge still on`, `is the car locked`, `what's the bedroom temperature`
- [x] real-AI semantic integration tests that assert intent parsing only and no device execution side effects
- [x] router-side device-signal detection now consumes account-scoped merged keyword cache
- [x] English query detection narrowed to explicit interrogative patterns to avoid noun-only false positives

Still not completed from the spec:

- [ ] metrics aggregation/dashboarding for heuristic hit rate, normalizer hit rate, fallback rate, and latency targets

## Review Notes

Review date: `2026-04-03`

Resolved in follow-up:

- [x] removed noun-only English query trigger `temperature` and switched to explicit English interrogative patterns
- [x] router-side device signal detection now accepts the merged account keyword cache

---

## Next Implementation Order

Follow this order for the next rounds of implementation:

1. Metrics aggregation/dashboarding for routing and fallback behavior

Notes:

- Metrics aggregation/dashboarding is different from span/log emission: tracing fields are already present, but we may still want explicit counters, reports, or dashboards.
- System-keyword DB seeding is optional and should only be added if we decide code-based bootstrap is insufficient for operations or admin tooling.
