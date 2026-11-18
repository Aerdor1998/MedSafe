"""Public API coverage for the human review continuation flow."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def test_pharmacist_can_reject_hitl_analysis_and_read_terminal_status(app, client):
    """A pharmacist reviewer can reject a saved analysis without rerunning it."""
    from backend.app.auth.jwt import get_optional_current_user
    from backend.app.auth.rbac import can_approve_analysis
    from backend.app.routers import langgraph as langgraph_module

    job = SimpleNamespace(
        id="job-1",
        session_id="review-session",
        user_id="pharmacist-1",
        triage_id=None,
        status="awaiting_review",
        payload={"patient_data": {}},
        created_at=None,
        finished_at=None,
        state={
            "session_id": "review-session",
            "triage_id": "triage-1",
            "report_id": "report-1",
            "status": "awaiting_human_review",
            "risk_level": "high",
            "confidence_score": 0.91,
            "interactions": [],
            "contraindications": [],
            "dosage_adjustments": [],
            "adverse_reactions": [],
            "evidence_links": [],
            "timestamps": {"hitl_started": "2026-11-18T10:00:00+00:00"},
        },
    )

    class FakeOrchestrator:
        async def get_job_by_session(self, session_id):
            return job if session_id == job.session_id else None

        async def update_job(self, *, status, state, finished_at, **_):
            job.status = status
            job.state = state
            job.finished_at = finished_at

    triage = SimpleNamespace(status="awaiting_review")
    report = SimpleNamespace(
        id="report-1",
        is_final=False,
        confidence_score=0.0,
        status="draft",
    )
    triage_query = MagicMock()
    triage_query.filter.return_value = triage_query
    triage_query.first.return_value = triage
    report_query = MagicMock()
    report_query.filter.return_value = report_query
    report_query.first.return_value = report
    db = MagicMock()
    job_query = MagicMock()
    job_query.filter.return_value.with_for_update.return_value.first.return_value = job
    report_query.order_by.return_value = report_query
    db.query.side_effect = [job_query, triage_query, report_query, job_query]

    @contextmanager
    def db_context():
        yield db

    orchestrator = FakeOrchestrator()
    app.dependency_overrides[can_approve_analysis] = lambda: "pharmacist-1"
    app.dependency_overrides[get_optional_current_user] = lambda: "pharmacist-1"
    try:
        with patch.object(
            langgraph_module, "get_orchestrator", return_value=orchestrator
        ), patch.object(
            langgraph_module, "get_db_context", side_effect=db_context
        ), patch.object(
            langgraph_module,
            "get_settings",
            return_value=SimpleNamespace(enable_hitl=True),
        ):
            decision = client.post(
                "/api/v2/hitl/approve",
                json={
                    "session_id": "review-session",
                    "approved": False,
                    "physician_notes": "Interaction remains unsafe",
                },
            )
            duplicate = client.post(
                "/api/v2/hitl/approve",
                json={"session_id": "review-session", "approved": True},
            )
            status = client.get("/api/v2/status/review-session")
    finally:
        app.dependency_overrides.pop(can_approve_analysis, None)
        app.dependency_overrides.pop(get_optional_current_user, None)

    assert duplicate.status_code == 400
    db.commit.assert_called_once()
    db.add.assert_called_once()
    assert decision.status_code == 200
    assert decision.json()["status"] == "rejected"
    assert decision.json()["message"] == "Analysis rejected by reviewer pharmacist-1."
    assert status.status_code == 200
    assert status.json()["status"] == "rejected"
    assert status.json()["report_id"] == "report-1"
    assert "hitl_completed" in status.json()["final_report"]["timestamps"]
    assert triage.status == "rejected"
    assert report.status == "rejected"
