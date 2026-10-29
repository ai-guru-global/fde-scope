"""GitHub 资源建档的数据模型与许可判定（pydantic v2，extra=forbid）。

两个正交轴，永不合并（AGENTS.md「measured, not aspirational」的溯源纪律）：

* :data:`LICENSE_NONE` / :data:`LICENSE_NOASSERTION` 是两个**不同**的哨兵值
  —— GitHub 对「什么都没声明」返回 null（归 NOASSERTION），对「明确无许可」
  才返回 NONE；把两者折叠会伪造上游意图。
* ``relevance`` 决定是否值得看，``license_spdx`` 决定能否逐字再分发。
  镜像门槛 = ``is_permissive(license) AND relevance != "noise"``，两者缺一
  都不落正文。

本模块只做纯数据与判定，不碰磁盘 / 网络（写盘归 harvest、读取归 repo）。
"""

from __future__ import annotations

import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# license 轴
# ---------------------------------------------------------------------------
#: 上游明确声明「无任何许可 / all rights reserved」。绝不镜像正文。
LICENSE_NONE = "NONE"
#: GitHub 无法识别（返回 null、自定义文件、或非标准声明）。绝不镜像正文。
LICENSE_NOASSERTION = "NOASSERTION"

#: 视为「宽松、可逐字再分发」的 SPDX（大小写不敏感，CC-BY* 含 ShareAlike，
#: 但**排除** CC-BY-*-NC / ND —— NonCommercial 与 NoDerivatives 与
#: 「沉淀进我们的 MIT 仓库再分发」不兼容）。
_PERMISSIVE_EXACT = frozenset(
    {
        "mit",
        "mit-0",
        "apache-2.0",
        "bsd-1-clause",
        "bsd-2-clause",
        "bsd-3-clause",
        "bsd-4-clause",
        "0bsd",
        "isc",
        "unlicense",
        "cc0-1.0",
        "cc0",
        "zlib",
        "python-2.0",
        "curl",
        "wtfpl",
        "postgresql",
        "ofl-1.1",
    }
)

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_REPO_RE = re.compile(r"^[^/\s]+/[^/\s]+$")

Relevance = Literal["core", "adjacent", "noise"]


def normalize_license(raw: str | None) -> str:
    """把 GitHub 的 license 字段归一到 SPDX 令牌。

    ``None`` / 空串 → :data:`LICENSE_NOASSERTION`（GitHub 认不出或未提供，
    绝不臆测成 NONE）。其余保留上游 SPDX id（含大小写差异交给判定层）。
    """
    if raw is None:
        return LICENSE_NOASSERTION
    token = raw.strip()
    if not token:
        return LICENSE_NOASSERTION
    return token


def is_permissive(license_spdx: str | None) -> bool:
    """该 SPDX 是否允许把正文逐字镜像进本仓库。"""
    if not license_spdx:
        return False
    key = license_spdx.strip().lower()
    if key in {LICENSE_NONE.lower(), LICENSE_NOASSERTION.lower()}:
        return False
    if key in _PERMISSIVE_EXACT:
        return True
    # CC-BY / CC-BY-SA（任意版本）可再分发；含 NC/ND 者不可。
    if key.startswith("cc-by"):
        return "-nc" not in key and "-nd" not in key
    return False


def mirror_gate(license_spdx: str, relevance: Relevance) -> bool:
    """该条目是否**被允许**镜像正文（不关心实际上有没有镜像）。"""
    return is_permissive(license_spdx) and relevance != "noise"


# ---------------------------------------------------------------------------
# 文件级镜像记录
# ---------------------------------------------------------------------------
class MirrorFile(BaseModel):
    """一个已落到 ``docs/github-resources/mirror`` 的逐字镜像文件。"""

    model_config = ConfigDict(extra="forbid")

    path: str  # 上游仓库内路径，例如 README.md
    local_name: str  # 本地镜像文件名（含 slug 前缀，扁平存放）
    blob_sha: str
    retrieved_at: str
    truncated: bool = False


