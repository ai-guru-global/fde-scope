"""ACP (Agent Client Protocol) adaptation placeholder.

QwenPaw 官方 ACP 形态（2026-08-25 检索，见 docs/qwenpaw_integration.md）：
两种模式——QwenPaw 作为 client/orchestrator（内置 ``delegate_external_agent``
tool 连接外部 ACP runner）与 QwenPaw 作为 ACP server。外部 runner 配置字段
（QwenPaw ``ACPAgentConfig``）：``enabled`` / ``command`` / ``args`` / ``env`` /
``trusted`` / ``tool_parse_mode`` / ``stdio_buffer_limit_bytes``，经 stdio
子进程协议通信。

本期（spec §5.2）只提供占位基类：FDE SOP 引擎作为 ACP runner 时实现
:class:`AcpEndpoint`，``runner_config()`` 的输出可直接填入 QwenPaw 的
Workspace → ACP 配置。网络协议实现不在本期。
"""

from __future__ import annotations

import abc
from typing import Any


class AcpEndpoint(abc.ABC):
    """Base class for exposing an FDE capability as a QwenPaw ACP runner.

    Subclasses declare the runner metadata; ``runner_config()`` emits the
    exact ``ACPAgentConfig`` fields QwenPaw expects.
    """

    name: str = ""
    description: str = ""
    acp_command: list[str] = []
    acp_env: dict[str, str] = {}

    @abc.abstractmethod
    async def handle(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle one ACP task payload. Not implemented in this phase."""
        raise NotImplementedError

    def runner_config(self) -> dict[str, Any]:
        """QwenPaw ACP runner config (Workspace → ACP page fields)."""
        command, *args = self.acp_command
        return {
            "enabled": True,
            "command": command,
            "args": args,
            "env": self.acp_env,
            "trusted": True,
            "tool_parse_mode": "call_title",
        }
