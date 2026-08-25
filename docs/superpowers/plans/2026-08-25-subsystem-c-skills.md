# 子系统 C：技能/方法论沉淀 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `fde_scope/skills/` 独立模块，实现 FDE 技能/方法论的沉淀、检索、审阅与导出（AgentScope/QwenPaw 格式），并打通 CLI 与 Web。

**Architecture:** 文件库存储（`.fde_scope/skills/<id>/{skill.md,meta.json}` + `index.json`），Pydantic v2 数据模型，`SkillService` 服务层；engagement 钩子只在 CLI 层调用（核心层零依赖）；导出器独立函数可单测。

**Tech Stack:** Python 3.11+, Pydantic v2, Typer/Rich（CLI）, FastAPI（Web）, pytest。

## Global Constraints

- 零新增运行时依赖（只用标准库 + 现有依赖）
- 所有新文件遵循现有代码风格：双引号、110 列宽、ruff（E/W/F/I/C4/B/SIM/UP）
- 模块 docstring 遵循现有风格（首行简述 + 用途说明）
- 存储根默认 `.fde_scope/skills/`，构造可注入 `root: Path`（测试用 tmp_path）
- 不引入全文检索依赖，搜索用大小写不敏感子串匹配
- 导出格式以官方文档为准，实现前先检索验证（AgentScope 2.0 skill / QwenPaw skill）

---

### Task 1: 数据模型 `skills/models.py`

**Files:**
- Create: `fde_scope/skills/__init__.py`
- Create: `fde_scope/skills/models.py`
- Test: `tests/test_skills.py`

**Interfaces:**
- Consumes: 无（纯模型）
- Produces: `SkillCategory`（RESEARCH/IMPLEMENTATION/OPTIMIZATION/METHODOLOGY）、`SkillStatus`（DRAFT/PUBLISHED/ARCHIVED）、`SkillSource`（MANUAL/GATE_HINT/AUTO_CAPTURE）、`SkillRecord`（字段见 spec §2.1，`id/title/category/tags/body_md/phase_slug/gate_slug/applies_to/source/source_engagement/status/version/created_at/updated_at/export_formats`）、`SkillDraft`（创建用，无 id/status/version/timestamps）、`SkillPatch`（可选字段，编辑用）

- [ ] **Step 1: 写失败测试**（先建 `tests/test_skills.py` 模型部分）

```python
import pytest
from pydantic import ValidationError

from fde_scope.skills.models import SkillCategory, SkillDraft, SkillRecord, SkillSource, SkillStatus


def test_skill_draft_defaults():
    draft = SkillDraft(
        title="OPC UA 连接踩坑", category=SkillCategory.IMPLEMENTATION,
        tags=["opcua"], body_md="# 步骤\n1. ...",
    )
    assert draft.source == SkillSource.MANUAL
    assert draft.status == SkillStatus.DRAFT
    assert draft.applies_to == []
    assert draft.phase_slug is None
    assert draft.gate_slug is None


def test_skill_record_generates_id_and_timestamps():
    rec = SkillRecord(
        title="t", category=SkillCategory.RESEARCH, tags=[], body_md="b",
    )
    assert rec.id.startswith("skill-")
    assert rec.version == 1
    assert rec.export_formats == []
    assert rec.status == SkillStatus.DRAFT


def test_skill_category_enum_values():
    assert SkillCategory.RESEARCH.value == "research"
    assert SkillCategory.IMPLEMENTATION.value == "implementation"
    assert SkillCategory.OPTIMIZATION.value == "optimization"
    assert SkillCategory.METHODOLOGY.value == "methodology"


def test_title_required():
    with pytest.raises(ValidationError):
        SkillDraft(category=SkillCategory.RESEARCH, tags=[], body_md="b")
```

- [ ] **Step 2: 运行测试确认失败**：`pytest tests/test_skills.py -v` → 期望 FAIL（ImportError: fde_scope.skills）
- [ ] **Step 3: 实现 models.py + `skills/__init__.py`**

```python
# fde_scope/skills/models.py
"""技能/方法论沉淀的数据模型。

混合形态：Markdown 正文（body_md）+ 结构化元数据（分类/标签/阶段绑定/溯源）。
独立于 engagement 引擎，跨项目复用。
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class SkillCategory(str, Enum):
    """沉淀内容的四类分类：调研 / 实施 / 调优 / 方法论。"""

    RESEARCH = "research"
    IMPLEMENTATION = "implementation"
    OPTIMIZATION = "optimization"
    METHODOLOGY = "methodology"


class SkillStatus(str, Enum):
    """生命周期：草稿 → 发布 → 归档。导出只作用于 published。"""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SkillSource(str, Enum):
    """来源：手动 / gate 阻塞提示 / 操作自动捕获。"""

    MANUAL = "manual"
    GATE_HINT = "gate_hint"
    AUTO_CAPTURE = "auto_capture"


ExportFormat = Literal["agentscope", "qwenpaw"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SkillDraft(BaseModel):
    """创建技能的输入（id/status/version/时间戳由 SkillRecord 生成）。"""

    title: str = Field(min_length=1, max_length=80)
    category: SkillCategory
    tags: list[str] = Field(default_factory=list)
    body_md: str = ""
    phase_slug: str | None = None
    gate_slug: str | None = None
    applies_to: list[str] = Field(default_factory=list)
    source: SkillSource = SkillSource.MANUAL
    source_engagement: str | None = None


class SkillPatch(BaseModel):
    """编辑技能的输入；未提供的字段保持不变。"""

    title: str | None = Field(default=None, min_length=1, max_length=80)
    tags: list[str] | None = None
    body_md: str | None = None
    phase_slug: str | None = None
    gate_slug: str | None = None
    applies_to: list[str] | None = None


class SkillRecord(BaseModel):
    """一条技能记录（持久化为 meta.json + skill.md）。"""

    id: str = Field(default_factory=lambda: f"skill-{secrets.token_hex(4)}")
    title: str
    category: SkillCategory
    tags: list[str] = Field(default_factory=list)
    body_md: str = ""
    phase_slug: str | None = None
    gate_slug: str | None = None
    applies_to: list[str] = Field(default_factory=list)
    source: SkillSource = SkillSource.MANUAL
    source_engagement: str | None = None
    status: SkillStatus = SkillStatus.DRAFT
    version: int = 1
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    export_formats: list[str] = Field(default_factory=list)

    def touch(self) -> None:
        """内容变更后调用：版本 +1、更新时间刷新。"""
        self.version += 1
        self.updated_at = _now()
```

