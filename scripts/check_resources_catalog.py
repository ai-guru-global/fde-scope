#!/usr/bin/env python3
"""校验 docs/github-resources/ 的一致性（仓库自检，结果确定、不触网）。

    make check-resources    # 等价 python3 scripts/check_resources_catalog.py

钉住四条「同一事实源」的关系，任何一处漂移就退出 1：

1. **README 计数 ⇔ 清单 ⇔ 磁盘**：头部声明的「建档仓库 / 逐字镜像 / 镜像文件」
   三个数字，必须分别等于 manifest 记录数、``mirror: true`` 记录数（== 磁盘镜像目录数）、
   磁盘上真实 ``.md`` 文件数（== ``files[]`` 条目总数）。
2. **磁盘 ⇔ 清单**（不变量 a）：每个 ``mirror: true`` 记录都有对应镜像目录，目录里
   ``.md`` 集合 == ``files[].local_name``；磁盘上不存在无清单归属的孤儿目录。
3. **provenance 头**（不变量 f）：每个镜像文件字节头都含 ``repo`` / ``license`` / ``commit`` /
   ``upstream path``，且 license 与清单一致——镜像正文一旦脱离溯源就失去再分发依据。
4. **NOTICE**（不变量 j）：每个镜像仓库在 NOTICE 里有一行 SPDX 记录（镜像 README 之后，
   「no third-party content is vendored」这句话必须已被逐仓声明取代）。

纯模型不变量（NONE≠NOASSERTION、非宽松/ noise 绝不 mirror、双语摘要…）由
``tests/test_resources_guard.py`` 用构造数据守；本脚本只管**落盘产物**这一侧。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from fde_scope.resources.models import is_permissive
from fde_scope.resources.repo import load_resources

ROOT = Path(__file__).resolve().parent.parent
GR = ROOT / "docs" / "github-resources"
MIRROR = GR / "mirror"
README = GR / "README.md"
NOTICE = ROOT / "NOTICE"

COUNTS_RE = re.compile(r"建档仓库 (\d+) 个 · 逐字镜像 (\d+) 个仓库 · 镜像文件 (\d+) 个")
# README 表格行：| repo | license | commit | files | `mirror/<dir>/` |
ROW_RE = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*`mirror/([^/`]+)/`\s*\|\s*$",
    re.M,
)


def main() -> int:
    problems: list[str] = []

    recs = load_resources()
    mirrored = [r for r in recs if r.mirror]
    by_dir = {r.mirror_dir: r for r in mirrored}

    if len(by_dir) != len(mirrored):
        problems.append("mirror_dir 在多条记录间不唯一（镜像目录会互相覆盖）")

    # 1) README 计数 ⇔ 清单 ⇔ 磁盘
    text = README.read_text(encoding="utf-8") if README.is_file() else ""
    m = COUNTS_RE.search(text)
    if not m:
        problems.append("README 缺少「建档仓库 N 个 · 逐字镜像 N 个仓库 · 镜像文件 N 个」声明行")
        declared_total = declared_mir = declared_files = None
    else:
        declared_total, declared_mir, declared_files = (int(x) for x in m.groups())
        if declared_total != len(recs):
            problems.append(f"README 建档仓库数 {declared_total} ≠ manifest 记录数 {len(recs)}")
        if declared_mir != len(mirrored):
            problems.append(f"README 逐字镜像数 {declared_mir} ≠ manifest mirror:true {len(mirrored)}")

    # 磁盘镜像目录 + 文件
    disk_dirs = sorted(d.name for d in MIRROR.iterdir() if d.is_dir()) if MIRROR.is_dir() else []
    disk_files: dict[str, list[str]] = {}
    if MIRROR.is_dir():
        for d in MIRROR.iterdir():
            if d.is_dir():
                disk_files[d.name] = sorted(p.name for p in d.glob("*.md"))
    disk_md_total = sum(len(v) for v in disk_files.values())
    manifest_file_total = sum(len(r.files) for r in mirrored)

    if len(disk_dirs) != len(mirrored):
        problems.append(f"磁盘镜像目录 {len(disk_dirs)} ≠ manifest mirror:true {len(mirrored)}")
    if declared_files is not None and declared_files != disk_md_total:
        problems.append(f"README 镜像文件数 {declared_files} ≠ 磁盘 .md {disk_md_total}")
    if manifest_file_total != disk_md_total:
        problems.append(f"manifest files[] 总数 {manifest_file_total} ≠ 磁盘 .md {disk_md_total}")

    # 2) 磁盘 ⇔ 清单：逐目录对齐 + 孤儿目录
    for dname in disk_dirs:
        rec = by_dir.get(dname)
        if rec is None:
            problems.append(f"磁盘孤儿镜像目录无清单归属：mirror/{dname}")
            continue
        disk_set = set(disk_files.get(dname, []))
        manifest_set = {f.local_name for f in rec.files}
        if disk_set != manifest_set:
            only_disk = sorted(disk_set - manifest_set)
            only_man = sorted(manifest_set - disk_set)
            problems.append(f"mirror/{dname} 文件集合不一致：磁盘独有 {only_disk}，清单独有 {only_man}")

    for rec in mirrored:
        if rec.mirror_dir not in disk_dirs:
            problems.append(f"mirror:true 记录缺磁盘目录：mirror/{rec.mirror_dir}")

    # 3) 非宽松 / noise 绝不 mirror（落盘侧复核，模型层已由 guard 守）
    for rec in mirrored:
        if not is_permissive(rec.license_spdx):
            problems.append(f"{rec.repo}: license {rec.license_spdx!r} 非宽松却被镜像")
        if rec.relevance == "noise":
            problems.append(f"{rec.repo}: noise 条目绝不镜像，却 mirror:true")

    # 4) provenance 头（不变量 f）
    for dname, names in disk_files.items():
        rec = by_dir.get(dname)
        if rec is None:
            continue
        for name in names:
            head = (MIRROR / dname / name).read_text(encoding="utf-8", errors="replace")[:600]
            if "fde-scope mirror" not in head:
                problems.append(f"mirror/{dname}/{name}: 缺 provenance 头")
                continue
            if f"repo: {rec.repo}" not in head:
                problems.append(f"mirror/{dname}/{name}: 头内 repo 与清单不符（应为 {rec.repo}）")
            if f"license: {rec.license_spdx}" not in head:
                problems.append(f"mirror/{dname}/{name}: 头内 license 与清单不符（应为 {rec.license_spdx}）")
            if "commit: " not in head or "upstream path: " not in head:
                problems.append(f"mirror/{dname}/{name}: 头缺 commit / upstream path 字段")

    # 5) README 表格行 ⇔ 镜像目录，一一对应且文件数/许可一致
    rows = ROW_RE.findall(text)
    row_dirs = [r[4] for r in rows]
    dupes = {d for d in row_dirs if row_dirs.count(d) > 1}
    if dupes:
        problems.append(f"README 表格重复目录行：{sorted(dupes)}")
    for repo_cell, lic_cell, _commit, files_cell, dname in rows:
        rec = by_dir.get(dname)
        if rec is None:
            problems.append(f"README 表格指向无镜像归属的目录：mirror/{dname}")
            continue
        if repo_cell != rec.repo:
            problems.append(f"README 表格 {dname} 仓库名 {repo_cell!r} ≠ 清单 {rec.repo!r}")
        if lic_cell != rec.license_spdx:
            problems.append(f"README 表格 {dname} 许可 {lic_cell!r} ≠ 清单 {rec.license_spdx!r}")
        if int(files_cell) != len(rec.files):
            problems.append(f"README 表格 {dname} 文件数 {files_cell} ≠ 清单 {len(rec.files)}")
    missing_rows = sorted(set(by_dir) - set(row_dirs))
    if missing_rows:
        problems.append(f"镜像目录未登记进 README 表格：{missing_rows}")

    # 6) NOTICE 每个镜像仓库一行（不变量 j）
    notice_text = NOTICE.read_text(encoding="utf-8") if NOTICE.is_file() else ""
    for rec in mirrored:
        if rec.repo not in notice_text:
            problems.append(f"NOTICE 缺镜像仓库条目：{rec.repo}")

    print(
        f"records: {len(recs)} ｜ mirror:true: {len(mirrored)} ｜ "
        f"disk dirs: {len(disk_dirs)} ｜ disk .md: {disk_md_total} ｜ README rows: {len(rows)}"
    )
    if problems:
        print(f"\n❌ {len(problems)} 个问题：")
        for s in problems:
            print(f"  - {s}")
        return 1
    print("✅ 全部通过（README 计数 ⇔ 清单 ⇔ 磁盘；镜像目录/文件对齐；provenance 头齐全；NOTICE 逐仓条目）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
