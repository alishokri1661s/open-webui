"""
Router for the offline "Intel" workspace.

Endpoints (all require an authenticated, verified user):

    GET  /api/v1/intel/meta                      capability + schema information
    GET  /api/v1/intel/flights                   latest state per aircraft (table)
    GET  /api/v1/intel/flights/{id}/trajectory   full trajectory for one aircraft
    POST /api/v1/intel/search                    document retrieval used as RAG context
    GET  /api/v1/intel/health                    lightweight connectivity probe
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from open_webui.utils.auth import get_verified_user
from open_webui.utils.intel import (
    IntelDisabled,
    IntelError,
    IntelService,
    IntelUnavailable,
    get_config,
)

router = APIRouter()


def _service() -> IntelService:
    try:
        return IntelService()
    except IntelDisabled as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _to_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, IntelUnavailable):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if isinstance(exc, IntelDisabled):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, IntelError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Intel workspace error: {exc}",
    )


class IntelSearchForm(BaseModel):
    query: str = ""
    top_k: Optional[int] = Field(default=None, ge=1, le=25)
    start: Optional[str] = None
    end: Optional[str] = None
    hours: Optional[float] = None
    filters: Optional[dict[str, Any]] = None


@router.get('/meta')
async def get_intel_meta(force: bool = Query(False), user=Depends(get_verified_user)):
    """Return feature flags, detected schema and connectivity information."""
    service = _service()
    try:
        return await service.meta(force=force)
    except Exception as exc:
        raise _to_http_error(exc)


@router.get('/health')
async def get_intel_health(user=Depends(get_verified_user)):
    config = get_config()
    if not config.enabled:
        return {'enabled': False, 'ok': False}
    if config.demo:
        return {'enabled': True, 'ok': True, 'source': 'demo'}
    try:
        meta = await IntelService(config).meta(force=True)
    except Exception as exc:  # health must never raise
        return {'enabled': True, 'ok': False, 'source': 'elasticsearch', 'error': str(exc)}
    es = meta.get('elasticsearch') or {}
    return {
        'enabled': True,
        'ok': bool(es.get('connected')),
        'source': 'elasticsearch',
        'error': es.get('error'),
        'doc_count': es.get('doc_count'),
    }


@router.get('/flights')
async def get_intel_flights(
    start: Optional[str] = Query(None, description='ISO-8601 range start'),
    end: Optional[str] = Query(None, description='ISO-8601 range end'),
    hours: Optional[float] = Query(None, description='Lookback window in hours (when start is omitted)'),
    q: str = Query('', description='Free text filter (callsign, route, status, ...)'),
    size: Optional[int] = Query(None, ge=1, le=2000),
    user=Depends(get_verified_user),
):
    """Latest known state of each aircraft in the requested time window."""
    service = _service()
    try:
        return await service.flights(start=start, end=end, hours=hours, query=q, size=size)
    except Exception as exc:
        raise _to_http_error(exc)


@router.get('/flights/{identifier}/trajectory')
async def get_intel_trajectory(
    identifier: str,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    hours: Optional[float] = Query(None),
    user=Depends(get_verified_user),
):
    """Full trajectory (``trajectory`` field or per-document positions) of one aircraft."""
    service = _service()
    try:
        return await service.trajectory(identifier, start=start, end=end, hours=hours)
    except Exception as exc:
        raise _to_http_error(exc)


@router.post('/search')
async def post_intel_search(form_data: IntelSearchForm, user=Depends(get_verified_user)):
    """Search the Elasticsearch index and return trimmed documents for RAG."""
    service = _service()
    try:
        return await service.search(
            form_data.query,
            top_k=form_data.top_k,
            start=form_data.start,
            end=form_data.end,
            hours=form_data.hours,
            filters=form_data.filters,
        )
    except Exception as exc:
        raise _to_http_error(exc)
