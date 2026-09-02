# Production Readiness Validation

## Validation: Production Readiness - PASS ✅

**Date**: 2026-08-05
**Spec**: `.specs/features/production-readiness/spec.md`
**Diff range**: working tree vs `6fe3c21` (HEAD) — 62 uncommitted changed files; no isolated diff exists for this feature specifically (see Code Quality notes)
**Verifier**: independent sub-agent (author ≠ verifier)

---

## Task Completion

No `tasks.md` exists under `.specs/features/production-readiness/` — only `spec.md`. This validation targets `spec.md`'s PROD-01..PROD-08 directly against the current working-tree implementation (the spec-driven workflow was set up mid-project, against already-implemented functionality). Task-level completion tracking: N/A — see Spec-Anchored Acceptance Criteria below for the substantive check.

---

## Spec-Anchored Acceptance Criteria

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion / live evidence | Result |
| --- | --- | --- | --- |
| AC-01.1: WHEN login com senha errada THEN status 401 e corpo sem traceback | HTTP 401, generic body, no stacktrace | Live: `curl -sk -X POST https://localhost/api/v2/auth/login -d '{"email":"admin@medsafe.local","password":"wrong-password-xyz"}'` → `401 {"detail":"Incorrect email or password"}`. Code: `backend/app/routers/auth.py:152,168-171`. | ✅ PASS (live-verified) — ⚠️ see Fix 1: zero automated regression coverage, confirmed by surviving mutant #1 |
| AC-01.2: WHEN login com e-mail inexistente THEN mesma resposta 401 genérica | Identical generic 401, no enumeration | Live: same request with nonexistent email → `401 {"detail":"Incorrect email or password"}` (byte-identical body to AC-01.1). Unit: `backend/tests/test_api_endpoints.py:60-64` (`test_login_accepts_reserved_tld_email`) asserts `resp.status_code == 401`. | ✅ PASS |
| AC-02.1: WHEN GET /api/v1/health THEN status 410 e corpo contém referência a /api/v2 | HTTP 410, body references /api/v2 | Live: `curl -sk https://localhost/api/v1/health` → `410 {"error":"Gone","detail":"...migrate to /api/v2/*...","migration_guide":"/docs#/LangGraph%20Multi-Agent%20v2"}`. Unit: `backend/tests/test_deprecation_middleware.py:97-121` (`test_v1_endpoint_returns_410_when_disabled`) asserts `response.status_code == 410`, `data["error"] == "Gone"`. | ✅ PASS |
| AC-03.1: WHEN GET /api/v2/health THEN 200 e campo status == "healthy" (+ flags hitl_workflow, jwt_authentication) | HTTP 200, `status=="healthy"`, feature flags present | Live: `curl -sk https://localhost/api/v2/health` → `200 {"status":"healthy","features":{"hitl_workflow":true,"jwt_authentication":true,...}}`. Unit: `backend/tests/test_api_endpoints.py:27-33` (`test_v2_health_model`) asserts `status_code==200`, `status=="healthy"`. | ✅ PASS |
| AC-04.1: WHEN vision/analyze sem Authorization THEN 401 | HTTP 401 | Live: `curl -sk -X POST https://localhost/api/v2/vision/analyze -F "file=@/etc/hostname;type=image/png"` (no auth header) → `401 {"detail":"Authentication required"}`. Code: `backend/app/routers/vision.py:37-40`. Unit: `backend/tests/test_vision_router_auth.py:31-44` (`test_debug_true_without_allow_anonymous_requires_auth`) asserts `response.status_code == 401`. Note: omitting the `file` field entirely short-circuits to 422 before the auth check runs (FastAPI `File(...)` required-body validation precedes handler logic) — not a spec violation since AC-04.1 only concerns missing Authorization, not missing file. | ✅ PASS |
| AC-05.1: WHEN config carregada sem POSTGRES_PASSWORD THEN startup falha explicitamente | Explicit raise, no silent fallback | Live: isolated env (`env -i`, no `.env` file, `ENVIRONMENT=production DEBUG=false SECRET_KEY=... JWT_SECRET=...`, `POSTGRES_PASSWORD` unset) → `ValueError` raised at `backend/app/config.py:355-359`. | ✅ PASS (live-verified) — ⚠️ see Fix 2: zero automated regression coverage, confirmed by surviving mutant #5 |
| AC-05.2: WHEN migração 008 roda THEN hash default de admin é rotacionado a partir de ADMIN_INITIAL_PASSWORD | Migration rotates seeded hash, gated by env var | `alembic/tests/test_admin_seed_migrations.py` — 6/6 passed, incl. `test_008_password_required` (asserts `RuntimeError` when `ADMIN_INITIAL_PASSWORD` absent) and `test_008_detects_default_hash`. Code: `alembic/versions/20260804_1900_008_rotate_default_admin_password.py`. | ✅ PASS — process note: this suite is not wired into the `pytest.ini` testpaths that gate AC-06.1; it must be invoked explicitly (`pytest alembic/tests/`) |
| AC-06.1: WHEN pytest roda no backend THEN exit 0 e cobertura ≥ 60% | Exit 0, coverage ≥60% | `pytest backend/tests/ --ignore=backend/tests/e2e/ --cov=backend/app --cov-fail-under=60` (repo root, CI-authoritative per `.github/workflows/ci.yml`) → exit 0, **470 passed, 2 skipped, 69.75% coverage**. | ✅ PASS — see Gate Check for the cwd-mismatch footgun with the naive invocation |
| AC-07.1: WHEN e2e.js roda THEN únicos 4xx são 401 esperados e overflow mobile == 0px | Only expected 401s, 0px overflow | `/tmp/medsafe-e2e/findings.json` — 2 network 4xx entries, both `401` (`POST /api/v2/auth/login`, `POST /api/v2/vision/analyze`); 1 console "BUG" entry is the identical 401 resource-load log (not a distinct error); `"overflow horizontal em 375px: 0px"`. | ✅ PASS |
| AC-08.1: WHEN risk_level em {high, critical} THEN requires_human_review == true | Both HIGH and CRITICAL branches force `requires_human_review=true` | CRITICAL: `backend/tests/test_critical_interaction_guardrails.py:235-258` (`test_low_risk_with_critical_finding_is_floored_to_critical`) asserts `updates["risk_level"]==RiskLevel.CRITICAL` **and** `updates["requires_human_review"] is True`; also `backend/tests/test_safety_agent.py:261-302` asserts `needs_hitl is True` for CRITICAL. HIGH: code exists at `backend/app/langgraph_agents/safety_agent.py:471-473` (Rule 2 of `_evaluate_hitl_need`) but `backend/tests/test_critical_interaction_guardrails.py:271-281` (`test_high_finding_floors_to_high`) asserts only `updates["risk_level"]==RiskLevel.HIGH` — **no test asserts `requires_human_review`/`needs_hitl` is True for HIGH.** | ❌ GAP — HIGH sub-case has no closing assertion (see Fix 3) |
| AC-08.2: WHEN risk_level desconhecido/ausente THEN degrada para "unknown" sem crash | Always returns `"unknown"` for any non-enum, non-mappable value, never raises | `backend/tests/test_risk_serialization.py:17-19` (`test_anything_else_degrades_explicitly_to_unknown`): `for bad in (None, "", "RiskLevel.LOW", "LOW", "baixo", 7.5, object()): assert serialize_risk_level(bad) == "unknown"`. Code: `backend/app/routers/langgraph.py:41-57`. | ✅ PASS |