# ---------------------------------------------------------------------------
# 仓库级记录
# ---------------------------------------------------------------------------
class ResourceRecord(BaseModel):
    """一个 GitHub 仓库的建档条目：元数据 + 许可判定 + 镜像状态。"""

    model_config = ConfigDict(extra="forbid")

    slug: str
    repo: str  # owner/name
    url: str
    license_spdx: str
    license_decision_applied: str
    relevance: Relevance
    categories: list[str] = Field(min_length=1)

    stars: int
    upstream_updated_at: str
    default_branch: str
    is_fork: bool
    archived: bool
    snapshot_at: str

    mirror: bool = False
    files: list[MirrorFile] = Field(default_factory=list)
    #: 当「许可宽松 + 非 noise 却没有镜像正文」时，必须写清原因；
    #: 当因许可被拒绝镜像时，写拒绝理由（溯源诚实度）。
    mirror_reason: str | None = None

    #: 上游一句话原文（不可信外部输入；渲染进页面前必须 html.escape）。
    upstream_description: str | None = None
    #: 我们自己撰写的双语摘要（永远可再分发）。core/adjacent 必填。
    summary_zh: str | None = None
    summary_en: str | None = None

    # -- 归一化 -------------------------------------------------------------
    @field_validator("slug")
    @classmethod
    def _slug_kebab(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(f"slug must be kebab-case [a-z0-9-], got {v!r}")
        return v

    @field_validator("repo")
    @classmethod
    def _repo_shape(cls, v: str) -> str:
        v = v.strip()
        if not _REPO_RE.match(v):
            raise ValueError(f"repo must be 'owner/name', got {v!r}")
        return v

    @field_validator("license_spdx")
    @classmethod
    def _license_present(cls, v: str) -> str:
        token = normalize_license(v)
        # NONE 与 NOASSERTION 是两个不同令牌，此处不折叠、不转成 null。
        return token

    # -- owner / name / mirror 目录（去歧义）--------------------------------
    @property
    def owner(self) -> str:
        return self.repo.split("/", 1)[0]

    @property
    def name(self) -> str:
        return self.repo.split("/", 1)[1]

    @property
    def mirror_dir(self) -> str:
        """``docs/github-resources/mirror`` 下的目录名 ``owner__name``。"""
        return f"{self.owner}__{self.name}"

    # -- 跨字段不变量 -------------------------------------------------------
    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        # 1. mirror_dir 唯一性前提：owner / name 内含 '__' 会让目录名歧义。
        if "__" in self.owner or "__" in self.name:
            raise ValueError(f"owner/name must not contain '__' (mirror dir ambiguity): {self.repo!r}")

        # 2. NONE / NOASSERTION 绝不镜像正文（不变量 1 的机器化）。
        if self.mirror and not is_permissive(self.license_spdx):
            raise ValueError(
                f"{self.slug}: mirror=true but license {self.license_spdx!r} is not redistributable"
            )

        # 3. 镜像门槛之外的条目必须 mirror=false。
        if self.mirror and self.relevance == "noise":
            raise ValueError(f"{self.slug}: noise entries are never mirrored")

        # 4. mirror=true ⇒ 至少一个文件条目。
        if self.mirror and not self.files:
            raise ValueError(f"{self.slug}: mirror=true requires files[] entries")

        # 5. 宽松 + 非 noise 却未镜像 ⇒ 必须给理由（否则是漏抓）。
        if not self.mirror and mirror_gate(self.license_spdx, self.relevance) and not self.mirror_reason:
            raise ValueError(f"{self.slug}: permissive+non-noise but not mirrored requires mirror_reason")

        # 6. core / adjacent 必须有双语摘要（我们自己写，可再分发）。
        if self.relevance in ("core", "adjacent") and not (self.summary_zh and self.summary_en):
            raise ValueError(f"{self.slug}: relevance={self.relevance} requires summary_zh and summary_en")

        return self


# ---------------------------------------------------------------------------
# snapshot（发现做实，不谎称全量）
# ---------------------------------------------------------------------------
class QuerySnapshot(BaseModel):
    """一条发现查询在采集时刻的字面量与 total_count 快照。"""

    model_config = ConfigDict(extra="forbid")

    query: str
    total_count: int = Field(ge=0)
    pages_fetched: int = Field(ge=1)
    snapshot_at: str


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = "github"
    queries: list[QuerySnapshot] = Field(default_factory=list)
    unique_repos: int = Field(default=0, ge=0)
    #: 诚实标注：union 是「本次采集」而非「全体」。
    note: str | None = None
