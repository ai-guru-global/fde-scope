"""QwenPaw 导出目录结构校验器（spec §5.2）。

Task 2 先提供最小版（恒通过），Task 3 增强为正式实现：
结构存在性 + profiles 必填字段 + agent id 规则 + persona 引用。
"""

from __future__ import annotations

from pathlib import Path


def validate_export(out_dir: Path) -> dict:
    """校验导出目录，返回 ``{"valid": bool, "errors": list[str]}``。"""
    return {"valid": True, "errors": []}
