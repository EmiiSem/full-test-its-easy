import re


def parse_geos(raw: str) -> list[str]:
    parts = [part for part in re.split(r"[\s,;]+", raw.strip().upper()) if part]
    if not parts or any(not re.fullmatch(r"[A-Z]{2}", part) for part in parts):
        raise ValueError(
            "Гео-коды должны быть двухбуквенными ISO, через запятую. Например: MX, AU"
        )
    unique: list[str] = []
    for part in parts:
        if part not in unique:
            unique.append(part)
    return unique


def make_alias(name: str) -> str:
    alias = re.sub(r"[^A-Za-z0-9_]+", "_", name.strip())
    alias = re.sub(r"_+", "_", alias).strip("_")
    if not alias:
        raise ValueError("Название кампании не содержит символов для идентификатора")
    return alias[:80]


def split_integer(total: int, count: int) -> list[int]:
    if count <= 0:
        return []
    base, remainder = divmod(total, count)
    first_larger = count - remainder
    return [base + (1 if index >= first_larger else 0) for index in range(count)]


def equal_shares(count: int) -> list[int]:
    return split_integer(100, count)


def redistribute(offers: list[dict]) -> None:
    """Recalculate active unpinned shares so active shares sum to 100.

    Pinned offers keep their share. Removed offers stay at 0 and are excluded
    from the sum. The integer remainder goes to the last unpinned offers,
    so three equal shares are 33, 33, 34.
    """
    active = [offer for offer in offers if offer["status"] == "active"]
    pinned = [offer for offer in active if offer["pinned"]]
    free = [offer for offer in active if not offer["pinned"]]
    pinned_sum = sum(int(offer["share"]) for offer in pinned)
    if pinned_sum > 100:
        raise ValueError("Сумма закреплённых долей больше 100")
    parts = split_integer(100 - pinned_sum, len(free))
    for offer, share in zip(free, parts, strict=True):
        offer["share"] = share
    for offer in offers:
        if offer["status"] != "active":
            offer["share"] = 0
