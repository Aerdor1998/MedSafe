# LESSONS - auto-maintained by scripts/lessons.py

> Machine-owned. Do NOT hand-edit. Changes are overwritten on the next `lessons.py` write.
> Canonical state lives in `.specs/lessons.json`. Edit lessons only via the script.
> promote_threshold=2 distinct features · window_days=45 · quarantine_threshold=2

## Confirmed (load these at Specify/Design)

Corroborated across multiple features. Safe to apply as guidance.

_none_

## Candidates (under observation - do NOT load as guidance yet)

Seen once or not yet corroborated. Tracked, not trusted.

### L-001 - When testing login rejection, add a test that mocks a real password hash and POSTs the wrong password to exercise verify_password() directly - a test that only mocks user=None never reaches that branch.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `backend/tests/test_api_endpoints.py` · harmful: 0
- features: production-readiness
- evidence: backend/app/routers/auth.py:152 (mutant #1) (backend/tests/test_api_endpoints.py)
- last seen: 2026-08-06T01:21:48Z

### L-002 - Security-validation tests that always patch.dict a valid secret env var never exercise the sentinel-default/absence-rejection branch - add an explicit absent-value test with _env_file=None to bypass .env auto-loading.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `backend/tests/test_config.py` · harmful: 0
- features: production-readiness
- evidence: backend/app/config.py:355-359 (mutant #5) (backend/tests/test_config.py)
- last seen: 2026-08-06T01:21:48Z

### L-003 - A two-branch spec criterion (e.g. risk_level in {high, critical}) needs a direct outcome assertion for EACH branch - a test that only asserts the intermediate risk_level for one branch (HIGH) can mask a missing final-outcome assertion (requires_human_review) that the other branch (CRITICAL) does cover.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `backend/app/langgraph_agents/safety_agent.py` · harmful: 0
- features: production-readiness
- evidence: AC-08.1 (backend/app/langgraph_agents/safety_agent.py)
- last seen: 2026-08-06T01:21:48Z

### L-004 - An nginx upstream block resolving a Docker service hostname without a resolver directive caches the IP at start/reload - document (or automate) a nginx restart/reload step whenever that upstream container is recreated independently.
- signal: `spec_deviation` · recurrence: 1 feature(s) · scope: `infra/nginx/nginx.conf` · harmful: 0
- features: production-readiness
- evidence: E2 (spec.md edge cases) (infra/nginx/nginx.conf)
- last seen: 2026-08-06T01:21:48Z

## Quarantined (failed when applied - ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_
