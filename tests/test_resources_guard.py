"""GitHub 资源建档的契约守卫。

Origin: 计划 docs 之外的新数据面（topic:forward-deployed-engineer 资源镜像）。
这些测试在「许可/相关性两轴」的不变量漂移时失败：

* ``NONE`` 与 ``NOASSERTION`` 是两个不同枚举值，永不被折叠、永不为 null
  —— 把「GitHub 认不出」当成「上游声明无许可」会伪造上游意图；
* 镜像门槛同时要求 ``permissive-license AND relevance != noise``，
  无许可项只存元数据 + 我们自己撰写的双语摘要，绝不逐字复制正文；
* 宽松 + 非 noise 却未镜像必须写 ``mirror_reason``（漏抓不可静默）；
* core/adjacent 必须中英双语摘要齐全（可再分发的自产内容）；
* slug / repo 唯一，镜像目录名对 owner/name 的 ``__`` 歧义零容忍。

磁盘 ⇔ 清单一致性（镜像文件、provenance 头、rail、HTML 转义、snapshot↔
harvest 查询、NOTICE）在 ``make fetch-resources`` 落地后由本文件补齐。
"""

from __future__ import annotations

from typing import Any

import pytest

from fde_scope.resources import repo
from fde_scope.resources.models import (
    LICENSE_NOASSERTION,
    LICENSE_NONE,
    MirrorFile,
    ResourceRecord,
    Snapshot,
    is_permissive,
    mirror_gate,
    normalize_license,
)


# ---------------------------------------------------------------------------
# 构造一条最小合法记录，逐条改字段做拒绝式测试
# ---------------------------------------------------------------------------
def _base(**overrides: Any) -> ResourceRecord:
    payload: dict[str, Any] = {
        "slug": "demo-repo",
        "repo": "acme/demo-repo",
        "url": "https://github.com/acme/demo-repo",
        "license_spdx": "MIT",
        "license_decision_applied": "MIT → 宽松许可",
        "relevance": "core",
        "categories": ["field-guide"],
        "stars": 10,
        "upstream_updated_at": "2026-10-06",
        "default_branch": "main",
        "is_fork": False,
        "archived": False,
        "snapshot_at": "2026-10-06",
        "mirror": False,
        "mirror_reason": "pending fetch",
        "summary_zh": "示例中文摘要。",
        "summary_en": "Example English summary.",
    }
    payload.update(overrides)
    return ResourceRecord.model_validate(payload)


# ---------------------------------------------------------------------------
# 许可轴：NONE ≠ NOASSERTION，永不为 null，判定正确
# ---------------------------------------------------------------------------
def test_none_and_noassertion_are_distinct_tokens() -> None:
    assert LICENSE_NONE != LICENSE_NOASSERTION


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_normalize_maps_missing_to_noassertion_not_none(raw: str | None) -> None:
    # 「认不出」绝不能被伪装成「上游声明无许可」。
    assert normalize_license(raw) == LICENSE_NOASSERTION


def test_license_spdx_is_never_null_or_empty() -> None:
    rec = _base(license_spdx="")  # validator normalizes
    assert rec.license_spdx == LICENSE_NOASSERTION


@pytest.mark.parametrize(
    ("spdx", "permissive"),
    [
        ("MIT", True),
        ("MIT-0", True),
        ("Apache-2.0", True),
        ("BSD-3-Clause", True),
        ("CC0-1.0", True),
        ("CC-BY-4.0", True),
        ("CC-BY-SA-4.0", True),
        ("CC-BY-NC-4.0", False),  # NonCommercial 与再分发进 MIT 仓库不兼容
        ("CC-BY-ND-4.0", False),  # NoDerivatives
        ("GPL-3.0", False),
        ("BSD-2-Clause-Patent", False),
        (LICENSE_NONE, False),
        (LICENSE_NOASSERTION, False),
    ],
)
def test_is_permissive(spdx: str, permissive: bool) -> None:
    assert is_permissive(spdx) is permissive