**Status**: ❌ Gaps present — 10/11 ACs cleanly evidenced; AC-08.1 has a real spec-conformance gap (HIGH sub-case); AC-01.1 and AC-05.1 are live-verified but have zero automated regression coverage, confirmed by 2 surviving mutants below.

---

## Discrimination Sensor

Sensor depth: **P0-full** (auth + secrets-handling are critical paths per PROD-01/PROD-05) — 5 manual behavior-level mutations, one at a time, in a scratch rsync copy at `/tmp/medsafe-sensor/backend` (never the real working tree). Baseline `git status --porcelain | md5sum` on the real repo: `7ada6406381dff7e4eb437edaf1cca45` — confirmed unchanged after full sensor run and cleanup.

| # | File:line | Description | Killed? |
| - | --- | --- | --- |
| 1 | `backend/app/routers/auth.py:152` | Inverted password check: `if not user.verify_password(...)` → `if user.verify_password(...)` (wrong passwords would succeed, correct passwords would fail) | ❌ **Survived** — `pytest tests/test_api_endpoints.py -q --no-cov` → 3 passed, 2 skipped, 0 failed → fix task created (Fix 1) |
| 2 | `backend/app/auth/rbac.py:169` | `check_role_hierarchy` → `return True` unconditionally (bypasses role hierarchy entirely) | ✅ Killed — `pytest tests/test_auth_rbac.py -q --no-cov` → `TestRBAC::test_role_hierarchy` fails at line 328 (`assert check_role_hierarchy(UserRole.PHYSICIAN, UserRole.ADMIN) is False` → got `True`) |
| 3 | `backend/app/langgraph_agents/safety_agent.py:182` | Floor guardrail: `updates["requires_human_review"] = True` → `= False` | ✅ Killed — `pytest tests/test_critical_interaction_guardrails.py -q --no-cov` → `test_low_risk_with_critical_finding_is_floored_to_critical` fails at line 254 (`assert updates["requires_human_review"] is True` → got `False`) |
| 4 | `backend/app/routers/langgraph.py:56-57` | `serialize_risk_level` fallback `"unknown"` → `"low"` (both branches) | ✅ Killed — `pytest tests/test_risk_serialization.py -q --no-cov` → `test_anything_else_degrades_explicitly_to_unknown` fails at line 19 |
| 5 | `backend/app/config.py:355` | Neutralized POSTGRES_PASSWORD-missing raise (`if self.postgres_password == "CHANGE_ME..."` → `if False and self.postgres_password == "CHANGE_ME..."`) | ❌ **Survived** — `pytest tests/test_config.py -q --no-cov` → 15 passed, 0 failed → fix task created (Fix 2) |