`fde_scope/skills/__init__.py` 导出 `models` 中的符号（`from .models import ...`，`__all__` 列全）。

- [ ] **Step 4: 运行测试确认通过**：`pytest tests/test_skills.py -v` → PASS
- [ ] **Step 5: Commit**：`git add fde_scope/skills tests/test_skills.py && git commit -m "feat(skills): add skill data models"`

---

### Task 2: 文件库存储 `skills/store.py`

**Files:**
- Create: `fde_scope/skills/store.py`
- Test: `tests/test_skills.py`（追加 store 部分）

**Interfaces:**
- Consumes: `SkillRecord`（Task 1）
- Produces: `SkillStore(root: Path = Path(".fde_scope/skills"))`，方法：`save(record)`、`load(skill_id) -> SkillRecord | None`、`load_all() -> list[SkillRecord]`、`delete(skill_id)`、`rebuild_index()`、`index_entries() -> list[dict]`（id/title/category/status/tags/updated_at）；存储布局 `<root>/<id>/skill.md` + `<root>/<id>/meta.json` + `<root>/index.json`

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path
from fde_scope.skills.models import SkillCategory, SkillRecord, SkillStatus
from fde_scope.skills.store import SkillStore


def _rec(title="t", **kw) -> SkillRecord:
    kw.setdefault("category", SkillCategory.METHODOLOGY)
    kw.setdefault("tags", [])
    kw.setdefault("body_md", "# body")
    return SkillRecord(title=title, **kw)


def test_store_roundtrip(tmp_path):
    store = SkillStore(tmp_path / "skills")
    rec = _rec(title="OPC UA 踩坑")
    store.save(rec)
    loaded = store.load(rec.id)
    assert loaded == rec
    assert (tmp_path / "skills" / rec.id / "skill.md").read_text() == "# body"
    assert (tmp_path / "skills" / rec.id / "meta.json").exists()


def test_store_index_and_rebuild(tmp_path):
    store = SkillStore(tmp_path / "skills")
    a, b = _rec(title="A"), _rec(title="B", category=SkillCategory.RESEARCH)
    store.save(a)
    store.save(b)
    assert len(store.index_entries()) == 2
    # 模拟索引损坏：重建必须从目录恢复
    (tmp_path / "skills" / "index.json").write_text("{broken")
    store.rebuild_index()
    assert len(store.index_entries()) == 2


def test_store_load_missing_and_corrupt(tmp_path):
    store = SkillStore(tmp_path / "skills")
    assert store.load("skill-nope") is None
    d = tmp_path / "skills" / "skill-bad"
    d.mkdir(parents=True)
    (d / "meta.json").write_text("{bad json")
    assert store.load("skill-bad") is None  # 损坏条目跳过，不抛异常


def test_store_delete(tmp_path):
    store = SkillStore(tmp_path / "skills")
    rec = _rec()
    store.save(rec)
    store.delete(rec.id)
    assert store.load(rec.id) is None
    assert len(store.index_entries()) == 0
