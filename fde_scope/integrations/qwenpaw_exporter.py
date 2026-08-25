"""QwenPaw 导出器：FDE 产物 → QwenPaw 可消费形态（spec §5.2）。

字段对齐官方（2026-08-25 检索）：
- ``config.json`` 的 ``agents.profiles[agent_id]``：id/name/description/enabled
  （必填 id+name+enabled；description 用于多 Agent 协作）；
- workspace 内 ``agent.json``：id/name/description/language/system_prompt_files；
- persona 即 workspace 内 AGENTS.md（system_prompt_files 引用）；
- 技能 = workspace ``skills/`` 目录（SKILL.md，与 AgentScope 同源）。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fde_scope.config import AgentSpec, TenantConfig
from fde_scope.corpus.types import CorpusReport
from fde_scope.skills.models import SkillRecord


def _agent_id(name: str) -> str:
    """归一化为 QwenPaw 合法 agent id（^[a-zA-Z0-9][a-zA-Z0-9_-]*[a-zA-Z0-9]$）。"""
    s = re.sub(r"[^a-zA-Z0-9_-]", "-", name).strip("-")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*[a-zA-Z0-9]|[a-zA-Z0-9]", s):
        raise ValueError(f"agent name {name!r} cannot form a valid agent id")
    return s


@dataclass
class ExportBundle:
    """一次导出的产物句柄。"""

    out_dir: Path
    written: list[str] = field(default_factory=list)
    report: dict = field(default_factory=dict)


class QwenPawExporter:
    """把 tenant 拓扑 / 技能 / corpus 导出为 QwenPaw 兼容目录树。"""

    def export(
        self,
        tenant: TenantConfig,
        out_dir: Path,
        skills: list[SkillRecord] | None = None,
        corpus_report: CorpusReport | None = None,
    ) -> ExportBundle:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        specs = tenant.agents or [AgentSpec(name=f"{tenant.name}_agent", role=tenant.name)]
        ids = [_agent_id(s.name) for s in specs]
        bundle = ExportBundle(out_dir=out)

        # config.json — 全局多 Agent 拓扑（官方 agents.profiles 结构）
        cfg = {
            "agents": {
                "active_agent": ids[0],
                "profiles": {
                    aid: {
                        "id": aid,
                        "name": s.name,
                        "description": s.role,
                        "enabled": True,
                    }
                    for aid, s in zip(ids, specs)
                },
            }
        }
        self._write(out / "config.json", cfg, bundle)

        # workspaces/{agent_id}/ — 每 agent 配置 + persona
        for aid, s in zip(ids, specs):
            ws = out / "workspaces" / aid
            self._write(
                ws / "agent.json",
                {
                    "id": aid,
                    "name": s.name,
                    "description": s.role,
                    "language": "en",
                    "system_prompt_files": ["AGENTS.md"],
                },
                bundle,
            )
            prompt = s.system_prompt or (
                f"You are the {s.role} for {tenant.name} (tenant={tenant.id}). "
                "Answer customer tickets using only the tenant corpus. "
                "Never access other tenants' data."
            )
            (ws / "AGENTS.md").write_text(f"# {s.name}\n\n{prompt}\n", encoding="utf-8")
            bundle.written.append(f"workspaces/{aid}/AGENTS.md")

        # skills/ — published 技能包（qwenpaw 格式）
        if skills:
            from fde_scope.skills.exporters import export_many

            for f in export_many(skills, "qwenpaw"):
                p = out / "skills" / f.name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(f.content, encoding="utf-8")
                bundle.written.append(f"skills/{f.name}")

        # corpus.json — collection 说明
        if corpus_report is not None:
            self._write(
                out / "corpus.json",
                {
                    "collection": f"corpus_{tenant.id}",
                    "total": corpus_report.total,
                    "real": corpus_report.real,
                    "synthetic": corpus_report.synthetic,
                },
                bundle,
            )

        # 校验报告（Task 3 起复用正式校验器）
        from .validator import validate_export

        bundle.report = validate_export(out)
        self._write(out / "qwenpaw_validate.json", bundle.report, bundle)
        return bundle

    @staticmethod
    def _write(path: Path, data: dict[str, Any], bundle: ExportBundle) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        bundle.written.append(str(path.relative_to(bundle.out_dir)))
