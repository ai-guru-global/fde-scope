"""本体语义层（TBox/ABox + SHACL-lite 校验 + JSON-LD 导出）。

零新依赖：pydantic + pyyaml + 标准库；不导入 agentscope（零配置可跑）。
"""

from .validation import (
    ValidationIssue,
    ValidationReport,
    resolve_imports,
    validate_schema,
)

__all__ = [
    "ValidationIssue",
    "ValidationReport",
    "resolve_imports",
    "validate_schema",
]