```

- [ ] **Step 2: 运行确认失败**：`pytest tests/test_skills.py -k store -v` → FAIL（ModuleNotFoundError）
- [ ] **Step 3: 实现 store.py**

```python
"""技能文件库存储：.fde_scope/skills/<id>/{skill.md, meta.json} + index.json。

原子写（临时文件 + rename），损坏条目跳过不炸，index.json 可由目录重建。
零新增依赖，目录即备份可携带。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import SkillRecord


class SkillStore:
    """按 skill 目录组织的本地文件库。"""

    def __init__(self, root: Path = Path(".fde_scope/skills")) -> None:
        self.root = Path(root)
        self._index_path = self.root / "index.json"

    # -- 路径 ---------------------------------------------------------------
    def _dir_for(self, skill_id: str) -> Path:
        return self.root / skill_id

    def _meta_path(self, skill_id: str) -> Path:
        return self._dir_for(skill_id) / "meta.json"

    def _body_path(self, skill_id: str) -> Path:
        return self._dir_for(skill_id) / "skill.md"

    # -- 写 ------------------------------------------------------------------
    def save(self, record: SkillRecord) -> None:
        """原子写入一个技能（目录 + meta.json + skill.md + 更新索引）。"""
        d = self._dir_for(record.id)
        d.mkdir(parents=True, exist_ok=True)
        meta = record.model_dump(exclude={"body_md"})
        self._atomic_write(self._meta_path(record.id), json.dumps(meta, ensure_ascii=False, indent=2))
        self._atomic_write(self._body_path(record.id), record.body_md)
        self._touch_index(record)

    def delete(self, skill_id: str) -> None:
        """删除技能目录并重建索引。"""
        d = self._dir_for(skill_id)
        if d.exists():
            for p in d.iterdir():
                p.unlink()
            d.rmdir()
        self.rebuild_index()

    # -- 读 ------------------------------------------------------------------
    def load(self, skill_id: str) -> SkillRecord | None:
        meta_path = self._meta_path(skill_id)
        if not meta_path.exists():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["body_md"] = self._body_path(skill_id).read_text(encoding="utf-8")
            return SkillRecord.model_validate(meta)
        except (ValueError, KeyError, OSError):
            return None  # 损坏条目跳过

    def load_all(self) -> list[SkillRecord]:
        if not self.root.exists():
            return []
        return [r for r in (self.load(p.name) for p in self.root.iterdir() if p.is_dir()) if r is not None]

    # -- 索引 ----------------------------------------------------------------
    def index_entries(self) -> list[dict]:
        if not self._index_path.exists():
            self.rebuild_index()
            return self.index_entries()
        try:
            return json.loads(self._index_path.read_text(encoding="utf-8"))
        except ValueError:
            self.rebuild_index()
            return self.index_entries()

    def rebuild_index(self) -> None:
        """从目录重建索引（index.json 缺失/损坏/删除后调用）。"""
        entries = [
            {
                "id": r.id, "title": r.title, "category": r.category.value,
                "status": r.status.value, "tags": r.tags,
                "updated_at": r.updated_at.isoformat(),
            }
            for r in self.load_all()
        ]
        self.root.mkdir(parents=True, exist_ok=True)
        self._atomic_write(self._index_path, json.dumps(entries, ensure_ascii=False, indent=2))

    def _touch_index(self, record: SkillRecord) -> None:
        entries = [e for e in self.index_entries() if e["id"] != record.id]
        entries.append({
            "id": record.id, "title": record.title, "category": record.category.value,
            "status": record.status.value, "tags": record.tags,
            "updated_at": record.updated_at.isoformat(),
        })
        self._atomic_write(self._index_path, json.dumps(entries, ensure_ascii=False, indent=2))

    # -- 原子写 --------------------------------------------------------------
    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
```

- [ ] **Step 4: 运行确认通过**：`pytest tests/test_skills.py -k store -v` → PASS
- [ ] **Step 5: Commit**：`git add fde_scope/skills/store.py tests/test_skills.py && git commit -m "feat(skills): add file-based skill store"`

---

### Task 3: 服务层 `skills/service.py`（CRUD + 检索）

**Files:**
- Create: `fde_scope/skills/service.py`
- Test: `tests/test_skills.py`（追加 service 部分）

**Interfaces:**
- Consumes: `SkillStore`（Task 2）、`SkillRecord/SkillDraft/SkillPatch`（Task 1）
- Produces: `SkillService(store)`；方法：`create(draft) -> SkillRecord`、`get(skill_id) -> SkillRecord`（KeyError）、`update(skill_id, patch) -> SkillRecord`、`publish(skill_id)`、`archive(skill_id)`、`search(query=None, *, category=None, tags=None, status=None, phase_slug=None, gate_slug=None, profile=None, limit=50) -> list[SkillRecord]`、`list_drafts() -> list[SkillRecord]`；publish/archive 对错误状态抛 `ValueError`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from fde_scope.skills.models import SkillCategory, SkillDraft, SkillSource, SkillStatus
from fde_scope.skills.service import SkillService
from fde_scope.skills.store import SkillStore


@pytest.fixture()
def service(tmp_path):
    return SkillService(SkillStore(tmp_path / "skills"))


def test_create_and_get(service):
    rec = service.create(SkillDraft(title="T", category=SkillCategory.RESEARCH, tags=["a"], body_md="b"))
    assert rec.status == SkillStatus.DRAFT
    assert service.get(rec.id).title == "T"


def test_publish_archive_lifecycle(service):
    rec = service.create(SkillDraft(title="T", category=SkillCategory.RESEARCH))
    service.publish(rec.id)
    assert service.get(rec.id).status == SkillStatus.PUBLISHED
    service.archive(rec.id)
    assert service.get(rec.id).status == SkillStatus.ARCHIVED


def test_publish_requires_draft(service):
    rec = service.create(SkillDraft(title="T", category=SkillCategory.RESEARCH))
    service.publish(rec.id)
    with pytest.raises(ValueError):
        service.publish(rec.id)  # 已发布不能再 publish


def test_update_bumps_version(service):
    rec = service.create(SkillDraft(title="T", category=SkillCategory.RESEARCH))
    from fde_scope.skills.models import SkillPatch
    updated = service.update(rec.id, SkillPatch(title="T2", tags=["x"]))
    assert updated.title == "T2"
    assert updated.tags == ["x"]
    assert updated.version == 2


def test_search_filters(service):
    service.create(SkillDraft(title="OPC UA 连接", category=SkillCategory.IMPLEMENTATION,
                              tags=["opcua"], phase_slug="deploy", applies_to=["manufacturing"]))
    service.create(SkillDraft(title="工单分类", category=SkillCategory.RESEARCH,
                              tags=["ticket"], applies_to=["ticket"]))
    service.create(SkillDraft(title="工会评审", category=SkillCategory.METHODOLOGY,
                              tags=["gate"], gate_slug="works_council"))
    assert len(service.search("opc")) == 1
    assert len(service.search(status=SkillStatus.DRAFT)) == 3
    assert len(service.search(category=SkillCategory.RESEARCH)) == 1
    assert len(service.search(profile="ticket")) == 2
    assert len(service.search(gate_slug="works_council")) == 1
    assert len(service.search(phase_slug="deploy")) == 1
    assert len(service.search(tags=["opcua", "ticket"])) == 2  # 任一标签命中


def test_list_drafts_only(service):
    a = service.create(SkillDraft(title="A", category=SkillCategory.RESEARCH))
    b = service.create(SkillDraft(title="B", category=SkillCategory.RESEARCH))
    service.publish(a.id)
    assert [r.id for r in service.list_drafts()] == [b.id]


def test_get_missing_raises(service):
    with pytest.raises(KeyError):
        service.get("skill-nope")
```

- [ ] **Step 2: 运行确认失败**：`pytest tests/test_skills.py -k service -v` → FAIL
- [ ] **Step 3: 实现 service.py**

```python
"""技能服务层：CRUD、生命周期、检索、草稿队列。