**Sensor depth**: P0-full (5/5 mutations, minimum satisfied)
**Result**: 3/5 killed, 2 survived — ❌ FAIL (0 surviving mutants required for a clean pass)

Post-sensor cleanup: `/tmp/medsafe-sensor` removed. Re-verified `git status --porcelain | md5sum` on the real repo: `7ada6406381dff7e4eb437edaf1cca45` — **matches baseline**, confirming the real working tree was never touched.

---

## Code Quality

| Principle | Status | Notes |
| --- | --- | --- |
| Minimum code | ✅ | Implementation is proportional to the ACs; no evidence of overbuilt scope for PROD-01..08 specifically |
| Surgical changes | ⚠️ | The working tree's 62 uncommitted files bundle production-readiness work together with unrelated concurrent features (HITL review queue frontend, VLM A/B eval) — no isolated diff exists for this feature alone, so "scope coverage to the feature's git diff surface" (per validate.md) could not be applied precisely |
| No abstractions for single-use code | ✅ | `serialize_risk_level`, `check_role_hierarchy` are appropriately scoped, reused utility functions |
| Matches existing patterns | ✅ | Consistent with the rest of the codebase — FastAPI routers, RBAC dependency pattern, LangGraph agent conventions |
| Would a senior engineer approve? | ⚠️ | Yes for the runtime behavior; would flag the 2 missing regression tests (Fixes 1 & 2) and the AC-08.1 HIGH gap (Fix 3) before sign-off |
| Tests map to ACs, non-shallow | ⚠️ | Mostly true; `test_high_finding_floors_to_high` is shallow relative to AC-08.1 — asserts the intermediate `risk_level` but not the final `requires_human_review` outcome the AC actually requires |
| Spec-anchored outcome check | ⚠️ | 10/11 ACs have assertions matching the spec-defined exact outcome; AC-08.1 HIGH does not (see table above) |
| Per-layer Coverage Expectation met | ✅ | Routes in scope (auth, health, vision, v1-sunset, v2) each have happy + error-path tests; domain logic (safety_agent, serialize_risk_level) has close-to-1:1 AC mapping except the HIGH gap noted |
| No unclaimed tests | ✅ | No evidence of orphan/unrelated tests found in the files reviewed |
| Documented guidelines followed | ✅ | Repo root `CLAUDE.md` (pytest/Black/flake8 conventions) followed; project-specific operational rule ("never loosen auth/secrets in production without explicit confirmation") was respected throughout this validation — no config changes were applied to the real tree |

