from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping

TALENT_LEVELS = ("1", "4", "7", "10", "13", "16", "20")
DEFAULT_TIER_ORDER = TALENT_LEVELS
TALENT_LEVELS = list(DEFAULT_TIER_ORDER)
TALENT_STRING_PATTERN = re.compile(r"^\[T([0-9]{7}),([A-Za-z0-9]+)\]$")


@dataclass(frozen=True)
class TalentBuildHero:
    slug: str
    name: str
    export_token: str


@dataclass(frozen=True)
class TalentBuildTierOption:
    index: int
    title: str
    description: str = ""
    hotkey: str = ""


@dataclass(frozen=True)
class TalentBuildTier:
    level: str
    options: list[TalentBuildTierOption]


@dataclass(frozen=True)
class TalentBuildData:
    hero: TalentBuildHero
    tiers: list[TalentBuildTier]


@dataclass(frozen=True)
class ParsedTalentString:
    hero_token: str
    selections: dict[str, int]


def resolve_hero_token(hero_record: Mapping[str, object]) -> str:
    for key in ("build_copy_name", "alt_name", "name", "short_name", "slug"):
        raw_value = str(hero_record.get(key) or "").strip()
        token = "".join(char for char in raw_value if char.isalnum())
        if token:
            return token
    raise ValueError("hero record is missing an export token")


def build_talent_string(
    hero_token: str,
    selections: Mapping[str, int | str],
    *,
    tier_order: Iterable[str] = DEFAULT_TIER_ORDER,
) -> str:
    normalized_token = str(hero_token or "").strip()
    if not normalized_token:
        raise ValueError("hero_token is required")

    digits: list[str] = []
    for tier in tier_order:
        raw_value = selections.get(str(tier), 0)
        try:
            value = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"selection for tier {tier} must be an integer") from exc
        if value < 0 or value > 9:
            raise ValueError(f"selection for tier {tier} must be between 0 and 9")
        digits.append(str(value))
    return f"[T{''.join(digits)},{normalized_token}]"


def build_talent_string_for_hero(
    hero_record: Mapping[str, object],
    selections: Mapping[str, int | str],
    *,
    tier_order: Iterable[str] = DEFAULT_TIER_ORDER,
) -> str:
    return build_talent_string(resolve_hero_token(hero_record), selections, tier_order=tier_order)


def parse_talent_string(value: str, *, tier_order: Iterable[str] = DEFAULT_TIER_ORDER) -> ParsedTalentString:
    raw_value = str(value or "").strip()
    match = TALENT_STRING_PATTERN.fullmatch(raw_value)
    if match is None:
        raise ValueError("talent string must use HOTS format like [T3211221,Leoric]")

    digits, hero_token = match.groups()
    levels = [str(level) for level in tier_order]
    if len(digits) != len(levels):
        raise ValueError(f"talent string must include exactly {len(levels)} tier digits")

    selections = {level: int(digit) for level, digit in zip(levels, digits)}
    return ParsedTalentString(hero_token=hero_token, selections=selections)
