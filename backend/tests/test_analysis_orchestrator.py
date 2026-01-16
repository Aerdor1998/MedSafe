from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import pytest

import backend.app.services.analysis_orchestrator as ao


@dataclass
class _DummyTriage:
    id: str = "triage-1"
    job_id: Optional[str] = None
    status: str = "pending"


@dataclass
class _DummyReport:
    id: str = "report-1"


@dataclass
class _DummyJob:
    id: str = "job-1"
    session_id: str = "sess-1"
    triage_id: Optional[str] = None
    user_id: Optional[str] = None
    status: str = "pending"
    payload: Dict[str, Any] = field(default_factory=dict)
    state: Dict[str, Any] = field(default_factory=dict)
    last_error: Optional[str] = None
    started_at: Any = None
    finished_at: Any = None
    retries: int = 0


class _Query:
    def __init__(self, model, first_obj):
        self.model = model
        self._first_obj = first_obj

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._first_obj


class _FakeDB:
    def __init__(self, triage=None, job=None):
        self._triage = triage
        self._job = job
        self.added = []
        self.committed = 0
        self.refreshed = []

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed += 1

    def refresh(self, obj):
        self.refreshed.append(obj)

    def query(self, model):
        if model is ao.Triage:
            return _Query(model, self._triage)
        if model is ao.AnalysisJob:
            return _Query(model, self._job)
        return _Query(model, None)


@contextmanager
def _db_ctx(db: _FakeDB):
    yield db


@pytest.mark.asyncio
async def test_orchestrator_run_analysis_builds_initial_state_and_calls_graph(
    monkeypatch,
):
    captured = {}

    class _Graph:
        async def ainvoke(self, initial_state, config):
            captured["initial_state"] = initial_state
            captured["config"] = config
            return {
                "risk_level": "low",
                "interactions": [],
                "contraindications": [],
                "session_id": initial_state["session_id"],
            }

    monkeypatch.setattr(ao, "get_graph", lambda: _Graph())

    orch = ao.AnalysisOrchestrator()
    result = await orch.run_analysis(
        {"age": 10, "cid_codes": ["x"], "meds_in_use": ["a"]},
        "ibuprofen",
        session_id="sess-123",
        triage_id="t-1",
    )
    assert result["risk_level"] == "low"
    assert captured["initial_state"]["patient_data"]["conditions"] == ["x"]
    assert captured["initial_state"]["patient_data"]["current_medications"] == ["a"]
    assert captured["config"]["configurable"]["thread_id"] == "sess-123"


@pytest.mark.asyncio
async def test_orchestrator_job_lifecycle_update(monkeypatch):
    job = _DummyJob(id="job-42", session_id="sess-42")
    db = _FakeDB(job=job)
    monkeypatch.setattr(ao, "get_db_context", lambda: _db_ctx(db))
    monkeypatch.setattr(ao, "AnalysisJob", _DummyJob)

    orch = ao.AnalysisOrchestrator()
    await orch.update_job(
        job_id="job-42", status="running", state={"a": 1}, increment_retries=True
    )
    assert job.status == "running"
    assert job.state == {"a": 1}
    assert job.retries == 1


@pytest.mark.asyncio
async def test_orchestrator_create_analysis_job_sets_triage_job_id(monkeypatch):
    triage = _DummyTriage(id="triage-9")
    db = _FakeDB(triage=triage)
    monkeypatch.setattr(ao, "get_db_context", lambda: _db_ctx(db))
    monkeypatch.setattr(ao, "AnalysisJob", _DummyJob)
    monkeypatch.setattr(ao, "Triage", _DummyTriage)

    orch = ao.AnalysisOrchestrator()
    job_id = await orch.create_analysis_job(
        session_id="sess-9",
        triage_id="triage-9",
        user_id="u",
        medication="aspirin",
        patient_data={"age": 1},
        notes=None,
        model_override="m",
    )
    assert job_id == "job-1"
    assert triage.job_id == "sess-9"


def test_orchestrator_format_responses(monkeypatch):
    class _LangSettings:
        effective_model_name = "model-x"

    monkeypatch.setattr(ao, "get_langgraph_settings", lambda: _LangSettings())

    orch = ao.AnalysisOrchestrator()
    state = {
        "session_id": "sess",
        "risk_level": "high",
        "confidence_score": 0.8,
        "structured_recommendations": {"header": "H", "immediate_actions": ["A"]},
        "interactions": [
            {"drug1": "a", "drug2": "b", "severity": "high", "description": "x"}
        ],
        "contraindications": [{"type": "t", "severity": "high", "description": "y"}],
        "status": "completed",
    }

    v2 = orch.format_v2_response(state, session_id="sess", triage_id="t", report_id="r")
    assert v2["session_id"] == "sess"
    assert v2["structured_recommendations"]["header"] == "H"

    legacy = orch.format_legacy_response(
        state,
        patient_info={"age": 40, "sex": "F", "current_medications": []},
        model_used=None,
    )
    assert legacy["model_used"] == "model-x"
    assert "analysis_notes" in legacy and legacy["analysis_notes"]
