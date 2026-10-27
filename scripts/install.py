"""把仓库里的技能库扁平化安装到任意 Agent 客户端的 skills 目录。

用法：
    python scripts/install.py --target ~/.claude/skills
    python scripts/install.py --target D:/some/skills --dry-run

只复制含 SKILL.md 的目录，重名时报告冲突而不覆盖。

安全约定：任何覆盖都先复制到目标旁的临时目录，成功后再原子替换。复制失败时
旧版本原样保留，不会出现「旧版已删、新版不全」的中间态。
"""
import argparse
import shutil
import sys
import uuid
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


def replace_dir(src: Path, dst: Path):
    """用 src 原子替换 dst：先拷到同级临时目录，成功后再换位。"""
    tmp = dst.with_name(f".{dst.name}.installing-{uuid.uuid4().hex[:8]}")
    try:
        shutil.copytree(src, tmp)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    backup = None
    if dst.exists():
        backup = dst.with_name(f".{dst.name}.old-{uuid.uuid4().hex[:8]}")
        dst.rename(backup)
    try:
        tmp.rename(dst)
    except Exception:
        if backup is not None:
            backup.rename(dst)
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    if backup is not None:
        shutil.rmtree(backup, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, help="目标 skills 目录")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="覆盖目标中已存在的同名技能")
    args = ap.parse_args()

    target = Path(args.target).expanduser()
    if not args.dry_run:
        if target.exists() and not target.is_dir():
            sys.exit(f"错误：目标路径已存在且不是目录 —— {target}")
        if target.resolve() == REPO or REPO in target.resolve().parents:
            sys.exit(f"错误：目标目录位于仓库内部，拒绝写入 —— {target}")

    items = discover()
    print(f"发现 {len(items)} 个技能")

    existed, failed = [], []
    copied = 0
    for src, name in items:
        dst = target / name
        if dst.exists() and not args.force:
            existed.append(name)
            continue
        if args.dry_run:
            verb = "覆盖" if dst.exists() else "复制"
            print(f"  [待{verb}] {name}")
            copied += 1
            continue
        try:
            target.mkdir(parents=True, exist_ok=True)
            replace_dir(src, dst)
            copied += 1
        except Exception as e:
            failed.append((name, str(e)))
            print(f"  [失败] {name}: {e}")

    print(f"复制 {copied} 个，跳过 {len(existed)} 个，失败 {len(failed)} 个")
    if existed:
        print("已存在而跳过（要覆盖请加 --force）：")
        for n in existed:
            print(f"  - {n}")
    if failed:
        print("失败项（已保留原目录，未损坏）：")
        for n, msg in failed:
            print(f"  - {n}: {msg}")
    print(f"目标目录：{target}")
    if args.dry_run:
        print("（--dry-run：未实际写盘）")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