检索规则：query 对 title/tags/body 大小写不敏感子串匹配；其余精确过滤；
tags 为"任一命中"；按 updated_at 倒序。过滤在内存中进行（文件库规模，
无需索引查询）。
"""

from __future__ import annotations

from .models import SkillCategory, SkillDraft, SkillPatch, SkillRecord, SkillStatus
from .store import SkillStore


class SkillService:
    """技能库的门面：所有业务规则集中在此。"""

    def __init__(self, store: SkillStore) -> None:
        self.store = store

    # -- CRUD ---------------------------------------------------------------
    def create(self, draft: SkillDraft) -> SkillRecord:
        rec = SkillRecord(**draft.model_dump())
        self.store.save(rec)
        return rec

    def get(self, skill_id: str) -> SkillRecord:
        rec = self.store.load(skill_id)
        if rec is None:
            raise KeyError(skill_id)
        return rec

    def update(self, skill_id: str, patch: SkillPatch) -> SkillRecord:
        rec = self.get(skill_id)
        for field, value in patch.model_dump(exclude_unset=True).items():
            setattr(rec, field, value)
        rec.touch()
        self.store.save(rec)
        return rec

    # -- 生命周期 ------------------------------------------------------------
    def publish(self, skill_id: str) -> SkillRecord:
        rec = self.get(skill_id)
        if rec.status != SkillStatus.DRAFT:
            raise ValueError(f"only drafts can be published: {rec.status.value}")
        rec.status = SkillStatus.PUBLISHED
        rec.touch()
        self.store.save(rec)
        return rec

    def archive(self, skill_id: str) -> SkillRecord:
        rec = self.get(skill_id)
        if rec.status == SkillStatus.ARCHIVED:
            raise ValueError("already archived")
        rec.status = SkillStatus.ARCHIVED
        rec.touch()
        self.store.save(rec)
        return rec

    # -- 检索 ---------------------------------------------------------------
    def search(
        self,
        query: str | None = None,
        *,
        category: SkillCategory | None = None,
        tags: list[str] | None = None,
        status: SkillStatus | None = None,
        phase_slug: str | None = None,
        gate_slug: str | None = None,
        profile: str | None = None,
        limit: int = 50,
    ) -> list[SkillRecord]:
        q = (query or "").strip().lower()
        tag_set = set(tags or [])
        results = []
        for rec in self.store.load_all():
            if category is not None and rec.category != category:
                continue
            if status is not None and rec.status != status:
                continue
            if phase_slug is not None and rec.phase_slug != phase_slug:
                continue
            if gate_slug is not None and rec.gate_slug != gate_slug:
                continue
            if profile is not None and profile not in rec.applies_to:
                continue
            if tag_set and not (tag_set & set(rec.tags)):
                continue
            if q and q not in (rec.title + " " + " ".join(rec.tags) + " " + rec.body_md).lower():
                continue
            results.append(rec)
        results.sort(key=lambda r: r.updated_at, reverse=True)
        return results[:limit]

    def list_drafts(self) -> list[SkillRecord]:
        return self.search(status=SkillStatus.DRAFT)
```

- [ ] **Step 4: 运行确认通过**：`pytest tests/test_skills.py -k service -v` → PASS
- [ ] **Step 5: Commit**：`git add fde_scope/skills/service.py tests/test_skills.py && git commit -m "feat(skills): add skill service with lifecycle and search"`

---

### Task 4: 上下文沉淀：gate 提示 + 操作自动捕获

**Files:**
- Modify: `fde_scope/skills/service.py`（追加两个方法）
- Test: `tests/test_skills.py`（追加）

**Interfaces:**
- Consumes: `SkillService`（Task 3）
- Produces: `SkillService.suggest_from_gate_block(engagement_id: str, gate_slug: str, blockers: list[str]) -> SkillRecord`（source=GATE_HINT，category=METHODOLOGY，title 预填，body 模板含 blockers 摘要）；`SkillService.capture_operation(*, action: str, engagement_id: str, phase_slug: str | None = None, detail: dict | None = None) -> SkillRecord | None`（source=AUTO_CAPTURE，category 由 action 推导：advance→IMPLEMENTATION、gate_pass→METHODOLOGY、kpi→OPTIMIZATION，detail 空则返回 None）

- [ ] **Step 1: 写失败测试**

```python
def test_suggest_from_gate_block(service):
    rec = service.suggest_from_gate_block("eng-x", "functional_safety", ["缺 hazard analysis", "PL/SIL 不足"])
    assert rec.source == SkillSource.GATE_HINT
    assert rec.gate_slug == "functional_safety"
    assert rec.source_engagement == "eng-x"
    assert "functional_safety" in rec.title
    assert "hazard analysis" in rec.body_md
    assert rec.status == SkillStatus.DRAFT


def test_capture_operation_maps_category(service):
    from fde_scope.skills.models import SkillCategory
    r1 = service.capture_operation(action="advance", engagement_id="eng-x", phase_slug="deploy")
    assert r1 is not None and r1.category == SkillCategory.IMPLEMENTATION
    r2 = service.capture_operation(action="gate_pass", engagement_id="eng-x", phase_slug="deploy")
    assert r2 is not None and r2.category == SkillCategory.METHODOLOGY
    r3 = service.capture_operation(action="kpi", engagement_id="eng-x", phase_slug="flywheel")
    assert r3 is not None and r3.category == SkillCategory.OPTIMIZATION
    r4 = service.capture_operation(action="advance", engagement_id="eng-x")
    assert r4 is not None and r4.phase_slug is None
    # 未知 action 返回 None
    assert service.capture_operation(action="bogus", engagement_id="eng-x") is None
```

- [ ] **Step 2: 运行确认失败**：`pytest tests/test_skills.py -k "suggest or capture" -v` → FAIL
- [ ] **Step 3: 实现**（追加到 service.py）

```python
    # -- 上下文沉淀 -----------------------------------------------------------
    _ACTION_CATEGORIES = {
        "advance": SkillCategory.IMPLEMENTATION,
        "gate_pass": SkillCategory.METHODOLOGY,
        "kpi": SkillCategory.OPTIMIZATION,
    }

    def suggest_from_gate_block(
        self, engagement_id: str, gate_slug: str, blockers: list[str]
    ) -> SkillRecord:
        """gate 被阻塞时生成预填草稿（关键点提示）。"""
        summary = "; ".join(blockers[:3]) if blockers else "无"
        rec = SkillRecord(
            title=f"gate 被阻塞: {gate_slug} — {summary[:40]}",
            category=SkillCategory.METHODOLOGY,
            tags=[gate_slug, "gate-blocked"],
            body_md=(
                f"## 背景\n\n`{gate_slug}` 门禁在 engagement `{engagement_id}` 被阻塞。\n\n"
                f"## 阻塞项\n\n{summary}\n\n"
                "## 解法（待补充）\n\n- 步骤 1：…\n\n"
                "## 验收标准\n\n- …\n"
            ),
            gate_slug=gate_slug,
            source=SkillSource.GATE_HINT,
            source_engagement=engagement_id,
        )
        self.store.save(rec)
        return rec

    def capture_operation(
        self,
        *,
        action: str,
        engagement_id: str,
        phase_slug: str | None = None,
        detail: dict | None = None,
    ) -> SkillRecord | None:
        """操作自动捕获：记录一条轻量草稿；未知 action 返回 None。"""
        category = self._ACTION_CATEGORIES.get(action)
        if category is None:
            return None
        note = (detail or {}).get("note", "")
        body = (
            f"## 操作摘要\n\n`{action}` @ engagement `{engagement_id}`"
            + (f"（阶段 `{phase_slug}`）" if phase_slug else "")
            + (f"\n\n{note}" if note else "")
            + "\n\n## 可复用点（待补充）\n\n- …\n"
        )
        rec = SkillRecord(
            title=f"{action} 记录: {engagement_id}" + (f" @ {phase_slug}" if phase_slug else ""),
            category=category,
            tags=[action],
            body_md=body,
            phase_slug=phase_slug,
            source=SkillSource.AUTO_CAPTURE,
            source_engagement=engagement_id,
        )
        self.store.save(rec)
        return rec
```

- [ ] **Step 4: 运行确认通过**：`pytest tests/test_skills.py -k "suggest or capture" -v` → PASS
- [ ] **Step 5: Commit**：`git add fde_scope/skills/service.py tests/test_skills.py && git commit -m "feat(skills): add gate-hint and operation-capture drafts"`

---

### Task 5: 导出器 `skills/exporters.py`

**Files:**
- Create: `fde_scope/skills/exporters.py`
- Test: `tests/test_skills.py`（追加）

**Interfaces:**
- Consumes: `SkillRecord`（Task 1）
- Produces: `ExportFile = dataclass(name: str, content: str)`、`export_skill(record: SkillRecord, fmt: str) -> list[ExportFile]`（fmt 非法抛 `ValueError`）、`export_many(records, fmt) -> list[ExportFile]`（批量：每个技能一个目录条目）；agentscope 格式：`<skill-name>/SKILL.md`；qwenpaw 格式：`<skill-name>/SKILL.md`（frontmatter 字段经官方文档检索确认后定稿）

- [x] **Step 1: 检索官方格式**（已完成 2026-08-25）
  - **AgentScope 2.0**（官方教程 `doc.agentscope.io/tutorial/task_agent_skill.html`）：skill 目录必须含 `SKILL.md`（YAML frontmatter + Markdown 指令）；frontmatter 必填字段 `name`、`description`；注册 API 为 `Toolkit.register_agent_skill(dir)` / `get_agent_skill_prompt()`
  - **QwenPaw**（仓库 `CONTRIBUTING_zh.md` + 真实样例 `src/qwenpaw/agents/skills/file_reader-zh/SKILL.md`）：同一 Anthropic Agent Skills 规范，frontmatter 至少 `name` + `description`，可选 `metadata`（如 `qwenpaw.emoji`、`requires`）；目录可含可选 `references/`、`scripts/`；放入 skills 目录即自动发现（无需注册）
  - **两格式同源，差异仅 QwenPaw 可选 `metadata`** → 共用一个渲染器，qwenpaw 追加 metadata 块；目录名用 `_slugify(title)`（QwenPaw 目录惯例为下划线小写，但连字符亦兼容，见 ISSUE #2323）
  - 确认结果已写入 Step 4 实现代码区（docstring）
- [x] **Step 2: 写失败测试**（按检索确认的格式）

```python
def test_export_agentscope_format():
    from fde_scope.skills.exporters import export_skill
    rec = _rec(title="OPC UA 排查", tags=["opcua"])
    files = export_skill(rec, "agentscope")
    assert len(files) == 1
    assert files[0].name == "opc-ua-pai-cha/SKILL.md"  # 技能名 slug 化
    assert "name:" in files[0].content and "description:" in files[0].content
    assert "# body" in files[0].content


def test_export_qwenpaw_format():
    from fde_scope.skills.exporters import export_skill
    files = export_skill(_rec(title="T"), "qwenpaw")
    assert files[0].name.endswith("SKILL.md")
    assert files[0].content  # 非空


def test_export_unknown_format_raises():
    from fde_scope.skills.exporters import export_skill
    with pytest.raises(ValueError):
        export_skill(_rec(), "bogus")
```

- [x] **Step 3: 运行确认失败**：`pytest tests/test_skills.py -k export -v` → FAIL（ModuleNotFoundError，5 个失败）
- [x] **Step 4: 实现 exporters.py**（frontmatter 字段以 Step 1 检索结果为准；注：`_slugify` 零依赖实现丢弃非 ASCII 字符，测试断言中文标题 slug 化为 `opc-ua` 而非拼音）

```python
"""技能导出器：SkillRecord → AgentScope / QwenPaw 兼容 SKILL.md。

