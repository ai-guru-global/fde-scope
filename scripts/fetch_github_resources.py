#!/usr/bin/env python3
"""抓取 FDE 相关 GitHub 资源，落到包内 manifest 与逐字镜像。

    make fetch-resources              # 触网：枚举 → 增量镜像已审核条目 → 写盘
    make fetch-resources OFFLINE=1    # 离线：不触网，仅重排 manifest / snapshot（CI 无密钥）

胖逻辑在 :mod:`fde_scope.resources.harvest`（放包内以便单测覆盖，脚本本身不进
coverage source）。GitHub token 由 ``gh`` 从 keyring 自读，本脚本不经手、不记录。
"""

from __future__ import annotations

import typer

from fde_scope.resources import harvest


def main(
    offline: bool = typer.Option(False, "--offline", help="不触网，只重排已有 manifest / snapshot。"),
    max_pages: int = typer.Option(harvest.DEFAULT_MAX_PAGES, "--max-pages", help="每条查询最多采几页。"),
) -> None:
    try:
        snapshot = harvest.run_harvest(offline=offline, max_pages=max_pages)
    except harvest.HarvestError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc
    typer.secho(
        f"harvest done: {snapshot.unique_repos} unique repos, {len(snapshot.queries)} queries",
        fg=typer.colors.GREEN,
    )


if __name__ == "__main__":
    typer.run(main)
