"""Exercise competing review decisions in the disposable CI deployment."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from uuid import uuid4

import httpx

from backend.app.db.database import get_db_context
from backend.app.db.models import AnalysisJob, HITLReview, Report, Triage

if os.environ.get("POSTGRES_DB") != "medsafe_ci":
    raise RuntimeError("This scenario requires the disposable medsafe_ci database")

session_id = str(uuid4())
with get_db_context() as db:
    triage = Triage(age=42, status="awaiting_review")
    db.add(triage)
    db.flush()
    report = Report(triage_id=triage.id, risk_level="high", model_used="ci-fixture")
    db.add(report)
    db.flush()
    state = {
        "session_id": session_id,
        "triage_id": str(triage.id),
        "report_id": str(report.id),
        "risk_level": "high",
        "requires_human_review": True,
        "timestamps": {"hitl_started": datetime.now(timezone.utc).isoformat()},
    }
    db.add(AnalysisJob(session_id=session_id, triage_id=triage.id,
                       status="awaiting_review", state=state))
    db.commit()

with httpx.Client(base_url="http://localhost:9000/api/v2", timeout=30) as client:
    login = client.post("auth/login", json={"email": "admin@medsafe.local",
                                           "password": os.environ["ADMIN_INITIAL_PASSWORD"]})
    login.raise_for_status()
    client.headers["Authorization"] = "Bearer " + login.json()["access_token"]
    barrier = Barrier(2)

    def decide(approved):
        barrier.wait(timeout=10)
        return client.post("hitl/approve", json={"session_id": session_id, "approved": approved})

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(decide, (True, False)))

assert sorted(response.status_code for response in responses) == [200, 400], [
    response.status_code for response in responses
]
winner = next(response.json()["status"] for response in responses if response.is_success)
with get_db_context() as db:
    decision = db.query(HITLReview).filter_by(session_id=session_id).one()
    job = db.query(AnalysisJob).filter_by(session_id=session_id).one()
    report = db.get(Report, job.state["report_id"])
    assert job.status == winner == ("completed" if decision.approved else "rejected")
    assert report.status == ("final" if decision.approved else "rejected")
    assert db.get(Triage, job.triage_id).status == winner
print("One terminal decision and one audit entry persisted.")
