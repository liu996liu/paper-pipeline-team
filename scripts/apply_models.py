"""按 team.json 的 modelPolicy 同步各成员的 model / reasoningEffort。

改模型只改 team.json 的 modelPolicy.tiers，然后运行本脚本，避免手工改 9 个文件后不一致。
用法：
    python scripts/apply_models.py             # 写入
    python scripts/apply_models.py --dry-run   # 只看会改什么
    python scripts/apply_models.py --dry-run --strict   # CI 用：有任何不一致即退出码 1
"""
import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEAM = REPO / "team.json"


def apply(dry=False, strict=False):
    team = json.loads(TEAM.read_text(encoding="utf-8"))
    policy = team.get("modelPolicy") or {}
    tiers = policy.get("tiers") or {}
    roles = policy.get("roles") or {}
    if not tiers or not roles:
        raise SystemExit("team.json 缺少 modelPolicy.tiers 或 modelPolicy.roles")

    changed = 0
    missing = []
    for f in sorted((REPO / "agents").glob("*.md")):
        name = f.stem
        r = roles.get(name)
        if not r:
            missing.append(name)
            print(f"[跳过] {name}：modelPolicy.roles 未定义")
            continue
        t = tiers.get(r["tier"])
        if not t:
            print(f"[跳过] {name}：档位 {r['tier']} 未在 tiers 中定义")
            continue

        lines = f.read_text(encoding="utf-8").split("\n")
        out = []
        for line in lines:
            if line.startswith("model: "):
                out.append(f"model: {t['model']}")
            elif line.startswith("reasoningEffort: "):
                if t.get("reasoningEffort"):
                    out.append(f"reasoningEffort: {t['reasoningEffort']}")
            else:
                out.append(line)
        if t.get("reasoningEffort") and not any(x.startswith("reasoningEffort: ") for x in out):
            i = next((i for i, x in enumerate(out) if x.startswith("model: ")), None)
            if i is not None:
                out.insert(i + 1, f"reasoningEffort: {t['reasoningEffort']}")

        new = "\n".join(out)
        old = f.read_text(encoding="utf-8")
        if new != old:
            changed += 1
            tag = f"{t['model']}" + (f" / {t['reasoningEffort']}" if t.get("reasoningEffort") else "")
            print(f"{'[待改]' if dry else '[已改]'} {name} -> {r['tier']} ({tag})")
            if not dry:
                f.write_text(new, encoding="utf-8", newline="\n")
        else:
            print(f"[一致] {name} -> {r['tier']} ({t['model']})")
    print(f"\n共 {changed} 个文件需要更新" + ("（--dry-run 未写盘）" if dry else ""))
    if strict and (changed or missing):
        raise SystemExit(1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--strict", action="store_true", help="发现不一致时退出码 1（CI 用）")
    a = ap.parse_args()
    apply(a.dry_run, a.strict)
