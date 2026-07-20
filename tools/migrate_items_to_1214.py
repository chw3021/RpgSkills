#!/usr/bin/env python3
"""
Convert pre-1.21.4 item model overrides (models/item/*.json) into
1.21.4+ / 26.x item definitions (assets/minecraft/items/*.json).

  python tools/migrate_items_to_1214.py --dry-run
  python tools/migrate_items_to_1214.py --apply --stage simple
  python tools/migrate_items_to_1214.py --apply --stage complex
  python tools/migrate_items_to_1214.py --apply --stage all
  python tools/migrate_items_to_1214.py --apply --stage all --strip-overrides

Stages:
  simple  - CMD-only items (sword, axe, shears, ...)
  complex - bow / crossbow / fishing_rod (state predicates)
  all     - both
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODELS_ITEM = ROOT / "assets" / "minecraft" / "models" / "item"
ITEMS_DIR = ROOT / "assets" / "minecraft" / "items"

SIMPLE_ITEMS = {
    "blaze_rod",
    "diamond_sword",
    "globe_banner_pattern",
    "mace",
    "netherite_axe",
    "netherite_hoe",
    "netherite_pickaxe",
    "netherite_shovel",
    "netherite_spear",
    "netherite_sword",
    "shears",
    "trident",
}
COMPLEX_ITEMS = {"bow", "crossbow", "fishing_rod"}


def model_ref(path: str) -> dict[str, Any]:
    return {"type": "model", "model": path}


def normalize_model_path(path: str) -> str:
    if path.startswith("minecraft:"):
        return path[len("minecraft:") :]
    return path


def group_overrides(
    overrides: list[dict[str, Any]],
) -> dict[int | None, list[dict[str, Any]]]:
    groups: dict[int | None, list[dict[str, Any]]] = defaultdict(list)
    for ov in overrides:
        pred = ov.get("predicate") or {}
        cmd = pred.get("custom_model_data")
        if cmd is not None:
            cmd = int(cmd)
        groups[cmd].append(
            {
                "predicate": pred,
                "model": normalize_model_path(ov["model"]),
            }
        )
    return groups


def build_simple_dispatch(
    groups: dict[int | None, list[dict[str, Any]]],
    fallback_model: str,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for cmd in sorted(k for k in groups if k is not None):
        model_path = groups[cmd][0]["model"]
        entries.append(
            {
                "threshold": cmd,
                "model": model_ref(model_path),
            }
        )
    return {
        "model": {
            "type": "range_dispatch",
            "property": "custom_model_data",
            "entries": entries,
            "fallback": model_ref(fallback_model),
        }
    }


def build_bow_states(rows: list[dict[str, Any]], idle_fallback: str) -> dict[str, Any]:
    idle = idle_fallback
    pull0 = pull1 = pull2 = None
    for row in rows:
        pred = row["predicate"]
        path = row["model"]
        if pred.get("pulling") == 1:
            pull = pred.get("pull")
            if pull is None:
                pull0 = path
            elif float(pull) >= 0.9:
                pull2 = path
            elif float(pull) >= 0.65:
                pull1 = path
            else:
                pull0 = path
        else:
            idle = path

    pull_entries: list[dict[str, Any]] = []
    if pull1:
        pull_entries.append({"threshold": 0.65, "model": model_ref(pull1)})
    if pull2:
        pull_entries.append({"threshold": 0.9, "model": model_ref(pull2)})

    on_true: dict[str, Any]
    if pull0 or pull_entries:
        on_true = {
            "type": "range_dispatch",
            "property": "use_duration",
            "scale": 0.05,
            "entries": pull_entries,
            "fallback": model_ref(pull0 or idle),
        }
    else:
        on_true = model_ref(idle)

    return {
        "type": "condition",
        "property": "using_item",
        "on_false": model_ref(idle),
        "on_true": on_true,
    }


def build_crossbow_states(
    rows: list[dict[str, Any]], idle_fallback: str
) -> dict[str, Any]:
    idle = idle_fallback
    pull0 = pull1 = pull2 = None
    arrow = firework = None
    for row in rows:
        pred = row["predicate"]
        path = row["model"]
        if pred.get("charged") == 1:
            if pred.get("firework") == 1:
                firework = path
            else:
                arrow = path
        elif pred.get("pulling") == 1:
            pull = pred.get("pull")
            if pull is None:
                pull0 = path
            elif float(pull) >= 1.0:
                pull2 = path
            elif float(pull) >= 0.58:
                pull1 = path
            else:
                pull0 = path
        else:
            idle = path

    pull_entries: list[dict[str, Any]] = []
    if pull1:
        pull_entries.append({"threshold": 0.58, "model": model_ref(pull1)})
    if pull2:
        pull_entries.append({"threshold": 1.0, "model": model_ref(pull2)})

    if pull0 or pull_entries:
        charging: dict[str, Any] = {
            "type": "range_dispatch",
            "property": "crossbow/pull",
            "entries": pull_entries,
            "fallback": model_ref(pull0 or idle),
        }
    else:
        charging = model_ref(idle)

    uncharged: dict[str, Any] = {
        "type": "condition",
        "property": "using_item",
        "on_false": model_ref(idle),
        "on_true": charging,
    }

    cases: list[dict[str, Any]] = []
    if arrow:
        cases.append({"when": "arrow", "model": model_ref(arrow)})
    if firework:
        cases.append({"when": "rocket", "model": model_ref(firework)})

    if cases:
        return {
            "type": "select",
            "property": "charge_type",
            "cases": cases,
            "fallback": uncharged,
        }
    return uncharged


def build_fishing_rod_states(
    rows: list[dict[str, Any]], idle_fallback: str
) -> dict[str, Any]:
    idle = idle_fallback
    cast = None
    for row in rows:
        pred = row["predicate"]
        path = row["model"]
        if pred.get("cast") == 1:
            cast = path
        else:
            idle = path
    if cast is None:
        return model_ref(idle)
    return {
        "type": "condition",
        "property": "fishing_rod/cast",
        "on_false": model_ref(idle),
        "on_true": model_ref(cast),
    }


def build_complex_dispatch(
    item_name: str,
    groups: dict[int | None, list[dict[str, Any]]],
    fallback_model: str,
) -> dict[str, Any]:
    vanilla_rows = groups.get(None, [])
    if item_name == "bow":
        fallback = build_bow_states(vanilla_rows, fallback_model)
        state_builder = build_bow_states
    elif item_name == "crossbow":
        fallback = build_crossbow_states(vanilla_rows, fallback_model)
        state_builder = build_crossbow_states
    elif item_name == "fishing_rod":
        fallback = build_fishing_rod_states(vanilla_rows, fallback_model)
        state_builder = build_fishing_rod_states
    else:
        raise ValueError(f"Unsupported complex item: {item_name}")

    entries: list[dict[str, Any]] = []
    for cmd in sorted(k for k in groups if k is not None):
        entries.append(
            {
                "threshold": cmd,
                "model": state_builder(groups[cmd], groups[cmd][0]["model"]),
            }
        )

    return {
        "model": {
            "type": "range_dispatch",
            "property": "custom_model_data",
            "entries": entries,
            "fallback": fallback,
        }
    }


def strip_overrides_from_model(path: Path, dry: bool) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "overrides" not in data:
        return False
    del data["overrides"]
    if not dry:
        path.write_text(
            json.dumps(data, indent=4, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return True


def convert_item(item_name: str, dry: bool, strip_overrides: bool) -> str:
    src = MODELS_ITEM / f"{item_name}.json"
    if not src.is_file():
        raise FileNotFoundError(src)

    data = json.loads(src.read_text(encoding="utf-8"))
    overrides = data.get("overrides") or []
    if not overrides:
        return f"skip {item_name}: no overrides"

    groups = group_overrides(overrides)
    fallback_model = f"item/{item_name}"

    if item_name in COMPLEX_ITEMS:
        out = build_complex_dispatch(item_name, groups, fallback_model)
        kind = "complex"
    else:
        out = build_simple_dispatch(groups, fallback_model)
        kind = "simple"

    dest = ITEMS_DIR / f"{item_name}.json"
    cmd_count = len([k for k in groups if k is not None])
    if not dry:
        ITEMS_DIR.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            json.dumps(out, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if strip_overrides:
            strip_overrides_from_model(src, dry=False)

    action = "would write" if dry else "wrote"
    strip_note = ""
    if strip_overrides:
        strip_note = ", strip overrides" if not dry else ", would strip overrides"
    return f"{action} items/{item_name}.json ({kind}, {cmd_count} CMD){strip_note}"


def select_items(stage: str) -> list[str]:
    if stage == "simple":
        return sorted(SIMPLE_ITEMS)
    if stage == "complex":
        return sorted(COMPLEX_ITEMS)
    if stage == "all":
        return sorted(SIMPLE_ITEMS | COMPLEX_ITEMS)
    raise ValueError(f"Unknown stage: {stage}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="Write files (default: dry-run)")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only (default when --apply is omitted)",
    )
    ap.add_argument(
        "--stage",
        choices=("simple", "complex", "all"),
        default="all",
        help="Which item groups to convert",
    )
    ap.add_argument(
        "--strip-overrides",
        action="store_true",
        help="Remove overrides from models/item/<item>.json after writing items/",
    )
    ap.add_argument(
        "--only",
        nargs="+",
        help="Convert only these item names (e.g. diamond_sword bow)",
    )
    args = ap.parse_args()
    dry = not args.apply

    items = args.only if args.only else select_items(args.stage)
    print(f"{'DRY-RUN' if dry else 'APPLY'}: stage={args.stage}, items={len(items)}")
    print(f"  models: {MODELS_ITEM}")
    print(f"  items:  {ITEMS_DIR}")
    print()

    for name in items:
        try:
            print(f"  {convert_item(name, dry=dry, strip_overrides=args.strip_overrides)}")
        except Exception as exc:  # noqa: BLE001 - report per-item and continue
            print(f"  ERROR {name}: {exc}")

    if dry:
        print("\nApply: python tools/migrate_items_to_1214.py --apply --stage all --strip-overrides")


if __name__ == "__main__":
    main()
