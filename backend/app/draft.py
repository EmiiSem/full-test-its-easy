import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.keitaro import KeitaroClient
from app.models import OfferCatalog, StreamDraft, StreamOfferDraft
from app.shares import redistribute


class DraftError(ValueError):
    pass


def remember_offers(db: Session, offers: list[dict[str, Any]]) -> None:
    known = {
        row.keitaro_offer_id: row
        for row in db.scalars(select(OfferCatalog)).all()
    }
    for offer in offers:
        country = offer.get("country") or []
        country_text = ", ".join(str(item) for item in country) if isinstance(country, list) else str(country)
        row = known.get(offer["id"])
        if row is None:
            db.add(
                OfferCatalog(
                    keitaro_offer_id=offer["id"],
                    name=offer.get("name") or f"Offer {offer['id']}",
                    country=country_text,
                )
            )
        else:
            row.name = offer.get("name") or row.name
            row.country = country_text


def offer_names(db: Session) -> dict[int, OfferCatalog]:
    return {row.keitaro_offer_id: row for row in db.scalars(select(OfferCatalog)).all()}


def offer_draft(db: Session, campaign_id: int) -> StreamDraft | None:
    return db.scalar(
        select(StreamDraft).where(
            StreamDraft.keitaro_campaign_id == campaign_id,
            StreamDraft.role == "offers",
        )
    )


def ordered_offers(stream: StreamDraft) -> list[StreamOfferDraft]:
    return sorted(stream.offers, key=lambda offer: offer.id)


def sync_from_keitaro(
    db: Session,
    keitaro: KeitaroClient,
    campaign_id: int,
    offer_stream: dict[str, Any],
) -> StreamDraft:
    catalog = keitaro.list_offers()
    remember_offers(db, catalog)
    remote = [
        item
        for item in offer_stream.get("offers") or []
        if item.get("state") != "deleted"
    ]
    remote_ids = [item["offer_id"] for item in remote]
    draft = offer_draft(db, campaign_id)
    if draft is None:
        draft = StreamDraft(
            keitaro_campaign_id=campaign_id,
            keitaro_stream_id=offer_stream["id"],
            name=offer_stream.get("name") or "Offers",
            position=offer_stream.get("position") or 0,
            role="offers",
            dirty=False,
            published_offers="[]",
        )
        db.add(draft)
        db.flush()
    draft.keitaro_stream_id = offer_stream["id"]
    draft.name = offer_stream.get("name") or draft.name
    draft.position = offer_stream.get("position") or 0
    draft.dirty = False
    local = {row.keitaro_offer_id: row for row in ordered_offers(draft)}
    for item in remote:
        row = local.get(item["offer_id"])
        if row is None:
            db.add(
                StreamOfferDraft(
                    stream_draft_id=draft.id,
                    keitaro_offer_id=item["offer_id"],
                    share=int(item.get("share") or 0),
                    pinned=False,
                    status="active",
                )
            )
        else:
            row.share = int(item.get("share") or 0)
            row.pinned = False
            row.status = "active"
    for offer_id, row in local.items():
        if offer_id not in remote_ids:
            row.status = "removed"
            row.share = 0
            row.pinned = False
    draft.published_offers = json.dumps(
        [{"offer_id": item["offer_id"], "share": int(item.get("share") or 0)} for item in remote]
    )
    db.commit()
    db.refresh(draft)
    return draft


def seed_created_offer(
    db: Session,
    campaign_id: int,
    stream_id: int,
    offer_id: int,
    catalog: list[dict[str, Any]],
) -> None:
    remember_offers(db, catalog)
    draft = StreamDraft(
        keitaro_campaign_id=campaign_id,
        keitaro_stream_id=stream_id,
        name="Offers",
        position=2,
        role="offers",
        dirty=False,
        published_offers=json.dumps([{"offer_id": offer_id, "share": 100}]),
    )
    db.add(draft)
    db.flush()
    db.add(
        StreamOfferDraft(
            stream_draft_id=draft.id,
            keitaro_offer_id=offer_id,
            share=100,
            pinned=False,
            status="active",
        )
    )
    db.commit()


def _slots(stream: StreamDraft) -> list[dict[str, Any]]:
    return [
        {
            "row": row,
            "status": row.status,
            "pinned": row.pinned,
            "share": row.share,
        }
        for row in ordered_offers(stream)
    ]


def _apply_slots(slots: list[dict[str, Any]]) -> None:
    redistribute(slots)
    for slot in slots:
        slot["row"].share = slot["share"]
        slot["row"].status = slot["status"]
        slot["row"].pinned = slot["pinned"]


