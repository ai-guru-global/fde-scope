"""Tests for the QwenPaw integration surface (spec §5.2 ACP placeholder)."""

from __future__ import annotations

import pytest

from fde_scope.integrations.acp import AcpEndpoint


def test_acp_endpoint_is_abstract() -> None:
    with pytest.raises(TypeError):
        AcpEndpoint()  # type: ignore[abstract]


def test_acp_endpoint_runner_config_matches_qwenpaw_fields() -> None:
    class SopEngine(AcpEndpoint):
        name = "fde_sop"
        description = "FDE SOP state machine"
        acp_command = ["python", "-m", "fde_scope.acp_server"]
        acp_env = {"FDE_SCOPE_TENANT": "acme"}

        async def handle(self, payload: dict) -> dict:
            return {"ok": True}

    ep = SopEngine()
    cfg = ep.runner_config()
    # 字段名对齐 QwenPaw ACPConfig.ACPAgentConfig（官方源码 config.py）
    assert cfg["enabled"] is True
    assert cfg["command"] == "python"
    assert cfg["args"] == ["-m", "fde_scope.acp_server"]
    assert cfg["env"] == {"FDE_SCOPE_TENANT": "acme"}
    assert cfg["trusted"] is True
    assert cfg["tool_parse_mode"] == "call_title"
