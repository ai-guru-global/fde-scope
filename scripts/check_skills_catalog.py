#!/usr/bin/env python3
"""校验 docs/skills-catalog/ 的一致性（断链 / 五段结构 / README 索引与状态）。

用途：维护 skill 手册库时的验收门禁。新增/改名/删除页面无需改脚本，
README 头部声明的页数会自动与磁盘上的页面数比对。

用法：
    python3 scripts/check_skills_catalog.py        # 有问题退出码 1
    make check-catalog
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "docs" / "skills-catalog"
README = CATALOG / "README.md"

# README 表中的分区标题 -> (目录名, 头部声明里的中文标签)
SECTIONS = {
    "Zone A": "zone-a-pre-engagement",
    "Zone B": "zone-b-build",
    "Zone C": "zone-c-operationalization",
    "Zone D": "zone-d-handoff",
    "横切": "cross-cutting",
}

# 页内五段（按前缀匹配，允许带括号补充说明）
REQUIRED_HEADS = ("## 能做什么", "## 何时使用", "## 最佳实践", "## 项目应用位点", "## 相关")

ROW_RE = re.compile(r"^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*(✅|📦|⚰️)", re.M)
STATUS_RE = re.compile(r"^>\s*状态：(✅|📦|⚰️)", re.M)


def pages() -> list[Path]:
    return sorted(p for d in SECTIONS.values() for p in (CATALOG / d).glob("*.md"))


def readme_rows() -> list[tuple[str, str, str]]:
    text = README.read_text(encoding="utf-8")
    return [(name, rel, status) for name, rel, status in ROW_RE.findall(text)]


def main() -> int:
    problems: list[str] = []
    texts = {p: p.read_text(encoding="utf-8") for p in pages()}

    # 1) README 头部页数声明 vs 磁盘
    readme_text = README.read_text(encoding="utf-8")
    head_lines = [ln for ln in readme_text.splitlines() if "共 " in ln and "页" in ln]
    head = head_lines[0] if head_lines else ""
    declared: dict[str, re.Match | None] = {"total": re.search(r"共 (\d+) 页", head)}
    for label in SECTIONS:
        declared[label] = re.search(rf"{label}\s*(\d+)", head)
    counts = Counter(p.parent.name for p in pages())
    if not declared["total"] or int(declared["total"].group(1)) != len(pages()):
        problems.append(
            f"README 头部总页数与磁盘不符：声明 {declared['total'] and declared['total'].group(1)}，实际 {len(pages())}"
        )
    for label, d in SECTIONS.items():
        m = declared[label]
        if not m or int(m.group(1)) != counts[d]:
            problems.append(f"README 头部 {label} 页数与磁盘不符：声明 {m and m.group(1)}，实际 {counts[d]}")

    # 2) 五段结构 + 头部状态行
    for p, t in texts.items():
        heads = [ln for ln in t.splitlines() if ln.startswith("## ")]
        missing = [h for h in REQUIRED_HEADS if not any(ln.startswith(h) for ln in heads)]
        if missing:
            problems.append(f"{p.relative_to(ROOT)} 缺段：{'、'.join(missing)}")
        if not STATUS_RE.search(t):
            problems.append(f"{p.relative_to(ROOT)} 头部缺「> 状态：」行")

    # 3) README 行 <-> 页面一一对应，且状态一致
    rows = readme_rows()
    row_files = [r[1] for r in rows]
    dupes = [f for f, n in Counter(row_files).items() if n > 1]
    if dupes:
        problems.append(f"README 重复行：{dupes}")
    page_rel = {str(p.relative_to(CATALOG)) for p in pages()}
    for name, rel, _ in rows:
        if rel not in page_rel:
            problems.append(f"README 行指向不存在的页面：{name} -> {rel}")
    for rel in sorted(page_rel - set(row_files)):
        problems.append(f"页面未登记进 README：{rel}")

    status_of = {r[1]: r[2] for r in rows}
    for p, t in texts.items():
        row = status_of.get(str(p.relative_to(CATALOG)))
        page = STATUS_RE.search(t)
        if row and page and row != page.group(1):
            problems.append(f"{p.relative_to(ROOT)} 状态不一致：页内 {page.group(1)} / README {row}")

    # 4) catalog 内所有相对链接可解析
    for p, t in texts.items():
        for target in re.findall(r"\]\((?!https?://|#)([^)\s#]+)", t):
            if target.startswith("mailto:"):
                continue
            if not (p.parent / target).resolve().exists():
                problems.append(f"{p.relative_to(ROOT)} 断链：{target}")
    for target in re.findall(r"\]\((?!https?://|#)([^\s#)]+)", readme_text):
        if not (README.parent / target).resolve().exists():
            problems.append(f"README 断链：{target}")

    print(f"pages: {len(pages())} ｜ README rows: {len(rows)}")
    print(" ｜ ".join(f"{k}={counts[v]}" for k, v in SECTIONS.items()))
    if problems:
        print(f"\n❌ {len(problems)} 个问题：")
        for s in problems:
            print(f"  - {s}")
        return 1
    print("✅ 全部通过（页数、五段结构、索引一一对应、状态一致、无断链）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
