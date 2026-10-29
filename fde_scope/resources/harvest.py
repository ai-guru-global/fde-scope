"""GitHub FDE 资源抓取管线：枚举 → 元数据 → 许可判定 → 增量镜像。

设计约束（AGENTS.md）：

* **不变量 3（凭证只在环境变量）**：GitHub token 由 ``gh`` 自己从 keyring 读，
  本模块**不经手、不记录、不落盘**任何 token；所有网络调用都收在一个
  可 monkeypatch 的 :func:`_gh_json` 里，测试与 ``--offline`` 都不触网。
* **不变量 4（原子写盘）**：manifest 走 :func:`repo.save_resources`，
  镜像文件走 :func:`fsutil.atomic_write_text`。
* **溯源诚实（measured, not aspirational）**：``snapshot.yaml`` 记录每条查询的
  字面 query 串 + 采集时刻的 ``total_count`` + 实采页数；:data:`QUERIES` 是
  唯一事实源，被 ``tests/test_resources_guard.py`` 钉住与快照逐字一致。

许可 ⊥ 相关性两轴由 :mod:`fde_scope.resources.models` 强制；本模块只决定
「谁进目录、抓谁、抓到什么状态」，绝不绕过模型不变量落正文。
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import fsutil
from ..logutil import get_logger
from . import repo as _repo
from .models import (
    LICENSE_NOASSERTION,
    LICENSE_NONE,
    MirrorFile,
    QuerySnapshot,
    ResourceRecord,
    Snapshot,
    is_permissive,
    mirror_gate,
    normalize_license,
)

logger = get_logger("resources.harvest")

#: 发现查询字面量 —— 必须与 ``data/snapshot.yaml`` 的 queries 逐字一致
#: （guard test i 钉死，防止改了查询而快照计数还在说老数字）。
QUERIES: tuple[str, ...] = (
    "topic:forward-deployed-engineer",
    '"forward deployed engineer" in:readme',
    '"forward deployed engineer" in:name,description',
)

PER_PAGE = 100
DEFAULT_MAX_PAGES = 4

#: 镜像预算（防止把仓库撑爆）。
MAX_FILES_PER_REPO = 12
MAX_BYTES_PER_FILE = 200_000
MAX_BYTES_PER_REPO = 400_000
MAX_BYTES_TOTAL = 4_000_000
MAX_MD_DEPTH = 2

#: 逐字镜像根目录（仓库 checkout 专属，不进 wheel —— 同 skills-catalog）。
MIRROR_ROOT = Path(__file__).resolve().parents[2] / "docs" / "github-resources" / "mirror"


class HarvestError(RuntimeError):
    """不可恢复的抓取故障（缺 gh、鉴权失败等）。"""


# ---------------------------------------------------------------------------
# gh 封装（唯一触网点；测试 monkeypatch 此函数即可）
# ---------------------------------------------------------------------------
def _gh_json(args: list[str], *, retries: int = 3) -> Any | None:
    """Run ``gh api <args...>`` and parse the JSON body.

    Returns ``None`` on HTTP 404 / empty body. Retries on 403 / rate-limit
    with a ``retry-after``-aware backoff. Never inspects or logs credentials.
    """
    delay = 2.0
    last_err = ""
    for attempt in range(retries):
        proc = subprocess.run(  # noqa: S603 — argv is built here, never from user input
            ["gh", "api", *args],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            body = proc.stdout.strip()
            return json.loads(body) if body else None
        last_err = (proc.stderr or "").strip()
        low = last_err.lower()
        if "404" in low or "not found" in low:
            return None
        if attempt < retries - 1 and ("403" in low or "rate limit" in low or "retry" in low):
            sleep_for = _retry_after_seconds(last_err, default=delay)
            logger.warning(
                "gh api throttled (attempt %d/%d), sleeping %.1fs", attempt + 1, retries, sleep_for
            )
            time.sleep(sleep_for)
            delay *= 2
            continue
        raise HarvestError(
            f"gh api failed: {args[:2]} → {last_err.splitlines()[-1] if last_err else 'unknown'}"
        )
    raise HarvestError(f"gh api exhausted retries: {args[:2]}")


def _retry_after_seconds(stderr: str, *, default: float) -> float:
    m = re.search(r"retry-after[^0-9]*(\d+)", stderr, re.I)
    if m:
        return max(default, min(float(m.group(1)), 60.0))
    return default


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------
@dataclass
class Discovered:
    """一次枚举的结果：去重仓库 + 每条查询的快照计数。"""

    repos: dict[str, dict[str, Any]] = field(default_factory=dict)  # full_name -> raw item
    snapshots: list[QuerySnapshot] = field(default_factory=list)


def enumerate_repos(*, max_pages: int = DEFAULT_MAX_PAGES, snapshot_at: str | None = None) -> Discovered:
    """跑 :data:`QUERIES`，按 ``full_name`` 去重 union，并记录快照。

    ``pages_fetched`` 记的是**实采页数**（诚实，不谎称全量）；``total_count`` 是
    GitHub 在采集时刻返回的命中总数。
    """
    when = snapshot_at or dt.date.today().isoformat()
    found: dict[str, dict[str, Any]] = {}
    snaps: list[QuerySnapshot] = []
    for query in QUERIES:
        pages = 0
        total = 0
        for page in range(1, max_pages + 1):
            resp = _gh_json(
                [
                    "search/repositories",
                    "-X",
                    "GET",
                    "-f",
                    f"q={query}",
                    "-F",
                    f"per_page={PER_PAGE}",
                    "-F",
                    f"page={page}",
                ]
            )
            if not isinstance(resp, dict):
                break
            total = int(resp.get("total_count", 0) or 0)
            items = resp.get("items") or []
            pages = page
            for item in items:
                name = item.get("full_name")
                if name and name not in found:
                    found[name] = item
            if len(items) < PER_PAGE or page * PER_PAGE >= total:
                break
        snaps.append(
            QuerySnapshot(query=query, total_count=total, pages_fetched=max(pages, 1), snapshot_at=when)
        )
    logger.info("enumerated %d unique repos across %d queries", len(found), len(QUERIES))
    return Discovered(repos=found, snapshots=snaps)


# ---------------------------------------------------------------------------
# 元数据 → 记录（增量 reconcile，保留人工分类）
# ---------------------------------------------------------------------------
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def make_slug(full_name: str, taken: set[str]) -> str:
    """owner/name → 唯一 kebab slug；冲突时加 owner 前缀，仍冲突加序号。"""
    owner, _, name = full_name.partition("/")

    def keb(s: str) -> str:
        return _NON_ALNUM.sub("-", s.lower()).strip("-")

    base = keb(name) or "repo"
    candidate = base
    if candidate in taken:
        candidate = f"{keb(owner)}-{base}"
    n = 2
    while candidate in taken:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def _license_of(item: dict[str, Any]) -> str:
    lic = item.get("license")
    if isinstance(lic, dict):
        return normalize_license(lic.get("spdx_id"))
    return LICENSE_NOASSERTION


def _decision(spdx: str, relevance: str) -> str:
    if is_permissive(spdx):
        if relevance == "noise":
            return f"{spdx} → 许可宽松，但相关性为 noise，不镜像正文"
        return f"{spdx} → 宽松许可，正文可逐字镜像"
    if spdx == LICENSE_NONE:
        return "NONE → 上游声明无许可，正文一律不复制"
    if spdx == LICENSE_NOASSERTION:
        return "NOASSERTION → 许可不可辨识，仅元数据，正文不复制"
    # 认得出、但非宽松（copyleft 等）：与「认不出」是两种上游意图，绝不折叠。
    return f"{spdx} → 许可非宽松（copyleft 等），仅元数据，正文不复制"


def _facts(item: dict[str, Any], when: str) -> dict[str, Any]:
    return {
        "url": item.get("html_url") or f"https://github.com/{item.get('full_name', '')}",
        "license_spdx": _license_of(item),
        "stars": int(item.get("stargazers_count", 0) or 0),
        "upstream_updated_at": (item.get("updated_at") or when)[:10],
        "default_branch": item.get("default_branch") or "main",
        "is_fork": bool(item.get("fork", False)),
        "archived": bool(item.get("archived", False)),
        "snapshot_at": when,
        "upstream_description": item.get("description") or None,
    }


def reconcile(
    existing: list[ResourceRecord], found: dict[str, dict[str, Any]], *, snapshot_at: str
) -> list[ResourceRecord]:
    """把枚举结果并入已有 manifest。

    已建档的仓库：刷新事实字段（stars/updated/license/fork/archived/description），
    **保留人工分类**（relevance/categories/summary/mirror 状态/mirror_decision）。
    新发现的仓库：默认 ``noise`` + ``uncategorized`` + 不镜像 —— 镜像只发生在
    被显式提升为 core/adjacent 且许可宽松之后（计划「agent 先分类再 fetch」）。
    """
    by_repo = {r.repo: r for r in existing}
    taken_slugs = {r.slug for r in existing}
    out: list[ResourceRecord] = []

    for full_name, item in sorted(found.items()):
        facts = _facts(item, snapshot_at)
        prior = by_repo.get(full_name)
        if prior is not None:
            update = {**facts, "license_decision_applied": _decision(facts["license_spdx"], prior.relevance)}
            # 许可转差：已镜像者撤销镜像（保留元数据，绝不静默留旧正文于 manifest）。
            if prior.mirror and not is_permissive(facts["license_spdx"]):
                update |= {
                    "mirror": False,
                    "files": [],
                    "mirror_reason": "license no longer permissive → mirror withheld",
                }
            # 重新校验：把 facts 并入后仍必须满足全部跨字段不变量，否则当场报错而非落盘。
            out.append(ResourceRecord.model_validate(prior.model_dump() | update))
            continue

        slug = make_slug(full_name, taken_slugs)
        taken_slugs.add(slug)
        record = ResourceRecord(
            slug=slug,
            repo=full_name,
            relevance="noise",
            categories=["uncategorized"],
            license_decision_applied=_decision(facts["license_spdx"], "noise"),
            mirror=False,
            files=[],
            **facts,
        )
        out.append(record)

    # 保留本轮枚举没再命中、但已建档的旧条目（不静默删档）。
    seen = {r.repo for r in out}
    for r in existing:
        if r.repo not in seen:
            out.append(r)
    return out


# ---------------------------------------------------------------------------
# 镜像（逐字正文，仅对通过门槛且已审核的条目）
# ---------------------------------------------------------------------------
def _provenance_header(record: ResourceRecord, commit_sha: str, path: str, when: str) -> str:
    return (
        f"<!-- fde-scope mirror · repo: {record.repo} · license: {record.license_spdx} · commit: {commit_sha}\n"
        f"     upstream path: {path} · retrieved: {when} · verbatim; report issues upstream. -->\n\n"
    )


def _candidate_md(tree: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for entry in tree:
        if entry.get("type") != "blob":
            continue
        path = entry.get("path", "")
        if not path.lower().endswith(".md") or "__" in path or path.startswith("/"):
            continue
        depth = path.count("/") + 1
        if depth > MAX_MD_DEPTH:
            continue
        out.append(entry)
    return out


def _fetch_text(path: str, name: str, ref: str) -> str | None:
    blob = _gh_json([f"repos/{path}/git/blobs/{ref}"])
    if not isinstance(blob, dict) or blob.get("encoding") != "base64":
        return None
    try:
        return base64.b64decode(blob.get("content", "")).decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        logger.warning("skipping non-utf8 mirror %s:%s", name, path)
        return None


def mirror_repo(
    record: ResourceRecord, *, budget_total_remaining: int, snapshot_at: str
) -> tuple[ResourceRecord, int]:
    """抓取一个仓库的宽松正文镜像；返回更新后的记录 + 消耗字节数。

    失败绝不删除已有镜像：仅在 mirror_reason 追加 ``fetch_failed:<...>`` 保留旧 SHA。
    """
    remaining = budget_total_remaining
    existing_by_path = {f.path: f for f in record.files}
    new_files: list[MirrorFile] = []
    used = 0
    when = snapshot_at

    tree = _gh_json([f"repos/{record.repo}/git/trees/{record.default_branch}?recursive=1"])
    if not isinstance(tree, dict):
        updated = record.model_copy(
            update={"mirror_reason": (record.mirror_reason or "") + " fetch_failed:tree"}
        )
        return updated, 0
    candidates = _candidate_md(tree.get("tree") or [])[:MAX_FILES_PER_REPO]

    commit = _gh_json([f"repos/{record.repo}/commits/{record.default_branch}"])
    commit_sha = commit.get("sha", "") if isinstance(commit, dict) else ""

    repo_bytes = 0
    for entry in candidates:
        path = entry["path"]
        blob_sha = entry.get("sha", "")
        prior = existing_by_path.get(path)
        if prior is not None and prior.blob_sha == blob_sha and prior.local_name:
            # 未变：保留旧条目，不重抓、不重写；按其磁盘实际占用计入预算。
            new_files.append(prior)
            on_disk = MIRROR_ROOT / record.mirror_dir / prior.local_name
            repo_bytes += on_disk.stat().st_size if on_disk.is_file() else 0
            continue
        text = _fetch_text(record.repo, entry["path"], blob_sha)
        if text is None:
            continue
        if len(text) > MAX_BYTES_PER_FILE:
            text = text[:MAX_BYTES_PER_FILE]
            truncated = True
        else:
            truncated = False
        body = text.encode("utf-8")
        if repo_bytes + len(body) > MAX_BYTES_PER_REPO or used + len(body) > remaining:
            # 超预算：不写入、也不登记 files[]（manifest 只描述磁盘上真实存在的镜像）。
            logger.info("budget stop: %s:%s", record.repo, path)
            continue
        local_name = path.replace("/", "__")
        target = fsutil.safe_child(MIRROR_ROOT, record.mirror_dir, local_name)
        header = _provenance_header(record, commit_sha, path, when)
        fsutil.atomic_write_text(target, header + text)
        new_files.append(
            MirrorFile(
                path=path, local_name=local_name, blob_sha=blob_sha, retrieved_at=when, truncated=truncated
            )
        )
        repo_bytes += len(body)
        used += len(body)

    if not new_files:
        updated = record.model_copy(
            update={"mirror_reason": (record.mirror_reason or "") + " fetch_failed:no_readable_md"}
        )
        return updated, used

    updated = record.model_copy(
        update={"mirror": True, "files": sorted(new_files, key=lambda f: f.path), "mirror_reason": None}
    )
    return updated, used


# ---------------------------------------------------------------------------
# 顶层编排
# ---------------------------------------------------------------------------
def run_harvest(*, offline: bool = False, max_pages: int = DEFAULT_MAX_PAGES) -> Snapshot:
    """一次完整抓取：枚举 → reconcile → 镜像合格条目 → 落 manifest + snapshot。

    ``offline``：不触网，只把当前 manifest / snapshot 原样重排落盘（CI 无密钥可跑，
    让 README 计数与门户构建仍可执行）。
    """
    existing = _repo.load_resources()
    when = dt.date.today().isoformat()

    if offline:
        snapshot = _repo.load_snapshot() or Snapshot(queries=[], unique_repos=len(existing))
        _repo.save_resources(existing)
        _repo.save_snapshot(snapshot)
        logger.info("offline harvest: re-emitted %d records without network", len(existing))
        return snapshot

    found = enumerate_repos(max_pages=max_pages, snapshot_at=when)
    merged = reconcile(existing, found.repos, snapshot_at=when)

    budget_left = MAX_BYTES_TOTAL
    mirrored: list[ResourceRecord] = []
    for rec in merged:
        # 镜像只发生在：许可宽松 + 非 noise（门槛）+ 已审核（core/adjacent 有双语摘要）。
        # 新发现条目默认 noise、无摘要 → 不抓正文（agent 先分类、再 fetch 落地）。
        reviewed = rec.relevance in ("core", "adjacent") and bool(rec.summary_zh and rec.summary_en)
        if mirror_gate(rec.license_spdx, rec.relevance) and reviewed and budget_left > 0:
            rec, spent = mirror_repo(rec, budget_total_remaining=budget_left, snapshot_at=when)
            budget_left -= spent
        mirrored.append(rec)

    _repo.save_resources(mirrored)
    snapshot = Snapshot(
        queries=found.snapshots,
        unique_repos=len(found.repos),
        note=(
            "union 是「本次采集前若干页」的去重结果，不是全体匹配。in:readme / "
            "name,description 的全量命中远大于此；此处诚实记录 total_count 与实采页数。"
        ),
    )
    _repo.save_snapshot(snapshot)
    logger.info("harvest done: %d repos, mirror budget %d bytes left", len(mirrored), budget_left)
    return snapshot