# ---------------------------------------------------------------------------
# 镜像门槛：两轴同时成立
# ---------------------------------------------------------------------------
def test_mirror_gate_requires_permissive_and_non_noise() -> None:
    assert mirror_gate("MIT", "core") is True
    assert mirror_gate("MIT", "adjacent") is True
    assert mirror_gate("MIT", "noise") is False
    assert mirror_gate(LICENSE_NONE, "core") is False
    assert mirror_gate(LICENSE_NOASSERTION, "core") is False


def test_non_permissive_entry_cannot_mirror() -> None:
    with pytest.raises(ValueError, match="not redistributable"):
        _base(
            license_spdx=LICENSE_NOASSERTION,
            mirror=True,
            files=[
                MirrorFile(path="README.md", local_name="r.md", blob_sha="a" * 40, retrieved_at="2026-10-06")
            ],
        )


def test_noise_entry_is_never_mirrored() -> None:
    with pytest.raises(ValueError, match="noise"):
        _base(
            relevance="noise",
            mirror=True,
            files=[
                MirrorFile(path="README.md", local_name="r.md", blob_sha="a" * 40, retrieved_at="2026-10-06")
            ],
        )


def test_permissive_non_noise_unmirrored_requires_reason() -> None:
    with pytest.raises(ValueError, match="mirror_reason"):
        _base(mirror=False, mirror_reason=None)


def test_mirror_true_requires_files() -> None:
    with pytest.raises(ValueError, match="files"):
        _base(mirror=True, files=[], mirror_reason=None)


@pytest.mark.parametrize("relevance", ["core", "adjacent"])
def test_core_and_adjacent_require_bilingual_summary(relevance: str) -> None:
    with pytest.raises(ValueError, match="summary"):
        _base(relevance=relevance, summary_zh=None)


def test_noise_does_not_require_summary() -> None:
    rec = _base(relevance="noise", summary_zh=None, summary_en=None)
    assert rec.relevance == "noise"


# ---------------------------------------------------------------------------
# slug / repo 形状与镜像目录歧义
# ---------------------------------------------------------------------------
def test_slug_must_be_kebab() -> None:
    with pytest.raises(ValueError, match="kebab"):
        _base(slug="Bad_Slug")


def test_repo_must_be_owner_slash_name() -> None:
    with pytest.raises(ValueError, match="owner/name"):
        _base(repo="just-a-name")


def test_double_underscore_in_owner_rejected_for_dir_unambiguity() -> None:
    with pytest.raises(ValueError, match="ambiguity"):
        _base(repo="acme__corp/demo-repo")


# ---------------------------------------------------------------------------
# 加载器：真实种子 + 宽容解析 + 往返不折叠
# ---------------------------------------------------------------------------
def test_seed_manifest_loads_and_covers_license_cases() -> None:
    recs = repo.load_resources()
    assert len(recs) >= 3
    by_slug = {r.slug: r for r in recs}
    assert by_slug["fde-guidance-book"].license_spdx == LICENSE_NOASSERTION
    assert by_slug["fde-guidance-book"].mirror is False
    assert by_slug["summer-internships"].relevance == "noise"


def test_seed_slug_and_repo_are_unique() -> None:
    recs = repo.load_resources()
    slugs = [r.slug for r in recs]
    repos = [r.repo for r in recs]
    assert len(set(slugs)) == len(slugs)
    assert len(set(repos)) == len(repos)


def test_loader_skips_corrupt_entry_without_sinking_catalog(tmp_path) -> None:
    import yaml

    good = _base().model_dump(mode="json", exclude_none=True)
    path = tmp_path / "resources.yaml"
    path.write_text(
        yaml.safe_dump([good, {"slug": "nope"}], allow_unicode=True),
        encoding="utf-8",
    )
    recs = repo.load_resources(path)
    assert [r.slug for r in recs] == ["demo-repo"]