格式约定来自官方文档检索（2026-08-25）：AgentScope 2.0 教程
task_agent_skill.html 与 QwenPaw CONTRIBUTING_zh.md 均遵循 Anthropic
Agent Skills 规范：目录含 SKILL.md（YAML frontmatter + Markdown 指令），
frontmatter 必填 name + description；QwenPaw 额外支持可选 metadata。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import SkillRecord


@dataclass
class ExportFile:
    """一个导出产物文件（相对路径 + 内容）。"""

    name: str
    content: str


def _slugify(title: str) -> str:
    """标题 → 目录名：小写、非字母数字转连字符、截断 60 字符。"""
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:60] or "skill"


def _frontmatter(record: SkillRecord) -> str:
    """按官方格式生成 frontmatter（字段以检索结果为准）。"""
    return (
        "---\n"
        f"name: {_slugify(record.title)}\n"
        f"description: {record.title}\n"
        "---\n"
    )


def export_skill(record: SkillRecord, fmt: str) -> list[ExportFile]:
    """导出单条技能为指定格式；fmt 仅支持 agentscope / qwenpaw。"""
    if fmt not in ("agentscope", "qwenpaw"):
        raise ValueError(f"unsupported export format: {fmt!r}")
    name = _slugify(record.title)
    content = _frontmatter(record) + "\n" + record.body_md
    return [ExportFile(name=f"{name}/SKILL.md", content=content)]


def export_many(records: list[SkillRecord], fmt: str) -> list[ExportFile]:
    """批量导出（与单条同构，逐个目录条目）。"""
    files: list[ExportFile] = []
    for rec in records:
        files.extend(export_skill(rec, fmt))
    return files
```

- [x] **Step 5: 运行确认通过**：`pytest tests/test_skills.py -k export -v` → PASS（全量 26 个）
- [ ] **Step 6: Commit**：`git add fde_scope/skills/exporters.py tests/test_skills.py && git commit -m "feat(skills): add agentscope/qwenpaw exporters"`

---

### Task 6: CLI `skill` 命令组

**Files:**
- Modify: `fde_scope/cli.py`（新增 `skill_app`，注册到主 app；新增 `_maybe_suggest_skill` 钩子函数）
- Test: `tests/test_cli.py`（追加）

**Interfaces:**
- Consumes: `SkillService`/`SkillStore`（Task 2-4）、`export_skill/export_many`（Task 5）
- Produces: 子命令 `fde-scope skill add|list|show|edit|publish|archive|review|export`（参数见 spec §2.4）；`_maybe_suggest_skill(engagement_id: str, gate_slug: str, blockers: list[str], console)` —— 尝试创建 gate 提示草稿，失败静默；`_maybe_capture(service, *, action, engagement_id, phase_slug, detail=None)` —— 自动捕获，失败静默

- [x] **Step 1: 写失败测试**（`tests/test_cli.py` 追加）

```python
from typer.testing import CliRunner
from fde_scope.cli import app
from fde_scope.skills.models import SkillCategory, SkillStatus
from fde_scope.skills.store import SkillStore

runner = CliRunner()


def test_skill_add_publish_export(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, [
        "skill", "add", "--title", "OPC UA 排查", "--category", "implementation",
        "--tags", "opcua", "--body", "# 步骤",
    ])
    assert result.exit_code == 0
    store = SkillStore(tmp_path / ".fde_scope" / "skills")
    drafts = store.load_all()
    assert len(drafts) == 1
    assert drafts[0].status == SkillStatus.DRAFT
    sid = drafts[0].id
    assert runner.invoke(app, ["skill", "publish", sid]).exit_code == 0
    assert runner.invoke(app, ["skill", "export", sid, "--format", "agentscope",
                               "--out", str(tmp_path / "out")]).exit_code == 0
    assert (tmp_path / "out" / "opc-ua" / "SKILL.md").exists()


