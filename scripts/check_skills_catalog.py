#!/usr/bin/env python3
"""校验 docs/skills-catalog/ 的一致性。

两种模式：

    make check-catalog              # 仓库自检（已挂 CI）：页数 / 六段结构 / README 索引与状态 / 断链
    make check-local                # 本地对账：页内 ✅/📦 状态 vs 本机 ~/.qoder 下的真实安装

仓库自检不读任何外部目录，所以在 CI 里结果确定。本地对账（--local）额外读
`~/.qoder/skills/` 与 `~/.qoder/plugins/cache/`，报告状态漂移（标 ✅ 但盘上找不到、
标 📦 但已经装了）以及页内声明的插件版本与实装版本不一致。

新增/改名/删除页面无需改脚本；只有“建档名 ≠ 安装名”或“整页代表一个套件”时，
才需要在 IDENTITY 里补一行映射。
"""

from __future__ import annotations

import os
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
    "MCP": "mcp",
    "工具": "tools",
}

# 页内六段（按前缀匹配，允许带括号补充说明）
REQUIRED_HEADS = ("## 能做什么", "## 何时使用", "## 新人上手", "## 最佳实践", "## 项目应用位点", "## 相关")

ROW_RE = re.compile(r"^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*(✅|📦|⚰️)", re.M)
STATUS_RE = re.compile(r"^>\s*状态：(✅|📦|⚰️)", re.M)


def pages() -> list[Path]:
    return sorted(p for d in SECTIONS.values() for p in (CATALOG / d).glob("*.md"))


def readme_rows() -> list[tuple[str, str, str]]:
    text = README.read_text(encoding="utf-8")
    return [(name, rel, status) for name, rel, status in ROW_RE.findall(text)]


# --------------------------------------------------------------------------- 本地对账

QODER = Path.home() / ".qoder"
LOCAL_ROOTS = (QODER / "skills", QODER / "plugins" / "cache")

# 页名 -> 本机身份。缺省用页文件名 slug；只在下面四种情况下需要登记：
#   skill:<安装名>   真实目录名与建档名不同
#   plugin:<插件名>  整页代表一个插件/套件（不对应单一 skill 目录）
#   builtin          随客户端注入，磁盘上无 SKILL.md，不做校验
#   meta             索引/规约页（总览、纪律），不是可安装能力，静默跳过对账
IDENTITY: dict[str, str] = {
    "skill-discovery": "skill:find-skills",
    "vercel-deploy": "skill:deployments-cicd",  # 合页档案：实为 deployments-cicd + vercel-cli
    "sre-runbooks": "skill:runbook",
    "anthropic-documentation": "skill:documentation",
    "vllm-ascend": "skill:vllm-ascend-deploy",
    "sentry-mcp": "plugin:sentry",  # 提供 MCP server + 子 agent，不是 SKILL.md
    "architecture-visualization-suite": "plugin:architecture-visualization",
    "gstack-suite": "plugin:gstack",
    "using-superpowers-family": "plugin:superpowers",
    "knowledge-work-suite": "plugin:knowledge-work-plugins",
    "create-skill": "builtin",
    "schedule": "builtin",
    "security-scan": "plugin:security-scan",
    "postman": "plugin:postman",  # 页代表插件（skill 为 postman-knowledge/routing/agent-ready-apis）
    "datadog": "plugin:datadog",  # skill 为 ddsetup/ddconfig/ddtoolsets
    "alibabacloud-core-suite": "plugin:alibabacloud-core",
    "alibabacloud-spec-ops-suite": "plugin:alibabacloud-spec-ops",
    # MCP 区：server 页对账到提供它的插件；客户端内置的 server 无磁盘痕迹
    "firecrawl-mcp": "plugin:firecrawl",
    "chrome-devtools-mcp": "plugin:chrome-devtools-mcp",
    "cloud-agents-qca": "plugin:qoder-cloud-agents",
    "computer-use": "plugin:computer-use",  # qoder-bundler 布局，无版本层
    "cloudflare-docs-mcp": "plugin:cloudflare",
    "browser-use": "builtin",
    "qmind-mcp": "builtin",
    "extension-market": "builtin",
    "record-and-replay": "builtin",
    # 总览/规约页（mcp/overview、tools/*）不参与对账
    "overview": "meta",
    "discipline": "meta",
}


