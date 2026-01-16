from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import pytest


@pytest.fixture(autouse=True)
def _required_env(monkeypatch):
    """
    Ensure Settings() can be imported when running this file standalone.
    """
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-minimum-32-characters-long")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://medsafe:test_password@localhost:5432/medsafe"
    )


@dataclass
class _ModelBase:
    id: Optional[str] = None


@dataclass
class _Triage(_ModelBase):
    user_id: Optional[str] = None
    age: Any = None
    weight: Any = None
    pregnant: bool = False
    cid_codes: Any = field(default_factory=list)
    meds_in_use: Any = field(default_factory=list)
    allergies: Any = field(default_factory=list)
    renal_function: Any = None
    hepatic_function: Any = None
    notes: Optional[str] = None
    status: str = "pending"
    job_id: Optional[str] = None


@dataclass
class _Report(_ModelBase):
    triage_id: Optional[str] = None
    risk_level: str = "unknown"
    contraindications: Any = field(default_factory=list)
    interactions: Any = field(default_factory=list)
    dosage_adjustments: Any = field(default_factory=list)
    adverse_reactions: Any = field(default_factory=list)
    evidence_links: Any = field(default_factory=list)
    model_used: str = ""
    confidence_score: float = 0.0
    is_final: bool = True


@dataclass
class _AnalysisJob(_ModelBase):
    session_id: str = ""
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
    def __init__(self, store: list, model_type: type):
        self._store = store
        self._model_type = model_type

    def filter(self, *args, **kwargs):  # noqa: ARG002
        return self

    def first(self):
        for obj in self._store:
            if isinstance(obj, self._model_type):
                return obj
        return None


class _FakeDB:
    def __init__(self):
        self.items: list[Any] = []
        self._id_seq = 0

    def add(self, obj):
        self.items.append(obj)

    def commit(self):
        return None

    def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            self._id_seq += 1
            obj.id = f"id-{self._id_seq}"

    def query(self, model_type: type):
        return _Query(self.items, model_type)


class _EnumLike:
    def __init__(self, value: str):
        self.value = value


class _FakeGraph:
    def __init__(self, result: dict):
        self.result = result
        self.calls = []

    async def ainvoke(self, initial_state, config):
        self.calls.append((initial_state, config))
        return self.result


@pytest.fixture
def _patched_orchestrator(monkeypatch):
    """
    Patch AnalysisOrchestrator dependencies so we don't hit real DB or LangGraph.
    """
    from backend.app.services import analysis_orchestrator as mod

    fake_db = _FakeDB()

    @contextlib.contextmanager
    def _ctx():
        yield fake_db

    monkeypatch.setattr(mod, "get_db_context", _ctx, raising=True)
    monkeypatch.setattr(mod, "Triage", _Triage, raising=True)
    monkeypatch.setattr(mod, "Report", _Report, raising=True)
    monkeypatch.setattr(mod, "AnalysisJob", _AnalysisJob, raising=True)

    # Minimal langgraph settings
    monkeypatch.setattr(
        mod,
        "get_langgraph_settings",
        lambda: type("S", (), {"effective_model_name": "model-x"})(),
        raising=True,
    )

    return mod, fake_db


@pytest.mark.asyncio
async def test_create_triage_save_to_db_false_returns_none(_patched_orchestrator):
    mod, _db = _patched_orchestrator
    orch = mod.AnalysisOrchestrator()
    triage_id = await orch.create_triage({"age": 30}, "Aspirin", save_to_db=False)
    assert triage_id is None


@pytest.mark.asyncio
async def test_create_triage_persists_and_merges_meds(_patched_orchestrator):
    mod, fake_db = _patched_orchestrator
    orch = mod.AnalysisOrchestrator()
    triage_id = await orch.create_triage(
        {
            "age": 30,
            "current_medications": ["Warfarin"],
            "conditions": ["HTN"],
            "allergies": [],
        },
        "Aspirin",
        user_id="u1",
        notes="n",
        save_to_db=True,
    )
    assert triage_id == "id-1"
    triage = fake_db.items[0]
    assert triage.user_id == "u1"
    assert triage.meds_in_use == ["Aspirin", "Warfarin"]
    assert triage.cid_codes == ["HTN"]