def test_loader_missing_file_returns_empty(tmp_path) -> None:
    assert repo.load_resources(tmp_path / "absent.yaml") == []


def test_round_trip_preserves_none_vs_noassertion() -> None:
    import yaml

    for token in (LICENSE_NONE, LICENSE_NOASSERTION):
        rec = _base(license_spdx=token, mirror=False, mirror_reason="withheld")
        dumped = yaml.safe_load(
            yaml.safe_dump(rec.model_dump(mode="json", exclude_none=True), allow_unicode=True)
        )
        assert ResourceRecord.model_validate(dumped).license_spdx == token


def test_snapshot_records_measured_queries() -> None:
    snap = repo.load_snapshot()
    assert snap is not None
    assert snap.unique_repos > 0
    assert all(q.total_count > 0 for q in snap.queries)


# ---------------------------------------------------------------------------
# harvest 管线：枚举去重 / reconcile 保分类 / 镜像带 provenance（全部假 _gh_json）
# ---------------------------------------------------------------------------
from fde_scope.resources import harvest  # noqa: E402


def _search_item(full_name: str, *, stars: int = 5, spdx: str | None = "MIT", desc: str = "d") -> dict:
    return {
        "full_name": full_name,
        "html_url": f"https://github.com/{full_name}",
        "description": desc,
        "stargazers_count": stars,
        "updated_at": "2026-01-02T00:00:00Z",
        "default_branch": "main",
        "fork": False,
        "archived": False,
        "license": {"spdx_id": spdx} if spdx else None,
    }


def test_querires_are_the_single_source_pinned_in_snapshot() -> None:
    snap = repo.load_snapshot()
    assert snap is not None
    assert {q.query for q in snap.queries} == set(harvest.QUERIES)


def test_enumerate_dedups_across_queries_and_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_pages: dict[str, list[int]] = {}

    def fake_gh(args: list[str]) -> dict:
        q = next(a for a in args if a.startswith("q="))[2:]
        page = int(next(a for a in args if a.startswith("page="))[5:])
        seen_pages.setdefault(q, []).append(page)
        if q == harvest.QUERIES[0]:
            return {"total_count": 1, "items": [_search_item("acme/demo")]}
        if q == harvest.QUERIES[1]:
            return {"total_count": 1, "items": [_search_item("acme/demo")]}  # dup → union keeps one
        return {"total_count": 1, "items": [_search_item("other/new")]}

    monkeypatch.setattr(harvest, "_gh_json", fake_gh)
    found = harvest.enumerate_repos(max_pages=2, snapshot_at="2026-01-02")
    assert set(found.repos) == {"acme/demo", "other/new"}
    assert {s.query for s in found.snapshots} == set(harvest.QUERIES)
    # 每页 < PER_PAGE（只有 1 条）→ 首页即停，实采页数诚实为 1。
    assert all(s.pages_fetched == 1 for s in found.snapshots)


def test_reconcile_preserves_classification_and_defaults_new_to_noise() -> None:
    existing = [_base(slug="demo-repo", repo="acme/demo", relevance="adjacent", categories=["roadmap"])]
    found = {
        "acme/demo": _search_item("acme/demo", stars=999),  # refreshed facts
        "brand/new-repo": _search_item("brand/new-repo", spdx=None),  # unseen → noise
    }
    merged = harvest.reconcile(existing, found, snapshot_at="2026-02-02")
    by_repo = {r.repo: r for r in merged}
    demo = by_repo["acme/demo"]
    assert demo.relevance == "adjacent"  # classification preserved
    assert demo.categories == ["roadmap"]
    assert demo.stars == 999  # facts refreshed
    new = by_repo["brand/new-repo"]
    assert new.relevance == "noise" and new.categories == ["uncategorized"] and new.mirror is False