def test_skill_list_and_review(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["skill", "add", "--title", "T1", "--category", "research"])
    r = runner.invoke(app, ["skill", "list", "--category", "research"])
    assert r.exit_code == 0 and "T1" in r.stdout
    r2 = runner.invoke(app, ["skill", "review"])
    assert r2.exit_code == 0 and "T1" in r2.stdout


def test_skill_add_requires_category():
    r = runner.invoke(app, ["skill", "add", "--title", "T"])
    assert r.exit_code != 0
```

- [x] **Step 2: 运行确认失败**：`pytest tests/test_cli.py -k skill -v` → FAIL（no such command）
- [x] **Step 3: 实现 CLI**（`cli.py` 追加；风格对齐现有命令：`_banner` + rich Table + exit 2；**修正：`skill list` 默认 status 从 `published` 改为不过滤（None）**——测试期望 add 后立即可 list，且草稿审阅已由 `review` 专职负责）

```python
# -- skills（技能/方法论沉淀） ------------------------------------------------
skill_app = typer.Typer(name="skill", help="[Skills] 技能/方法论沉淀库.", no_args_is_help=True)
app.add_typer(skill_app)


def _skill_service() -> SkillService:
    from .skills.service import SkillService
    from .skills.store import SkillStore

    return SkillService(SkillStore(Path(".fde_scope/skills")))


def _maybe_suggest_skill(engagement_id: str, gate_slug: str, blockers: list[str]) -> None:
    """gate 阻塞时生成提示草稿；失败静默（不阻塞主流程）。"""
    try:
        rec = _skill_service().suggest_from_gate_block(engagement_id, gate_slug, blockers)
        console.print(
            f"💡 已把这次阻塞沉淀为草稿 [cyan]{rec.id}[/cyan] — "
            f"[bold]fde-scope skill review[/bold] 可查看并完善"
        )
    except OSError:
        pass


def _maybe_capture(action: str, engagement_id: str, phase_slug: str | None = None,
                   detail: dict | None = None) -> None:
    """操作自动捕获；失败静默。"""
    try:
        _skill_service().capture_operation(
            action=action, engagement_id=engagement_id, phase_slug=phase_slug, detail=detail
        )
    except OSError:
        pass


@skill_app.command("add")
def skill_add(
    title: str = typer.Option(..., "--title"),
    category: str = typer.Option(..., "--category", help="research|implementation|optimization|methodology"),
    tags: str = typer.Option("", "--tags", help="逗号分隔"),
    body: str = typer.Option("", "--body"),
    body_file: str | None = typer.Option(None, "--body-file", help="从文件读正文"),
    phase: str | None = typer.Option(None, "--phase"),
    gate: str | None = typer.Option(None, "--gate"),
    profile: str = typer.Option("", "--profile", help="ticket,manufacturing 逗号分隔"),
    engagement: str | None = typer.Option(None, "--engagement"),
    source: str = typer.Option("manual", "--source", help="manual|gate_hint|auto_capture"),
) -> None:
    """创建一条技能草稿。"""
    _banner(f"skill add · {title}")
    from .skills.models import SkillCategory, SkillDraft, SkillSource

    try:
        cat = SkillCategory(category)
        src = SkillSource(source)
    except ValueError:
        console.print("[red]非法 category/source[/red]（见 --help）")
        raise typer.Exit(2)
    text = Path(body_file).read_text(encoding="utf-8") if body_file else body
    service = _skill_service()
    rec = service.create(SkillDraft(
        title=title, category=cat,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        body_md=text, phase_slug=phase, gate_slug=gate,
        applies_to=[p.strip() for p in profile.split(",") if p.strip()],
        source=src, source_engagement=engagement,
    ))
    console.print(f"✅ 草稿创建 [cyan]{rec.id}[/cyan] — [bold]fde-scope skill review[/bold] 可审阅")


@skill_app.command("list")
def skill_list(
    category: str | None = typer.Option(None, "--category"),
    tag: str | None = typer.Option(None, "--tag"),
    status: str = typer.Option("published", "--status", help="published|draft|archived"),
    profile: str | None = typer.Option(None, "--profile"),
    gate: str | None = typer.Option(None, "--gate"),
    phase: str | None = typer.Option(None, "--phase"),
    search: str | None = typer.Option(None, "--search"),
) -> None:
    """列出/检索技能。"""
    _banner("skill list")
    from .skills.models import SkillCategory, SkillStatus

    service = _skill_service()
    try:
        cat = SkillCategory(category) if category else None
        st = SkillStatus(status) if status else None
    except ValueError:
        console.print("[red]非法 category/status[/red]")
        raise typer.Exit(2)
    rows = service.search(
        search, category=cat, tags=[tag] if tag else None, status=st,
        profile=profile, gate_slug=gate, phase_slug=phase,
    )
    if not rows:
        console.print("[yellow]无匹配技能[/yellow]")
        return
    table = Table(title=f"Skills · {len(rows)}")
    for col in ("id", "title", "category", "status", "tags", "updated"):
        table.add_column(col)
    for r in rows:
        table.add_row(r.id, r.title, r.category.value, r.status.value,
                      ",".join(r.tags), r.updated_at.strftime("%Y-%m-%d"))
    console.print(table)


@skill_app.command("show")
def skill_show(skill_id: str = typer.Argument(...)) -> None:
    """显示技能正文与元数据。"""
    from .skills.models import SkillStatus
    try:
        rec = _skill_service().get(skill_id)
    except KeyError:
        console.print(f"[red]技能不存在:[/red] {skill_id}")
        raise typer.Exit(2)
    console.print(f"\n[bold cyan]{rec.title}[/bold cyan] · {rec.category.value} · {rec.status.value} · v{rec.version}")
    console.print(f"tags={rec.tags} · phase={rec.phase_slug} · gate={rec.gate_slug} · "
                  f"applies_to={rec.applies_to} · source={rec.source.value}")
    console.print(f"源自: {rec.source_engagement or '—'} · 创建: {rec.created_at:%Y-%m-%d} · 更新: {rec.updated_at:%Y-%m-%d}")
    console.print("\n" + rec.body_md)


