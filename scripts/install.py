"""把仓库里的技能库扁平化安装到任意 Agent 客户端的 skills 目录。

用法：
    python scripts/install.py --target ~/.claude/skills
    python scripts/install.py --target D:/some/skills --dry-run

只复制含 SKILL.md 的目录，重名时报告冲突而不覆盖。
"""
import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"


def discover():
    """返回 [(skill_dir, skill_name)]，按路径排序；同名只保留第一个并报告。"""
    found, seen = [], {}
    for f in sorted(SKILLS.rglob("SKILL.md")):
        d = f.parent
        name = d.name
        if name in seen:
            print(f"[冲突] {name} 已存在，跳过：{d.relative_to(REPO)}")
            continue
        seen[name] = d
        found.append((d, name))
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, help="目标 skills 目录")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="覆盖目标中已存在的同名技能")
    args = ap.parse_args()

    target = Path(args.target).expanduser()
    items = discover()
    print(f"发现 {len(items)} 个技能")

    if not args.dry_run:
        target.mkdir(parents=True, exist_ok=True)

    copied = skipped = 0
    for src, name in items:
        dst = target / name
        if dst.exists() and not args.force:
            skipped += 1
            continue
        if args.dry_run:
            print(f"  [待复制] {name}")
            copied += 1
            continue
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        copied += 1

    print(f"复制 {copied} 个，跳过 {skipped} 个（已存在，用 --force 覆盖）")
    print(f"目标目录：{target}")
    if args.dry_run:
        print("（--dry-run：未实际写盘）")


if __name__ == "__main__":
    main()
