"""Read endpoints that feed the dashboards. All require at least 'viewer'."""
from fastapi import APIRouter, Depends, Request

from ..catalog import catalog_snapshot
from ..pdc_client import client
from ..recommend import recommend
from ..security import Principal
from ._auth import json_body, require

router = APIRouter(prefix="/api", tags=["analytics"])


@router.post("/facets")
async def facets(request: Request, principal: Principal = Depends(require("viewer"))):
    body = await json_body(request)
    return client.facets(body.get("term", "*"), body.get("facets"))


@router.post("/search")
async def search(request: Request, principal: Principal = Depends(require("viewer"))):
    body = await json_body(request)
    return client.search(body.get("term", "*"), body.get("facets"),
                         body.get("page", 1), body.get("perPage", 30))


@router.get("/trust-distribution")
def trust(term: str = "*", principal: Principal = Depends(require("viewer"))):
    return client.trust_distribution(term)


@router.get("/snapshot")
def snapshot(principal: Principal = Depends(require("viewer"))):
    """Catalog state — works offline in demo mode."""
    return catalog_snapshot()


@router.get("/recommend")
def recommend_route(request: Request, principal: Principal = Depends(require("viewer"))):
    args = request.query_params
    scope = args.get("scope") or None
    # section (a.k.a. category) makes the suggestions Analytics-section-aware
    section = args.get("section") or args.get("category") or None
    return recommend(catalog_snapshot(), scope, section)
