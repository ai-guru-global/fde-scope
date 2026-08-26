"""QwenPaw 导出产物校验器（spec §5.2）。

校验规则对齐官方形态（2026-08-25 检索）：config.json 的 agents.profiles
必填 id/name/enabled 且键 == id；每 profile 有 workspaces/{id}/agent.json
（必填 id/name，system_prompt_files 指向存在的 persona 文件）；agent id
匹配官方规则；skills/ 下 SKILL.md 含 frontmatter（name/description）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_AGENT_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*[a-zA-Z0-9]$|^[a-zA-Z0-9]$")


def validate_export(out_dir: Path) -> dict:
    """结构 + 必填字段 + agent id 规则校验；返回 {"valid", "errors"}。

    被校验目录可能不可信：非法 id / persona 路径一律短路，绝不拼接探测
    ``out_dir`` 之外的文件。
    """
    errors: list[str] = []
    out = Path(out_dir)

    cfg_path = out / "config.json"
    if not cfg_path.exists():
        return {"valid": False, "errors": ["config.json missing"]}
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return {"valid": False, "errors": [f"config.json invalid JSON: {exc}"]}
    if not isinstance(cfg, dict):
        return {"valid": False, "errors": ["config.json root is not an object"]}
    agents = cfg.get("agents")
    if not isinstance(agents, dict):
        return {"valid": False, "errors": ["agents section missing or not an object"]}
    profiles = agents.get("profiles")
    if not isinstance(profiles, dict):
        return {"valid": False, "errors": ["agents.profiles missing or not an object"]}
    if not profiles:
        errors.append("agents.profiles empty")
    active = agents.get("active_agent")
    if active is not None and profiles and active not in profiles:
        errors.append(f"active_agent {active!r} not in profiles")
    for key, p in profiles.items():
        if not isinstance(p, dict):
            errors.append(f"profile {key!r} is not an object")
            continue
        for required in ("id", "name", "enabled"):
            if required not in p:
                errors.append(f"profile {key!r} missing field {required!r}")
        if p.get("id") != key:
            errors.append(f"profile key {key!r} != id {p.get('id')!r}")
        aid = str(p.get("id", ""))
        if not _AGENT_ID_RE.fullmatch(aid):
            errors.append(f"agent id {aid!r} violates QwenPaw id rules")
            continue  # 非法 id 不得拼出 workspaces/ 外路径
        ws = out / "workspaces" / aid / "agent.json"
        if not ws.exists():
            errors.append(f"workspaces/{aid}/agent.json missing")
            continue
        try:
            aj = json.loads(ws.read_text(encoding="utf-8"))
        except ValueError as exc:
            errors.append(f"workspaces/{aid}/agent.json invalid JSON: {exc}")
            continue
        if not isinstance(aj, dict):
            errors.append(f"agent.json {aid!r} is not an object")
            continue
        for required in ("id", "name"):
            if required not in aj:
                errors.append(f"agent.json {aid!r} missing field {required!r}")
        for persona in aj.get("system_prompt_files") or []:
            pp = Path(str(persona))
            if pp.is_absolute() or ".." in pp.parts:
                errors.append(f"persona {persona!r} is not a relative file for agent {aid!r}")
                continue
            if not (out / "workspaces" / aid / persona).exists():
                errors.append(f"persona {persona!r} missing for agent {aid!r}")

    skills_dir = out / "skills"
    if skills_dir.exists():
        for skill_md in skills_dir.glob("*/SKILL.md"):
            text = skill_md.read_text(encoding="utf-8")
            if not text.startswith("---\n") or "name:" not in text or "description:" not in text:
                errors.append(f"skill {skill_md.parent.name!r} SKILL.md lacks frontmatter")

    return {"valid": not errors, "errors": errors}