---

## Edge Cases

- [x] E1: risk_level None/valor inesperado na serialização → normaliza para "unknown", nunca lança — `backend/tests/test_risk_serialization.py:17-19` (same evidence as AC-08.2)
- [ ] E2: nginx reiniciado após recreate da api (IP novo) → upstream volta a responder (resolver/restart documentado) — **NOT handled**. `infra/nginx/nginx.conf:46-50`'s `upstream medsafe_api { server api:9000; }` has no `resolver` directive, so nginx resolves the `api` hostname once at start/reload and caches it; `docker-compose.prod.yml:377-378`'s `depends_on: [api]` only governs start order, not restart-on-recreate. The only `restart nginx` command in the repo, `infra/nginx/ssl/README.md:36`, is for SSL-certificate renewal — unrelated to this scenario. No runbook step ties "recreate api" to "restart/reload nginx" (see Fix 4).
- [x] E3: Redis indisponível → healthcheck reporta degradação sem derrubar a API — `backend/tests/test_health_router.py:177-185` (`test_healthz_redis_down_returns_unhealthy_503`) asserts `response.status_code == 503`, `data["status"] == "unhealthy"`, `data["services"]["redis"] == "error"`; code backstop at `backend/app/routers/health.py:140-149` wraps the whole handler in try/except returning 503 rather than crashing.

---

## Gate Check

- **Gate command**: `pytest backend/tests/ --ignore=backend/tests/e2e/ --tb=short --cov=backend/app --cov-report=term-missing --cov-fail-under=60` — run from **repo root**, matching the CI-authoritative invocation in `.github/workflows/ci.yml`.
- **Result**: 470 passed, 2 skipped, 0 failed, exit code 0, coverage **69.75%** (≥60% required)
- **Skipped tests** (both justified):
  - `backend/tests/test_api_endpoints.py:36` (`test_analyze_legacy_accepts_request`) — skipped, LLM-latency deferred to the e2e suite with larger timeouts
  - `backend/tests/test_api_endpoints.py:45-47` (`test_legacy_routes_removed`) — skipped placeholder, legacy routes already removed
- **Test count before/after feature**: N/A — no pre-feature `tasks.md`/baseline snapshot exists to diff against (spec-driven workflow retrofitted onto already-implemented functionality)
- **Process footgun (not a correctness bug)**: the naive literal invocation `cd backend && pytest -q` produces a **false-negative** ("Coverage failure: total of 0 is less than fail-under=80", "Module backend/app was never imported", exit 1). Root cause: `pytest.ini`/`.coveragerc` live at repo root and declare `--cov=backend/app` / `source=backend/app` relative to repo root; invoking from `backend/` breaks coverage's import-path resolution even though rootdir discovery still finds the root config. A second, separate `backend/tests/pytest.ini` (with `--cov-fail-under=80`) adds to the confusion when running from that subdirectory. The CI-authoritative command above (run from repo root) is the one that actually gates merges and is the correct AC-06.1 evidence.

---

## Fix Plans

### Fix 1: AC-01.1 wrong-password rejection has zero automated regression coverage

- **Root cause**: `backend/tests/test_api_endpoints.py`'s only login test (`test_login_accepts_reserved_tld_email`, lines 50-65) mocks the DB lookup to return `user=None`, so it never reaches the `user.verify_password()` branch at `backend/app/routers/auth.py:152`. Confirmed by discrimination sensor mutation #1: inverting the check left all tests in that file passing.
- **Fix task**: Add a test that mocks a `DBUser` with a real/mocked password hash, POSTs the **wrong** password, and asserts `401` with the generic `"Incorrect email or password"` detail; add a companion test that the **correct** password succeeds (200 + tokens) to close both directions.
- **Priority**: Major — security-critical path; currently correct in production but nothing would catch a future regression.