@skill_app.command("edit")
def skill_edit(
    skill_id: str = typer.Argument(...),
    title: str | None = typer.Option(None, "--title"),
    tags: str | None = typer.Option(None, "--tags"),
    body: str | None = typer.Option(None, "--body"),
) -> None:
    """编辑技能（version+1）。"""
    from .skills.models import SkillPatch
    try:
        rec = _skill_service().update(skill_id, SkillPatch(
            title=title, tags=[t.strip() for t in tags.split(",") if t.strip()] if tags else None,
            body_md=body,
        ))
    except KeyError:
        console.print(f"[red]技能不存在:[/red] {skill_id}")
        raise typer.Exit(2)
    console.print(f"✅ 已更新 [cyan]{rec.id}[/cyan] → v{rec.version}")


@skill_app.command("publish")
def skill_publish(skill_id: str = typer.Argument(...)) -> None:
    """发布草稿（可检索、可导出）。"""
    try:
        _skill_service().publish(skill_id)
    except KeyError:
        console.print(f"[red]技能不存在:[/red] {skill_id}")
        raise typer.Exit(2)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2)
    console.print(f"✅ 已发布 [cyan]{skill_id}[/cyan]")


@skill_app.command("archive")
def skill_archive(skill_id: str = typer.Argument(...)) -> None:
    """归档技能。"""
    try:
        _skill_service().archive(skill_id)
    except (KeyError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2)
    console.print(f"✅ 已归档 [cyan]{skill_id}[/cyan]")


@skill_app.command("review")
def skill_review(limit: int = typer.Option(20, "--limit")) -> None:
    """草稿审阅队列（自动捕获/gate 提示产生的草稿）。"""
    _banner("skill review")
    rows = _skill_service().list_drafts()[:limit]
    if not rows:
        console.print("[yellow]没有待审草稿[/yellow]")
        return
    table = Table(title=f"Draft queue · {len(rows)}")
    for col in ("id", "title", "source", "engagement"):
        table.add_column(col)
    for r in rows:
        table.add_row(r.id, r.title, r.source.value, r.source_engagement or "—")
    console.print(table)


@skill_app.command("export")
def skill_export(
    skill_id: str = typer.Argument(...),
    fmt: str = typer.Option(..., "--format", help="agentscope|qwenpaw"),
    out: str = typer.Option("exports", "--out", help="输出目录"),
) -> None:
    """导出技能为 AgentScope / QwenPaw 格式。"""
    from .skills.exporters import export_skill
    try:
        rec = _skill_service().get(skill_id)
        files = export_skill(rec, fmt)
    except KeyError:
        console.print(f"[red]技能不存在:[/red] {skill_id}")
        raise typer.Exit(2)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2)
    out_dir = Path(out)
    for f in files:
        p = out_dir / f.name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f.content, encoding="utf-8")
    console.print(f"✅ 导出 {len(files)} 个文件 → [green]{out_dir}[/green] ({fmt})")
```

- [x] **Step 4: 运行确认通过**：`pytest tests/test_cli.py -k skill -v` → PASS（16 个全量）
- [x] **Step 5: 全量回归**：`pytest` → 292 passed, 3 skipped（现有 CLI 测试未破坏）
- [ ] **Step 6: Commit**：`git add fde_scope/cli.py tests/test_cli.py && git commit -m "feat(cli): add skill command group"`

---

### Task 7: Web API 路由

**Files:**
- Modify: `fde_scope/web/app.py`（新增 8 个路由 + 单页中技能区段）
- Test: `tests/test_web.py`（追加）

**Interfaces:**
- Consumes: `SkillService`/`SkillStore`（Task 2-4）、`export_skill`（Task 5）
- Produces: 路由见 spec §2.6（`GET /api/skills`、`POST /api/skills`、`GET/PATCH /api/skills/{sid}`、`POST /api/skills/{sid}/publish|archive|export`、`GET /api/skills/drafts`）；SkillStore 根使用与现有 Web 相同的 `.fde_scope` 基础（`Path(".fde_scope/skills")`）

- [x] **Step 1: 写失败测试**（`tests/test_web.py` 追加）

```python
def test_skills_api_roundtrip(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = client.post("/api/skills", json={
        "title": "OPC UA 排查", "category": "implementation", "tags": ["opcua"],
        "body_md": "# 步骤", "phase_slug": "deploy",
    })
    assert r.status_code == 200
    sid = r.json()["id"]
    assert r.json()["status"] == "draft"
    assert client.post(f"/api/skills/{sid}/publish").status_code == 200
    got = client.get(f"/api/skills/{sid}")
    assert got.status_code == 200 and got.json()["status"] == "published"
    lst = client.get("/api/skills?category=implementation")
    assert lst.status_code == 200 and len(lst.json()) == 1
    drafts = client.get("/api/skills/drafts")
    assert drafts.status_code == 200 and len(drafts.json()) == 0  # 已发布
    exp = client.post(f"/api/skills/{sid}/export", json={"format": "agentscope"})
    assert exp.status_code == 200
    assert exp.json()["files"][0]["name"].endswith("SKILL.md")
    arch = client.post(f"/api/skills/{sid}/archive")
    assert arch.status_code == 200 and arch.json()["status"] == "archived"
```

（注意：现有 `tests/test_web.py` 的 client fixture 与 app 模块导入方式以现有文件为准，先读该文件确认 fixture 名称。）

- [x] **Step 2: 读现有 `tests/test_web.py` 确认 client fixture 用法**（fixture 已自动 `monkeypatch.chdir(tmp_path)`），运行确认失败：`pytest tests/test_web.py -k skills -v` → FAIL（404）
- [x] **Step 3: 实现路由**（`web/app.py` 追加；**修正两处**：① `_skill_service()` 用相对路径 `Path(".fde_scope/skills")`（与 `_ENGAGEMENTS_DIR` 同约定，绝对路径会破坏测试 chdir 隔离）；② `SkillDraft`/`SkillPatch` 需模块级导入（FastAPI 注册路由时即解析请求体类型注解，函数内 import 不生效）；export 的 `body.get("format")` 缺失时交 ValueError → 400）

```python
# -- skills API --------------------------------------------------------------
def _skill_service():
    from ..skills.service import SkillService
    from ..skills.store import SkillStore

    return SkillService(SkillStore(Path(__file__).resolve().parents[2] / ".fde_scope" / "skills"))


@app.get("/api/skills")
def api_skills(q: str | None = None, category: str | None = None, tag: str | None = None,
               status: str = "published", profile: str | None = None,
               gate: str | None = None, phase: str | None = None) -> list[dict]:
    from ..skills.models import SkillCategory, SkillStatus
    return [r.model_dump() for r in _skill_service().search(
        q, category=SkillCategory(category) if category else None,
        tags=[tag] if tag else None,
        status=SkillStatus(status) if status else None,
        profile=profile, gate_slug=gate, phase_slug=phase,
    )]


@app.post("/api/skills")
def api_skills_create(draft: SkillDraft) -> dict:
    return _skill_service().create(draft).model_dump()


@app.get("/api/skills/drafts")
def api_skills_drafts() -> list[dict]:
    return [r.model_dump() for r in _skill_service().list_drafts()]


@app.get("/api/skills/{sid}")
def api_skill_get(sid: str) -> dict:
    try:
        return _skill_service().get(sid).model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail="skill not found")


