"""
Medication search API (v2).

This is a lightweight endpoint used by the frontend auto-complete.
It is intentionally simple and uses the bundled YAML knowledge base.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Query, Request

from ..data import get_drug_synonyms
from ..middleware.rate_limit import limiter

router = APIRouter(prefix="/api/v2/medications", tags=["medications"])


@router.get("/search")
@limiter.limit("60/minute")
async def search_medications(
    request: Request,
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
) -> Dict[str, Any]:
    """
    Search medication names.

    Returns:
      { "results": [ { "name": "...", "active_ingredient": "...", "therapeutic_class": "..." } ] }
    """
    query = q.strip().lower()
    synonyms = get_drug_synonyms()

    hits: List[Dict[str, str]] = []

    # Search by canonical name + synonyms.
    for canonical, syns in synonyms.items():
        if len(hits) >= limit:
            break

        canonical_l = canonical.lower()
        if query in canonical_l:
            hits.append(
                {
                    "name": canonical,
                    "active_ingredient": canonical,
                    "therapeutic_class": "",
                }
            )
            continue

        if isinstance(syns, list):
            for s in syns:
                if query in str(s).lower():
                    hits.append(
                        {
                            "name": str(s),
                            "active_ingredient": canonical,
                            "therapeutic_class": "",
                        }
                    )
                    break

    return {"results": hits}
