"""Preview or apply the digest-bound II/2026 assistential historical import."""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministically preview or apply the II/2026 historical assistential import."
    )
    parser.add_argument("mode", choices=("preview", "apply"))
    for name in ("designation", "curriculum", "enrollment", "profiles", "decisions"):
        parser.add_argument(f"--{name}", type=Path, required=True, metavar="PATH")
        parser.add_argument(f"--{name}-sha256", required=True, metavar="SHA256")
    parser.add_argument("--actor-ci", required=True)
    parser.add_argument(
        "--policy",
        required=True,
        choices=("historical_availability_not_recorded",),
    )
    parser.add_argument("--effective-date", type=date.fromisoformat, default=date(2026, 8, 20))
    parser.add_argument("--historical-availability-unrecorded", action="store_true")
    parser.add_argument("--expected-digest", help="Required in apply mode")
    return parser


def _inputs(args: argparse.Namespace):
    from app.services.historical_assistential_import import ImportInputs

    names = ("designation", "curriculum", "enrollment", "profiles", "decisions")
    return ImportInputs(
        **{name: getattr(args, name) for name in names},
        expected_hashes={name: getattr(args, f"{name}_sha256") for name in names},
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.mode == "apply" and not args.expected_digest:
        _parser().error("apply requires --expected-digest")
    from app.database import SessionLocal
    from app.services.historical_assistential_import import (
        HistoricalImportError,
        apply_import,
        build_preview,
        safe_preview,
    )

    db = SessionLocal()
    try:
        kwargs = {
            "actor_ci": args.actor_ci,
            "policy": args.policy,
            "effective_date": args.effective_date,
            "historical_availability_unrecorded": args.historical_availability_unrecorded,
        }
        if args.mode == "preview":
            output = safe_preview(build_preview(db, _inputs(args), **kwargs))
            db.rollback()
        else:
            with db.begin():
                output = apply_import(
                    db, _inputs(args), expected_digest=args.expected_digest, **kwargs
                )
        print(json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0
    except HistoricalImportError as exc:
        db.rollback()
        print(json.dumps({"error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    except Exception:
        db.rollback()
        print(json.dumps({"error": "Import failed; the transaction was rolled back"}), file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
