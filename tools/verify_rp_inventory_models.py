#!/usr/bin/env python3
"""바닐라 도구 모델이 models/item 루트에 있는지, bow/crossbow 등 핵심 파일 존재 확인."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITEM = ROOT / "assets" / "minecraft" / "models" / "item"

TOOLS = ("sword", "axe", "pickaxe", "shovel", "hoe")
MATS = ("wooden", "stone", "copper", "iron", "golden", "diamond", "netherite")

ROOT_MODELS = (
    "bow.json",
    "crossbow.json",
    "fishing_rod.json",
    "trident.json",
    "shears.json",
    "mace.json",
    "blaze_rod.json",
    "globe_banner_pattern.json",
)


def main() -> None:
    missing: list[str] = []
    for name in ROOT_MODELS:
        if not (ITEM / name).is_file():
            missing.append(name)
    for mat in MATS:
        for t in TOOLS:
            stem = f"{mat}_{t}"
            if (ITEM / f"{stem}.json").is_file():
                continue
            missing.append(f"{stem}.json (optional if unused in pack)")
    # 실제로 팩에 포함된 것만 엄격 검사
    required = [
        "diamond_sword.json",
        "netherite_sword.json",
        "bow.json",
        "blaze_rod.json",
        "globe_banner_pattern.json",
        "shears.json",
    ]
    strict = [f for f in required if not (ITEM / f).is_file()]
    print("Strict missing:", strict or "none")
    print("Sample optional missing (first 10):", [m for m in missing if m.endswith(".json")][:10])


if __name__ == "__main__":
    main()
