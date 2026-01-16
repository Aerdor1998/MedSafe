"""
Workers package (background processes).

Currently contains the AnalysisJob worker that executes long-running LangGraph runs
and persists results back to Postgres for /api/v2/status polling.
"""