def local_inventory() -> dict[str, list[str]]:
    """扫描本机 skill 安装位：目录名 -> SKILL.md 相对路径（可能多处同名的）。

    布局不止一种，所以不限深度，只排除明显的干扰项：`~/.qoder/skills/<name>/SKILL.md`、
    插件带版本层的 `<market>/<plugin>/<version>/<name>/SKILL.md` 与
    `.../skills/<name>/SKILL.md`、以及 qoder-bundler 的无版本层布局。

    必须用 `os.walk(followlinks=True)`：部分条目（如百炼家族）在 `~/.qoder/skills/` 下
    是符号链接，`Path.rglob` 在 Python 3.12 不跟进符号链接目录，会漏成“假漂移”。
    """
    skip = {"node_modules", ".backup", ".git", "templates", "example", "examples"}
    inv: dict[str, list[str]] = {}
    seen: set[str] = set()
    for root in LOCAL_ROOTS:
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
            real = os.path.realpath(dirpath)
            if real in seen:  # 符号链接环 / 同一目录多入口
                dirnames[:] = []
                continue
            seen.add(real)
            if len(Path(dirpath).relative_to(root).parts) > 8:
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d not in skip]
            if "SKILL.md" not in filenames:
                continue
            skill_dir = Path(dirpath)
            inv.setdefault(skill_dir.name, []).append(str(skill_dir.relative_to(QODER)) + "/SKILL.md")
    return inv


def installed_plugins() -> dict[str, list[str]]:
    """插件名 -> 版本号列表（`cache/<market>/<plugin>/<version>/`，无版本层的记 '-'）。"""
    out: dict[str, list[str]] = {}
    cache = QODER / "plugins" / "cache"
    if not cache.is_dir():
        return out
    for md in cache.rglob("plugin.json"):
        rel = md.relative_to(cache).parts
        if len(rel) < 3:
            continue
        plugin, ver = rel[1], rel[2] if re.match(r"^\d+\.\d+", rel[2]) else "-"
        out.setdefault(plugin, []).append(ver)
    bundler = cache / "qoder-bundler"
    if bundler.is_dir():
        for d in sorted(bundler.iterdir()):
            if d.is_dir():
                out.setdefault(d.name, []).append("-")
    return out


def reconcile_local(rows: list[tuple[str, str, str]]) -> tuple[list[str], list[str]]:
    """返回 (硬问题, 提醒)。硬问题 = 状态撒谎；提醒 = 版本/多处同名。"""
    problems: list[str] = []
    notes: list[str] = []
    if not QODER.is_dir():
        return [f"本机无 {QODER} 目录，无法对账"], notes
    inv = local_inventory()
    plugins = installed_plugins()
    ok = drift = 0
    for _, rel, status in rows:
        page = CATALOG / rel
        slug = page.stem
        spec = IDENTITY.get(slug, f"skill:{slug}")
        head = page.read_text(encoding="utf-8") if page.exists() else ""
        if spec == "meta":
            continue
        if spec == "builtin":
            notes.append(f"{rel}: 客户端内置，磁盘无文件可校验（不计入漂移）")
            continue
        if spec.startswith("plugin:"):
            name = spec.split(":", 1)[1]
            found = name in plugins
            vers = plugins.get(name, [])
        else:
            name = spec.split(":", 1)[1]
            hits = inv.get(name, [])
            found = bool(hits)
            vers = [v for v in (re.findall(r"/(\d+\.\d+[^/]*)/", h) or ["-"] for h in hits) for v in v]
            if len(hits) > 1:
                notes.append(f"{rel}: `{name}` 在本机出现 {len(hits)} 处（{'; '.join(hits)}）")
        if status == "✅" and not found:
            problems.append(f"{rel}: 标 ✅ 但本机找不到 `{spec}`——要么装没了，要么页内状态/IDENTITY 映射要改")
            drift += 1
        elif status == "📦" and found:
            problems.append(
                f"{rel}: 标 📦（未装）但本机已存在 `{spec}` {sorted(set(vers))}——该回填 ✅ + 安装日期"
            )
            drift += 1
        elif status == "✅" and found:
            ok += 1
            real = {v for v in vers if v != "-"}
            claimed = set(re.findall(r"v?(\d+\.\d+\.\d+)", head))
            if claimed and real and not (claimed & real):
                notes.append(f"{rel}: 页内声明版本 {sorted(claimed)} 与本机实装 {sorted(real)} 不一致")
    notes.append(f"本地对账：{ok} 页 ✅ 已核实、{drift} 页漂移")
    return problems, notes


def main(local: bool = False) -> int:
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

    # 2) 六段结构 + 头部状态行
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

    notes: list[str] = []
    if local:
        extra, notes = reconcile_local(rows)
        problems.extend(extra)

    if notes:
        print("\n提醒（不阻断）：")
        for s in notes:
            print(f"  · {s}")

    if problems:
        print(f"\n❌ {len(problems)} 个问题：")
        for s in problems:
            print(f"  - {s}")
        return 1
    print("✅ 全部通过（页数、六段结构、索引一一对应、状态一致、无断链）")
    return 0


if __name__ == "__main__":
    sys.exit(main(local="--local" in sys.argv[1:]))