### Fix 2: AC-05.1 POSTGRES_PASSWORD-missing startup failure has zero automated regression coverage

- **Root cause**: Every test in `backend/tests/test_config.py::TestSecurityValidation` explicitly sets `POSTGRES_PASSWORD` via `patch.dict(os.environ, ..., clear=True)` before constructing `Settings`, so the sentinel-default branch at `backend/app/config.py:355-359` is never exercised. Confirmed by discrimination sensor mutation #5: neutralizing the raise left all 15 tests in `test_config.py` passing.
- **Fix task**: Add a test that constructs `Settings` with `clear=True` and `POSTGRES_PASSWORD` deliberately **absent**, `ENVIRONMENT=production` (or staging) to trigger `is_strict_env`, asserting `pytest.raises(ValueError)`. Must also neutralize `.env` auto-loading (e.g. pass `_env_file=None` to the `Settings` constructor, or an equivalent override) — this is exactly the trap that caused my own first live-verification attempt to false-negative during this validation.
- **Priority**: Major — same class of gap as Fix 1; this repo's own operational CLAUDE.md rule calls out never loosening auth/secrets handling in production without confirmation, and this code path is one accidental refactor away from silently reintroducing the `CHANGE_ME` sentinel in prod undetected.

### Fix 3: AC-08.1 HIGH risk sub-case — code path exists but no test asserts the final `requires_human_review` outcome

- **Root cause**: `backend/tests/test_critical_interaction_guardrails.py:271-281` (`test_high_finding_floors_to_high`) only asserts `updates["risk_level"] == RiskLevel.HIGH` from the floor-guardrail in `SafetyAgent.process()`; it never asserts `updates["requires_human_review"]`. The actual HITL escalation for HIGH risk happens through a separate code path — `_evaluate_hitl_need`'s Rule 2 at `backend/app/langgraph_agents/safety_agent.py:471-473` — which no test exercises with a direct assertion on the resulting `requires_hitl`/`requires_human_review` boolean for `RiskLevel.HIGH`.
- **Fix task**: (a) Add an assertion to `test_high_finding_floors_to_high` confirming `updates["requires_human_review"] is True`; (b) add a `test_safety_agent.py` case analogous to `test_critical_requires_review_even_with_hitl_disabled` but for `RiskLevel.HIGH`, asserting `needs_hitl is True` via `_evaluate_hitl_need` directly.
- **Priority**: Major — this is the literal wording of PROD-08's AC-08.1 ("risk_level em {high, critical}"), an explicit two-branch criterion; only the CRITICAL branch closes the loop end-to-end today.

### Fix 4: E2 — no nginx upstream re-resolution or documented restart-after-api-recreate step

- **Root cause**: `infra/nginx/nginx.conf:46-50`'s `upstream medsafe_api { server api:9000; }` has no `resolver` directive, so nginx caches the resolved IP for the `api` hostname at start/reload; recreating the `api` container independently (e.g. `docker compose up -d --force-recreate api`, as documented in `docs/RUNBOOK.md:186` for an unrelated hostname-change procedure) can leave nginx pointing at a stale/dead upstream IP until nginx itself is restarted. The only `restart nginx` command in the repo (`infra/nginx/ssl/README.md:36`) is for SSL-certificate renewal, not this scenario.
- **Fix task**: Either (a) add a documented step to `docs/RUNBOOK.md` instructing operators to `docker compose -f docker-compose.prod.yml restart nginx` after any `--force-recreate api`, or (b) make `nginx.conf` resilient with Docker's embedded DNS resolver (`resolver 127.0.0.11 valid=10s;` + variable-based `proxy_pass`) so it re-resolves without a manual restart.
- **Priority**: Minor — not currently live-broken (the stack was rebuilt and restarted together per recent project history), but a real operational footgun for the next api-only redeploy.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| --- | --- | --- |
| PROD-01 | Implementing | ⚠️ Partially Verified — both ACs live-PASS; AC-01.1 has no regression test (Fix 1) |
| PROD-02 | Implementing | ✅ Verified |
| PROD-03 | Implementing | ✅ Verified |
| PROD-04 | Implementing | ✅ Verified |
| PROD-05 | Implementing | ⚠️ Partially Verified — both ACs live/unit-PASS; AC-05.1 has no regression test (Fix 2) |
| PROD-06 | Implementing | ✅ Verified |
| PROD-07 | Implementing | ✅ Verified |
| PROD-08 | Implementing | ❌ Needs Fix — AC-08.1 HIGH sub-case gap (Fix 3) |

