"""Release-gate contracts for the GitHub Actions workflow."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_main_release_runs_versioned_playwright_suite_as_blocking_gate():
    """The real browser suite must run, and its failure must fail the workflow."""
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text("utf-8"))
    e2e = workflow["jobs"]["e2e-tests"]
    steps = e2e["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)

    assert any(step.get("uses", "").startswith("pnpm/action-setup@") for step in steps)
    assert "pnpm install --frozen-lockfile" in commands
    assert "playwright install --with-deps chromium" in commands
    assert "pnpm test" in commands
    assert not any(step.get("continue-on-error", False) for step in steps)
    assert "e2e-tests" in workflow["jobs"]["ci-summary"]["needs"]
