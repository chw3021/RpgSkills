#!/usr/bin/env python3
"""팩이 대상 마인크래프트 클라이언트 jar와 맞는지 확인.

1. 팩이 참조하는 모델/텍스처(items 정의의 model, 모델의 parent·textures)가
   팩 또는 대상 jar에 존재하는지 검사한다.
2. 기준 jar를 주면, 기준 버전에서 바닐라 파일을 덮어쓰던 팩 파일 중
   대상 버전에서 바닐라 경로가 사라진(덮어쓰기가 무효가 된) 파일을 찾는다.

사용법: python tools/verify_pack_against_client.py <target-client.jar> [<baseline-client.jar>]
문제가 있으면 종료 코드 1.
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MC = ROOT / "assets" / "minecraft"


def jar_assets(jar: str) -> set[str]:
    with zipfile.ZipFile(jar) as z:
        return {n[len("assets/minecraft/"):] for n in z.namelist() if n.startswith("assets/minecraft/")}


def pack_assets() -> set[str]:
    return {p.relative_to(MC).as_posix() for p in MC.rglob("*") if p.is_file() and p.parts[len(MC.parts)] != "optifine"}


def resource_path(ref: str, kind: str) -> str | None:
    """'minecraft:item/bow' 같은 참조를 models/... 또는 textures/... 경로로 바꾼다. 다른 네임스페이스·내장 모델은 None."""
    ns, _, path = ref.rpartition(":")
    if ns not in ("", "minecraft") or path.startswith("builtin/"):
        return None
    return f"models/{path}.json" if kind == "model" else f"textures/{path}.png"


def collect_refs(node, out: set[str]) -> None:
    """items 정의 트리 안의 모든 "model" 문자열 참조를 모은다."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "model" and isinstance(value, str):
                out.add(value)
            else:
                collect_refs(value, out)
    elif isinstance(node, list):
        for value in node:
            collect_refs(value, out)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    target = jar_assets(sys.argv[1])
    pack = pack_assets()
    available = target | pack
    problems: list[str] = []

    for f in sorted(MC.glob("items/*.json")):
        refs: set[str] = set()
        collect_refs(json.loads(f.read_text(encoding="utf-8")), refs)
        for ref in refs:
            path = resource_path(ref, "model")
            if path and path not in available:
                problems.append(f"{f.relative_to(MC).as_posix()}: missing model {ref}")

    for f in sorted(MC.glob("models/**/*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        name = f.relative_to(MC).as_posix()
        parent = data.get("parent")
        if isinstance(parent, str):
            path = resource_path(parent, "model")
            if path and path not in available:
                problems.append(f"{name}: missing parent {parent}")
        for tex in (data.get("textures") or {}).values():
            if isinstance(tex, str) and not tex.startswith("#"):
                path = resource_path(tex, "texture")
                if path and path not in available:
                    problems.append(f"{name}: missing texture {tex}")

    if len(sys.argv) > 2:
        baseline = jar_assets(sys.argv[2])
        for path in sorted(pack & baseline - target):
            problems.append(f"{path}: overrides a vanilla file that no longer exists in the target version")

    for p in problems:
        print(p)
    print(f"Checked {len(pack)} pack files against {Path(sys.argv[1]).name}: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