@pytest.mark.asyncio
async def test_run_analysis_calls_graph_with_thread_id_and_model_override(
    _patched_orchestrator, monkeypatch
):
    mod, _db = _patched_orchestrator
    fake_graph = _FakeGraph(
        {"risk_level": "low", "interactions": [], "contraindications": []}
    )
    monkeypatch.setattr(mod, "get_graph", lambda: fake_graph, raising=True)

    orch = mod.AnalysisOrchestrator()
    result = await orch.run_analysis(
        {"age": 10, "meds_in_use": ["A"]}, "B", session_id="s1", model_override="m1"
    )
    assert result["risk_level"] == "low"
    (initial_state, cfg) = fake_graph.calls[0]
    assert cfg["configurable"]["thread_id"] == "s1"
    assert cfg["configurable"]["model_override"] == "m1"
    assert initial_state["patient_data"]["current_medications"] == ["A"]


def test_format_v2_response_structured_and_enum_risk(_patched_orchestrator):
    mod, _db = _patched_orchestrator
    orch = mod.AnalysisOrchestrator()

    result = {
        "risk_level": _EnumLike("high"),
        "structured_recommendations": {"header": "H", "immediate_actions": ["X"]},
        "status": "completed",
    }
    out = orch.format_v2_response(result, session_id="s", triage_id="t", report_id="r")
    assert out["risk_level"] == "high"
    assert out["structured_recommendations"]["header"] == "H"
    assert out["structured_recommendations"]["immediate_actions"] == ["X"]


def test_format_legacy_response_includes_highlights_and_model_fallback(
    _patched_orchestrator, monkeypatch
):
    mod, _db = _patched_orchestrator
    orch = mod.AnalysisOrchestrator()

    # Make accuracy deterministic for assertion
    monkeypatch.setattr(
        mod, "compute_accuracy", lambda state, patient: (0.8, ["f1"]), raising=True
    )
    monkeypatch.setattr(
        mod,
        "build_recommendations_from_state",
        lambda state: ["Rec 1", "Rec 2"],
        raising=True,
    )

    patient = {
        "age": 70,
        "sex": "F",
        "weight": 60,
        "current_medications": ["A"],
        "conditions": ["C"],
        "allergies": [],
    }
    result = {
        "session_id": "s1",
        "risk_level": _EnumLike("critical"),
        "interactions": [
            {"severity": "high", "drug1": "A", "drug2": "B", "description": "desc"}
        ],
        "contraindications": [
            {"severity": "critical", "type": "x", "description": "y"}
        ],
        "confidence_score": 0.9,
        "status": "completed",
    }
    out = orch.format_legacy_response(result, patient_info=patient, model_used=None)
    assert out["risk_level"] == "critical"
    assert out["model_used"] == "model-x"  # from patched get_langgraph_settings
    assert "Interaction" in out["analysis_notes"]
    assert "Contraindication" in out["analysis_notes"]
    assert "Estimated accuracy" in out["analysis_notes"]


@pytest.mark.asyncio
async def test_create_and_update_job_and_save_report_updates_triage_status(
    _patched_orchestrator,
):
    mod, fake_db = _patched_orchestrator
    orch = mod.AnalysisOrchestrator()

    # create triage to be updated by save_report
    triage_id = await orch.create_triage(
        {"age": 30, "current_medications": []}, "A", save_to_db=True
    )

    job_id = await orch.create_analysis_job(
        session_id="sess",
        triage_id=triage_id,
        user_id="u",
        medication="A",
        patient_data={"age": 30},
        notes=None,
        model_override="m",
    )
    assert job_id == "id-2"

    await orch.update_job(job_id=job_id, status="running", increment_retries=True)
    job = next(x for x in fake_db.items if isinstance(x, _AnalysisJob))
    assert job.status == "running"
    assert job.retries == 1

    # report: requires_human_review -> triage status awaiting_review and is_final False
    report_id = await orch.save_report(
        triage_id, {"risk_level": "high", "requires_human_review": True}
    )
    assert report_id == "id-3"
    triage = next(x for x in fake_db.items if isinstance(x, _Triage))
    assert triage.status == "awaiting_review"
    report = next(x for x in fake_db.items if isinstance(x, _Report))
    assert report.is_final is False