def add_local_offer(db: Session, stream: StreamDraft, offer_id: int, catalog: list[dict[str, Any]]) -> None:
    remember_offers(db, catalog)
    if not any(item["id"] == offer_id for item in catalog):
        raise DraftError("Оффер с таким ID не найден в Keitaro")
    existing = next((row for row in stream.offers if row.keitaro_offer_id == offer_id), None)
    if existing and existing.status == "active":
        raise DraftError("Этот оффер уже есть в потоке")
    if existing and existing.status == "removed":
        raise DraftError("Оффер в архиве. Верните его кнопкой «Вернуть»")
    db.add(
        StreamOfferDraft(
            stream_draft_id=stream.id,
            keitaro_offer_id=offer_id,
            share=0,
            pinned=False,
            status="active",
        )
    )
    db.flush()
    db.refresh(stream)
    try:
        _apply_slots(_slots(stream))
    except ValueError as exc:
        raise DraftError(str(exc)) from exc
    stream.dirty = True
    db.commit()


def remove_local_offer(db: Session, stream: StreamDraft, offer_id: int) -> None:
    row = next((item for item in stream.offers if item.keitaro_offer_id == offer_id), None)
    if row is None or row.status != "active":
        raise DraftError("Оффер не найден в потоке кампании")
    row.status = "removed"
    row.share = 0
    row.pinned = False
    try:
        _apply_slots(_slots(stream))
    except ValueError as exc:
        raise DraftError(str(exc)) from exc
    stream.dirty = True
    db.commit()


def restore_local_offer(db: Session, stream: StreamDraft, offer_id: int) -> None:
    row = next((item for item in stream.offers if item.keitaro_offer_id == offer_id), None)
    if row is None or row.status != "removed":
        raise DraftError("В архиве нет такого оффера")
    row.status = "active"
    row.pinned = False
    try:
        _apply_slots(_slots(stream))
    except ValueError as exc:
        raise DraftError(str(exc)) from exc
    stream.dirty = True
    db.commit()


def toggle_pin(db: Session, stream: StreamDraft, offer_id: int) -> None:
    row = next((item for item in stream.offers if item.keitaro_offer_id == offer_id), None)
    if row is None or row.status != "active":
        raise DraftError("Закрепить можно только активный оффер")
    row.pinned = not row.pinned
    db.commit()


def cancel_draft(db: Session, stream: StreamDraft) -> None:
    published = json.loads(stream.published_offers or "[]")
    published_ids = {item["offer_id"] for item in published}
    shares = {item["offer_id"]: int(item["share"]) for item in published}
    for row in list(ordered_offers(stream)):
        if row.keitaro_offer_id in published_ids:
            row.status = "active"
            row.share = shares[row.keitaro_offer_id]
            row.pinned = False
        elif row.status == "active":
            db.delete(row)
        else:
            row.share = 0
            row.pinned = False
    stream.dirty = False
    db.commit()


def push_draft(db: Session, keitaro: KeitaroClient, stream: StreamDraft) -> None:
    remote = keitaro.request("GET", f"/streams/{stream.keitaro_stream_id}")
    active = [row for row in ordered_offers(stream) if row.status == "active"]
    payload = {
        "campaign_id": remote.get("campaign_id"),
        "type": remote.get("type") or "regular",
        "name": remote.get("name") or stream.name,
        "position": remote.get("position") or stream.position,
        "state": remote.get("state") or "active",
        "schema": remote.get("schema") or "landings",
        "action_type": remote.get("action_type") or "http",
        "action_payload": remote.get("action_payload") or "",
        "collect_clicks": remote.get("collect_clicks", True),
        "filter_or": remote.get("filter_or", False),
        "filters": [
            {
                "name": item.get("name"),
                "mode": item.get("mode"),
                "payload": item.get("payload") if isinstance(item.get("payload"), list) else [],
            }
            for item in remote.get("filters") or []
        ],
        "offers": [
            {"offer_id": row.keitaro_offer_id, "share": row.share, "state": "active"}
            for row in active
        ],
    }
    keitaro.update_stream(stream.keitaro_stream_id, payload)
    stream.published_offers = json.dumps(
        [{"offer_id": row.keitaro_offer_id, "share": row.share} for row in active]
    )
    stream.dirty = False
    db.commit()


def draft_offers(db: Session, stream: StreamDraft) -> list[dict[str, Any]]:
    names = offer_names(db)
    rows = []
    for row in ordered_offers(stream):
        catalog = names.get(row.keitaro_offer_id)
        country = [part.strip() for part in (catalog.country.split(",") if catalog and catalog.country else []) if part.strip()]
        rows.append(
            {
                "relation_id": row.id,
                "offer_id": row.keitaro_offer_id,
                "name": catalog.name if catalog else f"Offer {row.keitaro_offer_id}",
                "share": row.share,
                "state": row.status,
                "pinned": row.pinned,
                "country": country,
            }
        )
    return rows
