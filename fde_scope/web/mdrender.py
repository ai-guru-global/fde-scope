"""Shared Markdown plumbing for the reading pages (course / docs reader).

Extracted from ``course.py`` so the docs reader stops importing the course
module's private helpers (plan §7 item 4). Both pages render with
``html: False`` (raw HTML is escaped), demote headings one level, and rewrite
links **outside code fences** — the corpora's fenced template examples are
full of markdown links that must pass through untouched.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML

MD_IMAGE = re.compile(r"!\[([^\]\n]*)\]\(([^)\s]+)\)")
MD_LINK = re.compile(r"(?<!!)\[([^\]\n]*)\]\(([^)\s]+)\)")
AUTOLINK = re.compile(r"<(https?://[^>]+)>")
_FENCE_OPEN = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_FENCE_CLOSE = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*$")


class DemotingRenderer(RendererHTML):
    """Demote every heading one level (``#`` lessons render as ``h2`` etc.).

    Both ``heading_open`` and ``heading_close`` need it: the rule only rewrites
    ``token.tag``, and markdown-it sets the same tag name on the close token.
    A subclass, not ``renderer.rules[...] = fn`` — ``RendererHTML`` builds
    ``rules`` from the instance's own bound methods.
    """

    def heading_open(self, tokens, idx, options, env) -> str:  # noqa: ANN001
        return self._demoted(tokens, idx, options, env)

    def heading_close(self, tokens, idx, options, env) -> str:  # noqa: ANN001
        return self._demoted(tokens, idx, options, env)

    def _demoted(self, tokens, idx, options, env) -> str:  # noqa: ANN001
        tokens[idx].tag = f"h{min(int(tokens[idx].tag[1:]) + 1, 6)}"
        return self.renderToken(tokens, idx, options, env)


def demoting_markdown(renderer_cls: type[RendererHTML] | None = None) -> MarkdownIt:
    """A CommonMark parser with the shared config: raw HTML escaped, tables and
    strikethrough enabled, headings demoted via ``renderer_cls``."""
    return MarkdownIt(
        "commonmark",
        {"html": False},
        renderer_cls=renderer_cls or DemotingRenderer,
    ).enable(["table", "strikethrough"])


def fenced_indices(lines: list[str]) -> set[int]:
    """Indices of lines inside a code fence, the fence markers included.

    Reduced CommonMark rule: a fence opens on ``` / ~~~ (≤3 spaces indent)
    and closes on a bare run of the same character at least as long — one
    kind cannot close the other and an opener's info string is ignored.
    """
    fenced: set[int] = set()
    ch, n = "", 0
    for i, line in enumerate(lines):
        if ch:
            m = _FENCE_CLOSE.match(line)
            if m and m.group(1)[0] == ch and len(m.group(1)) >= n:
                ch = ""
            fenced.add(i)
        elif m := _FENCE_OPEN.match(line):
            fenced.add(i)
            ch, n = m.group(1)[0], len(m.group(1))
    return fenced


def rewrite_outside_fences(md_text: str, rewrite: Callable[[str], str]) -> str:
    """Apply ``rewrite`` to the runs of lines between code fences.

    Fence lines are kept byte-identical and global line numbers survive, so
    callers can keep line-indexed side tables (heading anchors) intact.
    """
    lines = md_text.split("\n")
    fenced = fenced_indices(lines)
    out: list[str] = []
    chunk: list[str] = []

    def flush() -> None:
        if chunk:
            out.append(rewrite("\n".join(chunk)))
            chunk.clear()

    for i, line in enumerate(lines):
        if i in fenced:
            flush()
            out.append(line)
        else:
            chunk.append(line)
    flush()
    return "\n".join(out)


def normalize_path(base: str, path: str) -> str:
    """Resolve ``path`` against the source document's repo-relative directory."""
    parts = [seg for seg in base.split("/") if seg]
    for seg in path.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
        else:
            parts.append(seg)
    return "/".join(parts)
