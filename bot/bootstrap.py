from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

DEFAULT_NEWS_INDEX = Path("news") / "index.json"
DEFAULT_HEROES_MANIFEST = Path("heroesprofile") / "manifest.json"


@dataclass(frozen=True)
class BootstrapDecision:
    should_sync: bool
    reason: str
    news_index_exists: bool
    heroes_manifest_exists: bool


def parse_bool_env(name: str, raw_value: str | None, *, default: bool) -> bool:
    if raw_value is None or raw_value.strip() == "":
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def decide_bootstrap_sync(
    env: Mapping[str, str] | None = None,
    *,
    news_index_path: Path = DEFAULT_NEWS_INDEX,
    heroes_manifest_path: Path = DEFAULT_HEROES_MANIFEST,
) -> BootstrapDecision:
    values = env if env is not None else os.environ
    skip = parse_bool_env("BOOTSTRAP_SYNC_SKIP", values.get("BOOTSTRAP_SYNC_SKIP"), default=False)
    force = parse_bool_env("BOOTSTRAP_SYNC_FORCE", values.get("BOOTSTRAP_SYNC_FORCE"), default=False)
    on_empty = parse_bool_env("BOOTSTRAP_SYNC_ON_EMPTY", values.get("BOOTSTRAP_SYNC_ON_EMPTY"), default=True)

    news_exists = news_index_path.exists()
    heroes_exists = heroes_manifest_path.exists()

    if skip:
        return BootstrapDecision(
            should_sync=False,
            reason="bootstrap disabled by BOOTSTRAP_SYNC_SKIP",
            news_index_exists=news_exists,
            heroes_manifest_exists=heroes_exists,
        )

    if force:
        return BootstrapDecision(
            should_sync=True,
            reason="bootstrap forced by BOOTSTRAP_SYNC_FORCE",
            news_index_exists=news_exists,
            heroes_manifest_exists=heroes_exists,
        )

    if on_empty and (not news_exists or not heroes_exists):
        return BootstrapDecision(
            should_sync=True,
            reason="bootstrap required because local cache is incomplete",
            news_index_exists=news_exists,
            heroes_manifest_exists=heroes_exists,
        )

    if not on_empty:
        reason = "bootstrap disabled because BOOTSTRAP_SYNC_ON_EMPTY is false"
    else:
        reason = "bootstrap skipped because local cache is already present"

    return BootstrapDecision(
        should_sync=False,
        reason=reason,
        news_index_exists=news_exists,
        heroes_manifest_exists=heroes_exists,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap sync decision helper")
    parser.add_argument(
        "--format",
        choices=("status", "reason"),
        default="status",
        help="output format",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    load_dotenv()
    try:
        decision = decide_bootstrap_sync()
    except ValueError as exc:
        parser.exit(status=2, message=f"{exc}\n")

    if args.format == "reason":
        print(decision.reason)
    else:
        print("run" if decision.should_sync else "skip")

    return 0 if decision.should_sync else 1


if __name__ == "__main__":
    raise SystemExit(main())
