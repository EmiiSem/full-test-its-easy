from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import NAME_PREFIX, settings
from app.database import get_db
from app.draft import (
    DraftError,
    add_local_offer,
    cancel_draft,
    draft_offers,
    offer_draft,
    push_draft,
    remove_local_offer,
    restore_local_offer,
    seed_created_offer,
    sync_from_keitaro,
    toggle_pin,
)
from app.keitaro import KeitaroClient, KeitaroError
from app.models import CampaignRecord
from app.shares import make_alias, parse_geos

app = FastAPI(title="Keitaro wrapper", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

keitaro = KeitaroClient(settings.keitaro_base_url, settings.keitaro_api_key)


@app.exception_handler(KeitaroError)
def handle_keitaro_error(_: Any, exc: KeitaroError) -> JSONResponse:
    status = exc.status if 400 <= exc.status < 600 else 502
    return JSONResponse(status_code=status, content={"detail": exc.message})


@app.exception_handler(DraftError)
def handle_draft_error(_: Any, exc: DraftError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


class CreateCampaignIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    geos: str = Field(min_length=2, max_length=200)
    offer_id: int = Field(gt=0)
    domain_id: int = Field(gt=0)
    group_id: int = Field(gt=0)
    traffic_source_id: int = Field(gt=0)


class AddOfferIn(BaseModel):
    offer_id: int = Field(gt=0)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/catalog")
def catalog() -> dict[str, Any]:
    domains = [
        {
            "id": item["id"],
            "name": item.get("name"),
            "is_ssl": bool(item.get("is_ssl")),
            "state": item.get("state"),
        }
        for item in keitaro.list_domains()
    ]
    groups = [
        {"id": item["id"], "name": item.get("name")}
        for item in keitaro.list_groups()
    ]
    sources = [
        {"id": item["id"], "name": item.get("name")}
        for item in keitaro.list_sources()
    ]
    offers = [
        {
            "id": item["id"],
            "name": item.get("name") or f"Offer {item['id']}",
            "country": item.get("country") or [],
            "state": item.get("state"),
        }
        for item in keitaro.list_offers()
        if item.get("state") != "deleted"
    ]
    offers.sort(key=lambda item: item["name"].lower())
    return {
        "domains": domains,
        "groups": groups,
        "traffic_sources": sources,
        "offers": offers,
    }


@app.get("/api/campaigns")
def list_campaigns(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    local = {
        record.keitaro_campaign_id: record
        for record in db.scalars(select(CampaignRecord)).all()
    }
    campaigns = []
    for item in keitaro.list_campaigns():
        if item.get("state") == "deleted":
            continue
        record = local.get(item["id"])
        campaigns.append(
            {
                "id": item["id"],
                "name": item.get("name"),
                "alias": item.get("alias"),
                "state": item.get("state"),
                "domain_id": item.get("domain_id"),
                "group_id": item.get("group_id"),
                "traffic_source_id": item.get("traffic_source_id"),
                "created_here": record is not None,
            }
        )
    campaigns.sort(key=lambda item: item["id"], reverse=True)
    return campaigns


@app.post("/api/campaigns", status_code=201)
def create_campaign(
    body: CreateCampaignIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    name = " ".join(body.name.split())
    if not name.startswith(NAME_PREFIX):
        raise HTTPException(
            status_code=422,
            detail=f"Название должно начинаться с {NAME_PREFIX}",
        )
    try:
        geos = parse_geos(body.geos)
        alias = make_alias(name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    catalog = keitaro.list_offers()
    known_offers = {item["id"] for item in catalog}
    if body.offer_id not in known_offers:
        raise HTTPException(status_code=422, detail="Оффер с таким ID не найден в Keitaro")

    campaign = keitaro.create_campaign(
        {
            "name": name,
            "alias": alias,
            "type": "position",
            "state": "active",
            "domain_id": body.domain_id,
            "group_id": body.group_id,
            "traffic_source_id": body.traffic_source_id,
            "cost_type": "CPC",
            "cost_value": 0,
            "cost_currency": "USD",
            "cost_auto": True,
        }
    )
    campaign_id = campaign["id"]
    try:
        google_stream = keitaro.create_stream(
            {
                "campaign_id": campaign_id,
                "type": "regular",
                "name": "Google",
                "position": 1,
                "schema": "redirect",
                "action_type": "http",
                "action_payload": "https://google.com",
                "state": "active",
                "collect_clicks": True,
                "filter_or": False,
                "filters": [
                    {"name": "country", "mode": "accept", "payload": geos}
                ],
                "landings": [],
                "offers": [],
            }
        )
        offer_stream = keitaro.create_stream(
            {
                "campaign_id": campaign_id,
                "type": "regular",
                "name": "Offers",
                "position": 2,
                "schema": "landings",
                "action_type": "http",
                "action_payload": "",
                "state": "active",
                "collect_clicks": True,
                "filter_or": False,
                "filters": [],
                "landings": [],
                "offers": [
                    {"offer_id": body.offer_id, "share": 100, "state": "active"}
                ],
            }
        )
    except KeitaroError:
        keitaro.delete_campaign(campaign_id)
        raise

    record = CampaignRecord(
        keitaro_campaign_id=campaign_id,
        name=name,
        alias=alias,
        geos=",".join(geos),
        offer_id=body.offer_id,
        domain_id=body.domain_id,
        group_id=body.group_id,
        traffic_source_id=body.traffic_source_id,
        google_stream_id=google_stream["id"],
        offer_stream_id=offer_stream["id"],
    )
    db.add(record)
    db.commit()
    seed_created_offer(db, campaign_id, offer_stream["id"], body.offer_id, catalog)
    return campaign_detail(campaign_id, db)


@app.get("/api/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    return campaign_detail(campaign_id, db)


@app.post("/api/campaigns/{campaign_id}/fetch")
def fetch_streams(campaign_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    remote = offer_stream(campaign_id)
    sync_from_keitaro(db, keitaro, campaign_id, remote)
    return campaign_detail(campaign_id, db)


@app.post("/api/campaigns/{campaign_id}/push")
def push_streams(campaign_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    draft = require_draft(db, campaign_id)
    if draft.dirty:
        push_draft(db, keitaro, draft)
    return campaign_detail(campaign_id, db)


@app.post("/api/campaigns/{campaign_id}/cancel")
def cancel_streams(campaign_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    cancel_draft(db, require_draft(db, campaign_id))
    return campaign_detail(campaign_id, db)


@app.post("/api/campaigns/{campaign_id}/offers")
def add_offer(
    campaign_id: int,
    body: AddOfferIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    draft = require_draft(db, campaign_id)
    add_local_offer(db, draft, body.offer_id, keitaro.list_offers())
    return campaign_detail(campaign_id, db)


@app.delete("/api/campaigns/{campaign_id}/offers/{offer_id}")
def remove_offer(
    campaign_id: int,
    offer_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    remove_local_offer(db, require_draft(db, campaign_id), offer_id)
    return campaign_detail(campaign_id, db)


@app.post("/api/campaigns/{campaign_id}/offers/{offer_id}/restore")
def restore_offer(
    campaign_id: int,
    offer_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    restore_local_offer(db, require_draft(db, campaign_id), offer_id)
    return campaign_detail(campaign_id, db)


@app.post("/api/campaigns/{campaign_id}/offers/{offer_id}/pin")
def pin_offer(
    campaign_id: int,
    offer_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    toggle_pin(db, require_draft(db, campaign_id), offer_id)
    return campaign_detail(campaign_id, db)


def require_draft(db: Session, campaign_id: int) -> Any:
    draft = offer_draft(db, campaign_id)
    if draft is None:
        remote = offer_stream(campaign_id)
        draft = sync_from_keitaro(db, keitaro, campaign_id, remote)
    return draft


def offer_stream(campaign_id: int) -> dict[str, Any]:
    _google, offers = split_streams(keitaro.list_streams(campaign_id))
    if offers is None:
        raise HTTPException(
            status_code=422,
            detail="У кампании нет потока с офферами",
        )
    return offers


def campaign_detail(campaign_id: int, db: Session) -> dict[str, Any]:
    campaign = keitaro.get_campaign(campaign_id)
    streams = keitaro.list_streams(campaign_id)
    google, offers = split_streams(streams)
    draft = None
    if offers is not None:
        draft = offer_draft(db, campaign_id)
        if draft is None:
            draft = sync_from_keitaro(db, keitaro, campaign_id, offers)
    domain = next(
        (item for item in keitaro.list_domains() if item["id"] == campaign.get("domain_id")),
        None,
    )
    offer_flow = flow_view(offers, {})
    if offer_flow is not None:
        offer_flow["dirty"] = bool(draft.dirty) if draft else False
        if draft is not None:
            offer_flow["offers"] = draft_offers(db, draft)
    root = settings.keitaro_base_url.rstrip("/")
    if root.endswith("/admin"):
        root = root[: -len("/admin")]
    return {
        "id": campaign["id"],
        "name": campaign.get("name"),
        "alias": campaign.get("alias"),
        "state": campaign.get("state"),
        "domain_id": campaign.get("domain_id"),
        "group_id": campaign.get("group_id"),
        "traffic_source_id": campaign.get("traffic_source_id"),
        "tracking_url": tracking_url(domain, campaign.get("alias")),
        "admin_url": f"{root}/admin/#!/campaigns/{campaign['id']}",
        "google_flow": flow_view(google, {}),
        "offer_flow": offer_flow,
    }


def tracking_url(domain: dict[str, Any] | None, alias: str | None) -> str | None:
    if not domain or not alias or not domain.get("name"):
        return None
    scheme = "https" if domain.get("is_ssl") else "http"
    return f"{scheme}://{domain['name']}/{alias}"


def split_streams(
    streams: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    google = None
    named_offers = None
    with_offers = None
    landings = None
    for stream in streams:
        if stream.get("state") == "deleted":
            continue
        payload = (stream.get("action_payload") or "").lower()
        if stream.get("schema") == "redirect" and "google" in payload:
            google = stream
            continue
        if stream.get("name") == "Offers":
            named_offers = stream
        if stream.get("offers") and with_offers is None:
            with_offers = stream
        if stream.get("schema") == "landings" and landings is None:
            landings = stream
    return google, named_offers or with_offers or landings


def flow_view(
    stream: dict[str, Any] | None,
    offer_names: dict[int, dict[str, Any]],
) -> dict[str, Any] | None:
    if stream is None:
        return None
    countries: list[str] = []
    for item in stream.get("filters") or []:
        if item.get("name") == "country" and item.get("mode") == "accept":
            payload = item.get("payload") or []
            if isinstance(payload, list):
                countries.extend(str(code) for code in payload)
    rows = []
    for item in stream.get("offers") or []:
        if item.get("state") == "deleted":
            continue
        source = offer_names.get(item["offer_id"], {})
        rows.append(
            {
                "relation_id": item.get("id"),
                "offer_id": item["offer_id"],
                "name": source.get("name") or f"Offer {item['offer_id']}",
                "share": item.get("share") or 0,
                "state": item.get("state") or "active",
                "pinned": False,
                "country": source.get("country") or [],
            }
        )
    return {
        "id": stream["id"],
        "name": stream.get("name"),
        "flow_schema": stream.get("schema"),
        "action_type": stream.get("action_type"),
        "action_payload": stream.get("action_payload") or "",
        "countries": countries,
        "dirty": False,
        "offers": rows,
    }