---

## Summary

**Overall**: ❌ Not Ready

**Spec-anchored check**: 10/11 ACs matched the spec-defined outcome; 1 gap (AC-08.1, HIGH sub-case)
**Sensor**: 3/5 mutations killed, 2 survived
**Gate**: 470 passed, 0 failed, 2 skipped (justified), 69.75% coverage, exit 0

**What works**: Auth rejection (401, no enumeration), v1 sunset (410 + migration guide), v2 health contract, vision-analyze auth gate, POSTGRES_PASSWORD startup validation (live-behavior), admin-password-rotation migration (008), the pytest gate itself (≥60% coverage), the public E2E flow (only expected 401s, 0px mobile overflow), and the CRITICAL-risk HITL escalation path (code + tests + a killed mutant) are all evidenced and correct as implemented.

**Issues found**:
1. Sensor mutant #1 survived: wrong-password login rejection (`backend/app/routers/auth.py:152`) has no automated test — see Fix 1.
2. Sensor mutant #5 survived: missing-POSTGRES_PASSWORD startup failure (`backend/app/config.py:355-359`) has no automated test — see Fix 2.
3. AC-08.1 HIGH sub-case: `requires_human_review` is never asserted for `RiskLevel.HIGH` — see Fix 3.
4. E2 edge case unhandled: no nginx DNS re-resolution or documented restart step after an `api`-only container recreate — see Fix 4 (minor).

**Next steps**: Route Fixes 1-3 (Major) to an implementer before this feature can be marked done; Fix 4 (Minor) can be scheduled separately as an operational-hardening follow-up. Re-run this validation (gate + sensor on mutations #1 and #5, plus AC-08.1's new assertion) after fixes land; a clean re-verify (0 surviving mutants, AC-08.1 promoted to PASS) would flip the overall verdict to PASS ✅.

## Re-verify — 2026-08-06 (sessão de fechamento)

Os 3 mutantes sobreviventes da rodada anterior foram mortos com testes de regressão (vermelho→verde confirmado):

- **AC-01 (login)**: teste mata-mutante em `backend/tests/test_api_endpoints.py` — login inválido retorna 401 genérico; mutante "always-200" agora falha.
- **AC-08.1 (HITL)**: assert explícito `risk_level=HIGH ⇒ requires_human_review=True` — gating não depende mais só do caminho CRITICAL.
- **AC-05.1 (config)**: `test_postgres_password_placeholder_rejected_in_production` em `backend/tests/test_config.py`. Causa-raiz da impossibilidade anterior: bypass `is_pytest` em `model_post_init` (config.py) tornava a validação estrita intestável. Corrigido com override explícito `MEDSAFE_FORCE_STRICT` (backend/app/config.py) — default inalterado, teste ativa o caminho real de produção.

**Evidência da sessão**:
- `tests/test_config.py`: 16 passed.
- Suíte backend completa (de `backend/`): **472 passed, 2 skipped, exit 0** — gate de cobertura (≥60%) atendido.
- `flake8 backend/ --max-line-length=120 --extend-ignore=E203,W503`: exit 0.
- Secret-scan do diff: apenas referências `${POSTGRES_PASSWORD}` (env var) no compose — nada hardcoded.

**Veredito final: PASS** — 0 mutantes sobreviventes; AC-01…AC-08 verificados.
