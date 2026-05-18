#!/usr/bin/env python3
"""
RPGskills 리소스팩: models/item·textures/item 루트에만 있는 파일을
  item/<무기>/<속성>/원래이름
  item/<무기>/growing/levN/원래이름
으로 옮기고, JSON·mcmeta·properties 안의 item/... 경로를 갱신합니다.

  python tools/restructure_rpgskills_pack.py --dry-run
  python tools/restructure_rpgskills_pack.py --apply

적용 전 git 커밋 권장. optifine/cit 등은 별도 검토가 필요할 수 있습니다.
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS_MC = ROOT / "assets" / "minecraft"

# (suffix, weapon_folder) — 긴 것부터 매칭
SUFFIX_RULES: list[tuple[str, str]] = [
    ("fishing_rod_cast", "fishing_rod"),
    ("crossbow_firework", "crossbow"),
    ("crossbow_arrow", "crossbow"),
    ("crossbow_pulling_2", "crossbow"),
    ("crossbow_pulling_1", "crossbow"),
    ("crossbow_pulling_0", "crossbow"),
    ("bow_pulling_2", "bow"),
    ("bow_pulling_1", "bow"),
    ("bow_pulling_0", "bow"),
    ("fishing_rod", "fishing_rod"),
    ("crossbow", "crossbow"),
    ("pickaxe", "pickaxe"),
    ("shovel", "shovel"),
    ("trident", "trident"),
    ("knuckle", "knuckle"),
    ("wand", "wand"),
    ("sword", "sword"),
    ("spear", "spear"),
    ("dagger", "dagger"),
    ("mace", "mace"),
    ("axe", "axe"),
    ("hoe", "hoe"),
    ("bow", "bow"),
]


def split_stem(stem: str) -> tuple[str, str, str] | None:
    """
    stem -> (weapon, attr_path, file_stem_for_new_location)
    attr_path: 'windy' | 'growing/lev3' 등
    """
    if re.fullmatch(
        r"(wooden|stone|copper|iron|golden|diamond|netherite)_(sword|axe|pickaxe|shovel|hoe)",
        stem,
    ):
        return None

    mlev = re.match(r"^lev([1-8])_(.+)$", stem)
    if mlev:
        lev, tail = mlev.group(1), mlev.group(2)
        for suf, weapon in SUFFIX_RULES:
            if tail == suf:
                return weapon, f"growing/lev{lev}", stem
        return None

    for suf, weapon in SUFFIX_RULES:
        suf_key = "_" + suf
        if stem.endswith(suf_key):
            prefix = stem[: -len(suf_key)]
            if not prefix:
                return None
            return weapon, prefix, stem
    return None


def old_texture_id(stem: str) -> str:
    return f"item/{stem}"


def new_texture_id(weapon: str, attr_path: str, stem: str) -> str:
    return f"item/{weapon}/{attr_path}/{stem}"


def collect_moves(sub: Path) -> list[tuple[Path, Path, str, str]]:
    moves: list[tuple[Path, Path, str, str]] = []
    if not sub.is_dir():
        return moves
    for p in sub.iterdir():
        if not p.is_file():
            continue
        stem = p.stem
        sp = split_stem(stem)
        if not sp:
            continue
        weapon, attr, file_stem = sp
        dst = sub / weapon / attr / f"{file_stem}{p.suffix}"
        oid = old_texture_id(file_stem)
        nid = new_texture_id(weapon, attr, file_stem)
        moves.append((p, dst, oid, nid))
    return moves


def replace_in_files(pairs: list[tuple[str, str]], dry: bool) -> int:
    touched = 0
    globs = ("*.json", "*.mcmeta", "*.properties")
    for pat in globs:
        for f in ASSETS_MC.rglob(pat):
            try:
                txt = f.read_text(encoding="utf-8")
            except OSError:
                continue
            nt = txt
            for old, new in pairs:
                if old in nt:
                    nt = nt.replace(old, new)
            if nt != txt:
                touched += 1
                if not dry:
                    f.write_text(nt, encoding="utf-8")
    return touched


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    dry = not args.apply

    all_moves: list[tuple[Path, Path, str, str]] = []
    for kind in ("models", "textures"):
        sub = ASSETS_MC / kind / "item"
        all_moves.extend(collect_moves(sub))

    pairs = sorted({(o, n) for _, _, o, n in all_moves}, key=lambda x: -len(x[0]))

    print(f"{'DRY-RUN' if dry else 'APPLY'}: {len(all_moves)} files to move")

    for src, dst, _, _ in all_moves[:30]:
        print(f"  {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")
    if len(all_moves) > 30:
        print(f"  ... +{len(all_moves) - 30} more")

    for src, dst, _, _ in all_moves:
        if not dry:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))

    n_files = replace_in_files(pairs, dry)
    print(f"Text files updated: {n_files} ({'preview only' if dry else 'saved'})")

    if dry:
        print("\n실제 적용: python tools/restructure_rpgskills_pack.py --apply")


if __name__ == "__main__":
    main()
