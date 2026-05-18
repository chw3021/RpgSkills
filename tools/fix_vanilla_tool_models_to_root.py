#!/usr/bin/env python3
"""
Minecraft는 도끼·검 등의 베이스 아이템 모델을 반드시
  assets/minecraft/models/item/<바닐라아이템id>.json
에 둔다 (예: diamond_sword.json). 재구조화로 sword/diamond/ 아래로
옮겨진 베이스 파일만 루트로 되돌리고, layer0은 바닐라 텍스처로 맞춘다.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_ITEM = ROOT / "assets" / "minecraft" / "models" / "item"

TIERS = ("wooden", "stone", "copper", "iron", "golden", "diamond", "netherite")
TOOLS = ("sword", "axe", "pickaxe", "shovel", "hoe")


def main() -> None:
    moved = 0
    for tool in TOOLS:
        for tier in TIERS:
            stem = f"{tier}_{tool}"
            nested = MODEL_ITEM / tool / tier / f"{stem}.json"
            if not nested.is_file():
                continue
            dst = MODEL_ITEM / f"{stem}.json"
            data = json.loads(nested.read_text(encoding="utf-8"))
            if "textures" in data and isinstance(data["textures"], dict):
                data["textures"]["layer0"] = f"minecraft:item/{stem}"
            dst.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
            nested.unlink()
            moved += 1
            # 빈 폴더 정리
            p = nested.parent
            while p != MODEL_ITEM and p.is_dir() and not any(p.iterdir()):
                p.rmdir()
                p = p.parent
    print(f"Restored {moved} vanilla tool models to models/item/")


if __name__ == "__main__":
    main()