def test_reconcile_downgrades_mirror_when_license_sours() -> None:
    mirrored = _base(
        repo="acme/demo",
        slug="demo-repo",
        mirror=True,
        mirror_reason=None,
        files=[
            MirrorFile(path="README.md", local_name="README.md", blob_sha="a" * 40, retrieved_at="2026-01-01")
        ],
    )
    found = {"acme/demo": _search_item("acme/demo", spdx=None)}  # license → NOASSERTION
    merged = harvest.reconcile([mirrored], found, snapshot_at="2026-02-02")
    rec = next(r for r in merged if r.repo == "acme/demo")
    assert rec.mirror is False and rec.files == []
    assert "no longer permissive" in (rec.mirror_reason or "")


def test_mirror_repo_writes_provenance_and_reuses_unchanged_blob(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "mirror"
    monkeypatch.setattr(harvest, "MIRROR_ROOT", root)
    calls: list[str] = []

    def fake_gh(args: list[str]) -> object:
        key = " ".join(args)
        calls.append(key)
        if "git/trees" in key:
            return {"sha": "t1", "tree": [{"path": "README.md", "type": "blob", "sha": "b1"}]}
        if "commits/" in key:
            return {"sha": "c-sha-123"}
        if "git/blobs/b1" in key:
            import base64

            return {"encoding": "base64", "content": base64.b64encode(b"# Hello world").decode()}
        return None

    monkeypatch.setattr(harvest, "_gh_json", fake_gh)
    rec = _base(repo="acme/demo", slug="demo-repo", mirror=False, mirror_reason="pending", files=[])
    out, spent = harvest.mirror_repo(rec, budget_total_remaining=1_000_000, snapshot_at="2026-02-02")
    assert out.mirror is True and out.mirror_reason is None
    assert [f.path for f in out.files] == ["README.md"] and out.files[0].blob_sha == "b1"
    written = root / "acme__demo" / "README.md"
    assert written.is_file()
    head = written.read_text(encoding="utf-8")
    assert "fde-scope mirror" in head and "acme/demo" in head and "c-sha-123" in head and "README.md" in head
    assert spent > 0

    # 增量：blob_sha 未变 → 第二轮不再抓该 blob。
    calls.clear()
    out2, _ = harvest.mirror_repo(out, budget_total_remaining=1_000_000, snapshot_at="2026-03-03")
    assert out2.files[0].blob_sha == "b1"
    assert not any("git/blobs/b1" in c for c in calls)  # 未重写


def test_run_harvest_offline_touches_no_network(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: object, **k: object) -> None:
        raise AssertionError("offline harvest must not call gh")

    monkeypatch.setattr(harvest, "_gh_json", boom)
    monkeypatch.setattr(repo, "_DATA_DIR", tmp_path)
    repo.save_resources([_base()])
    repo.save_snapshot(Snapshot(queries=[], unique_repos=1))
    snap = harvest.run_harvest(offline=True)
    assert snap.unique_repos == 1
    assert repo.load_resources(tmp_path / "resources.yaml")[0].slug == "demo-repo"


# ---------------------------------------------------------------------------
# 落盘产物 ⇔ 清单：a（镜像目录/文件对齐）· e（README 计数）· f（provenance 头）·
# j（NOTICE 逐仓条目）。这些都是仓库里已提交的静态产物，读盘即可、不触网，
# 与 ``make check-resources`` 同源；放这里是让 `make test` 也钉死它们。
# ---------------------------------------------------------------------------
import re  # noqa: E402
from pathlib import Path  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
_GR = _ROOT / "docs" / "github-resources"
_MIRROR = _GR / "mirror"
_README = _GR / "README.md"
_NOTICE = _ROOT / "NOTICE"
_COUNTS_RE = re.compile(r"建档仓库 (\d+) 个 · 逐字镜像 (\d+) 个仓库 · 镜像文件 (\d+) 个")


def _mirrored_records() -> list[ResourceRecord]:
    return [r for r in repo.load_resources() if r.mirror]


def test_every_mirror_true_record_has_matching_dir_and_files() -> None:
    """不变量 a：每个 mirror:true 都有磁盘目录，目录里的 .md 集合 == files[].local_name。"""
    for rec in _mirrored_records():
        d = _MIRROR / rec.mirror_dir
        assert d.is_dir(), f"mirror:true 缺磁盘目录：{rec.mirror_dir}"
        on_disk = {p.name for p in d.glob("*.md")}
        assert on_disk == {f.local_name for f in rec.files}, rec.mirror_dir
        # 镜像 ⇒ 许可可再分发且非 noise（模型层的不变量在磁盘侧复核）。
        assert is_permissive(rec.license_spdx)
        assert rec.relevance != "noise"


def test_no_orphan_mirror_dirs_without_manifest_record() -> None:
    """不变量 a 反向：磁盘上每个镜像目录都归某条 mirror:true 记录，无孤儿。"""
    assert _MIRROR.is_dir(), "逐字镜像根目录缺失（应随仓库提交）"
    by_dir = {r.mirror_dir for r in _mirrored_records()}
    on_disk = {p.name for p in _MIRROR.iterdir() if p.is_dir()}
    assert on_disk - by_dir == set()


def test_mirror_files_carry_provenance_header_matching_manifest() -> None:
    """不变量 f：每个镜像文件字节头含 repo / license / commit / upstream path，
    且头内 license 与清单一致——正文一旦脱离溯源就失去再分发依据。"""
    for rec in _mirrored_records():
        for name in {f.local_name for f in rec.files}:
            head = (_MIRROR / rec.mirror_dir / name).read_text(encoding="utf-8", errors="replace")[:600]
            assert "fde-scope mirror" in head, f"{rec.mirror_dir}/{name}: 缺 provenance 头"
            assert f"repo: {rec.repo}" in head, f"{rec.mirror_dir}/{name}: 头内 repo 与清单不符"
            assert f"license: {rec.license_spdx}" in head, f"{rec.mirror_dir}/{name}: 头内 license 与清单不符"
            assert "commit: " in head and "upstream path: " in head, f"{rec.mirror_dir}/{name}: 头缺字段"


def test_readme_declared_counts_match_manifest_and_disk() -> None:
    """不变量 e：README 头部声明的三个数字 == manifest 记录数 / mirror:true 数 / 磁盘 .md 数。"""
    text = _README.read_text(encoding="utf-8")
    m = _COUNTS_RE.search(text)
    assert m is not None, "README 缺「建档仓库 N 个 · 逐字镜像 N 个仓库 · 镜像文件 N 个」声明行"
    declared_total, declared_mir, declared_files = (int(x) for x in m.groups())
    recs = repo.load_resources()
    mirrored = _mirrored_records()
    disk_md = sum(len({f.local_name for f in r.files}) for r in mirrored)
    assert declared_total == len(recs)
    assert declared_mir == len(mirrored)
    assert declared_files == disk_md


def test_notice_lists_every_mirrored_repo() -> None:
    """不变量 j：每个镜像仓库在 NOTICE 里逐条署名（含其 repo 名）。"""
    notice = _NOTICE.read_text(encoding="utf-8")
    for rec in _mirrored_records():
        assert rec.repo in notice, f"NOTICE 缺镜像仓库条目：{rec.repo}"


def test_stored_decision_clauses_are_all_translatable_to_en() -> None:
    """/en/resources 用 :data:`_DECISION_CLAUSES_EN` 子句字典翻译存储的许可决定串；
    若 ``harvest._decision`` 新增一个中文子句而字典没跟上，英文页会回退成原文、
    漏出 CJK。这里把「落盘数据里出现的每个子句」钉在字典键集内（字典值本身由
    ``test_web`` 的 en 页测试守）。"""
    from fde_scope.web.resources import _DECISION_CLAUSES_EN

    for rec in repo.load_resources():
        tail = rec.license_decision_applied.partition(" → ")[2]
        assert tail in _DECISION_CLAUSES_EN, f"{rec.repo}: 子句 {tail!r} 无英文映射"