@app.patch("/api/skills/{sid}")
def api_skill_patch(sid: str, patch: SkillPatch) -> dict:
    try:
        return _skill_service().update(sid, patch).model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail="skill not found")


@app.post("/api/skills/{sid}/publish")
def api_skill_publish(sid: str) -> dict:
    try:
        return _skill_service().publish(sid).model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail="skill not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/skills/{sid}/archive")
def api_skill_archive(sid: str) -> dict:
    try:
        return _skill_service().archive(sid).model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail="skill not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/skills/{sid}/export")
def api_skill_export(sid: str, body: dict) -> dict:
    from ..skills.exporters import export_skill
    try:
        rec = _skill_service().get(sid)
        files = export_skill(rec, body["format"])
    except KeyError:
        raise HTTPException(status_code=404, detail="skill not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"skill_id": sid, "format": body["format"],
            "files": [{"name": f.name, "content": f.content} for f in files]}
```

- [x] **Step 4: 运行确认通过**：`pytest tests/test_web.py -k skills -v` → PASS；全量 `pytest` → 293 passed, 3 skipped
- [x] **Step 5: Commit**：`git add fde_scope/web/app.py tests/test_web.py && git commit -m "feat(web): add skills API"`

---

### Task 8: engagement 钩子（CLI 层接入）

**Files:**
- Modify: `fde_scope/cli.py`（`engage advance` 阻塞处、`gate check` 失败处、`engage advance` 成功处接入钩子）
- Test: `tests/test_cli.py`（追加）

**Interfaces:**
- Consumes: `_maybe_suggest_skill` / `_maybe_capture`（Task 6 已定义）
- Produces: 行为——`engage advance` 被阻塞时：打印提示 + 生成 gate 提示草稿；`gate check` 失败时：同上；`engage advance` 成功时：`_maybe_capture(action="advance", ...)`；`gate check` 通过时：`_maybe_capture(action="gate_pass", ...)`

- [x] **Step 1: 写失败测试**（`tests/test_cli.py` 追加；**修正计划缺陷**：内存构造的 eng 必须落盘（`_save_engagement`）CLI 才能加载——`_load_engagement` 从 `.fde_scope/engagements/<id>.json` 读文件；另补 `test_gate_check_failure_suggests_skill` 与 `test_advance_success_captures_operation`，共 3 个）

```python
def test_advance_blocked_suggests_skill(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # 用 manufacturing profile 创建 engagement，在需要 site_survey 的 phase 强制推进
    from fde_scope.engagement.context import EngagementContext
    from fde_scope.engagement.engagement import Engagement
    from fde_scope.engagement.phases import PhaseRegistry

    ctx = EngagementContext(id="eng-t", customer="Acme", profile="manufacturing")
    ctx.current_phase = "site_survey"  # 该阶段 gate 需要站点信息，空 ctx 必然阻塞
    eng = Engagement(ctx)
    eng.save_to = lambda: None  # 不需要
    runner.invoke(app, ["engage", "advance", "eng-t"])  # 阻塞 → 触发提示
    from fde_scope.skills.store import SkillStore
    drafts = SkillStore(tmp_path / ".fde_scope" / "skills").load_all()
    assert any(r.source.value == "gate_hint" for r in drafts)
```

（注意：先读 `tests/test_cli.py` 现有 engagement 相关测试，复用其构造方式，避免依赖不存在的 save_to 属性；以 `EngagementContext` 实际 API 为准。）

- [x] **Step 2: 运行确认失败**：`pytest tests/test_cli.py -k suggest -v` → FAIL（3 个，草稿未生成）
- [x] **Step 3: 接入钩子**（`cli.py` 中 `engage_advance` 与 `gate_check` 修改；已确认 `GateResult.blockers` 字段与 `AdvanceBlocked.result` 存在）

```python
# engage_advance 中：
    try:
        nxt = eng.advance(force=force)
    except AdvanceBlocked as exc:
        console.print(f"[red]❌ ADVANCE BLOCKED[/red] — phase={eng.ctx.current_phase}")
        console.print(exc.result.summary())
        _save_engagement(eng)
        _maybe_suggest_skill(engagement_id, eng.ctx.current_phase,
                             [b for b in exc.result.blockers])
        raise typer.Exit(1) from exc
    ...
    _save_engagement(eng)
    _maybe_capture("advance", engagement_id, phase_slug=eng.ctx.current_phase)
    console.print(f"✅ Advanced → ...")

# gate_check 中：
    result = eng.evaluate_gate(slug)
    _save_engagement(eng)
    console.print(result.summary())
    if not result.passed:
        _maybe_suggest_skill(engagement_id, slug, [b for b in result.blockers])
        raise typer.Exit(1)
    _maybe_capture("gate_pass", engagement_id, phase_slug=eng.ctx.current_phase)
```

（`GateResult.blockers` 字段名以 `engagement/gates/base.py` 实际定义为准，先读该文件确认。）

- [x] **Step 4: 运行确认通过**：`pytest tests/test_cli.py -k suggest -v` → PASS（3 个）
- [x] **Step 5: 全量回归**：`pytest` → 296 passed, 3 skipped
- [x] **Step 6: Commit**：`git add fde_scope/cli.py tests/test_cli.py && git commit -m "feat(cli): wire skill hooks into engage/gate flow"`

---

### 收尾（每步完成即做）

- [x] **Step: ruff + mypy 全量检查**：`ruff check` 22 个错误清零（F821 注解 → TYPE_CHECKING；SIM105 → contextlib.suppress；B904 ×17 → `from None`）+ `ruff format` 8 文件重排 + `mypy` 2 错误清零（web export fmt 类型收窄）→ 全部通过
- [x] **Step: 更新 README**（CLI reference 增补 `skill` 组；新增"💡 Skill 沉淀"小节，含三种入口/生命周期/导出示例；测试计数 296）
- [x] **Step: 最终 commit**：`git add -A && git commit -m "docs: document skills subsystem"`（06447ed）
