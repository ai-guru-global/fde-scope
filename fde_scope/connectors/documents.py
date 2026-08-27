"""Documents connector — turn a pile of on-site files into a corpus.

The "file-analysis" role agent needs a data source just like the data-analysis
(``csv``/``mysql``/``mes``) and log-analysis (``historian``/``mqtt``/``ros2``)
roles do. On site that source is usually a folder of PDFs, Word exports,
Excel worksheets and markdown runbooks. This connector wraps AgentScope 2.0's
``agentscope.rag`` parsers (``TextParser`` / ``PDFParser`` / ``WordParser`` /
``ExcelParser`` / ``PPTParser``) behind the same three-step contract the rest
of the kit uses, so the corpus engine consumes document text exactly like a
CSV row.

Zero-config promise holds: ``agentscope`` is imported *lazily inside the parse
step*, never at module import. Importing (and registering) this connector
succeeds with the extra absent; only actually parsing a file requires it — and
then we raise a clear, actionable error instead of a bare ImportError.

Field mapping (consumed by :class:`fde_scope.config.CorpusConfig`):
    id       -> ``{filename}#{section_index}``
    content  -> the section's text
    category -> the file extension (``pdf`` / ``docx`` / ...)
    source   -> the file path (carried through for provenance)
Non-text sections (e.g. image ``DataBlock``) are skipped — this connector feeds
a *text* corpus.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .base import Batch, DataConnector, register
from .schema import Schema, SchemaField

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime
    from agentscope.rag import ParserBase


def _run_coro(coro: Any) -> Any:
    """Run an ``async`` parser call from the synchronous connector surface.

    Normal paths (CLI, thread-pooled web handlers) have no running loop, so a
    plain ``asyncio.run`` works. If we are *already* inside a loop we cannot
    nest — offload to a one-shot worker thread that owns its own loop.
    """
    try:  # pragma: no cover - depends on ambient loop
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


@register
class DocumentsConnector(DataConnector):
    """Parse a file or directory of documents into text-corpus rows."""

    type = "documents"

    def __init__(self, source: str, **options: Any) -> None:
        super().__init__(source, **options)
        self._path = Path(source)
        self._recursive: bool = bool(options.get("recursive", True))
        self._max_bytes: int = int(options.get("max_file_bytes", 25 * 1024 * 1024))
        self._cache: list[dict[str, Any]] | None = None

    # -- lazy parser construction --------------------------------------------
    def _parsers(self) -> dict[str, ParserBase]:
        """Build an extension→parser map, importing AgentScope only on demand."""
        try:
            from agentscope.rag import ExcelParser, PDFParser, PPTParser, TextParser, WordParser
        except ImportError as exc:  # pragma: no cover - depends on extra
            raise RuntimeError(
                "the documents connector needs the AgentScope extra to parse files; "
                "install it with 'pip install \"fde-scope[agentscope]\"'"
            ) from exc
        mapping: dict[str, ParserBase] = {}
        for parser in (TextParser(), PDFParser(), WordParser(), ExcelParser(), PPTParser()):
            for ext in parser.supported_extensions():
                mapping.setdefault(ext.lower(), parser)
        return mapping

    # -- file discovery -------------------------------------------------------
    def _iter_files(self) -> Iterator[Path]:
        if self._path.is_file():
            yield self._path
        elif self._path.is_dir():
            globber = self._path.rglob("*") if self._recursive else self._path.glob("*")
            yield from sorted(p for p in globber if p.is_file())
        else:
            raise FileNotFoundError(f"documents source not found: {self.source}")

    # -- the three-step contract ---------------------------------------------
    def discover_schema(self) -> Schema:
        """Parse everything once (docs are small) and describe the resulting rows."""
        rows = self._all_rows()
        categories = sorted({str(r["category"]) for r in rows if r.get("category")})
        fields = [
            SchemaField(
                name="id", inferred_type="string", nullable=False, sample_values=[r["id"] for r in rows[:3]]
            ),
            SchemaField(name="content", inferred_type="string", nullable=False),
            SchemaField(name="source", inferred_type="string", nullable=False),
            SchemaField(
                name="category", inferred_type="string", nullable=False, sample_values=categories[:3]
            ),
        ]
        return Schema(
            source=str(self.source),
            fields=fields,
            row_count=len(rows),
            detected_categories=categories,
            detected_channels=[],
        )

    def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
        if n < 1:
            raise ValueError(f"extract_sample requires n >= 1 (got {n})")
        return self._all_rows()[:n]

    def stream(self, batch_size: int = 500) -> Iterator[Batch]:
        if batch_size < 1:
            raise ValueError(f"stream requires batch_size >= 1 (got {batch_size})")
        batch: list[dict[str, Any]] = []
        for row in self._all_rows():
            batch.append(row)
            if len(batch) >= batch_size:
                yield Batch(batch, source=str(self.source))
                batch = []
        if batch:
            yield Batch(batch, source=str(self.source))

    # -- internals ------------------------------------------------------------
    def _all_rows(self) -> list[dict[str, Any]]:
        """Parse every supported file into rows, caching the result."""
        if self._cache is not None:
            return self._cache
        parsers = self._parsers()  # raises if the extra is missing
        rows: list[dict[str, Any]] = []
        for file in self._iter_files():
            parser = parsers.get(file.suffix.lower())
            if parser is None:
                continue  # unsupported extension for this corpus
            if file.stat().st_size > self._max_bytes:
                continue  # guard against a runaway dump
            rows.extend(self._parse_file(parser, file))
        self._cache = rows
        return rows

    def _parse_file(self, parser: ParserBase, file: Path) -> list[dict[str, Any]]:
        data = file.read_bytes()
        sections = _run_coro(parser.parse(data, filename=file.name))
        ext = file.suffix.lstrip(".").lower() or "document"
        out: list[dict[str, Any]] = []
        for idx, section in enumerate(sections):
            text = getattr(section.content, "text", None)
            if not text:
                continue  # skip non-text (image / DataBlock) sections
            out.append(
                {
                    "id": f"{file.name}#{idx}",
                    "content": text,
                    "source": str(file),
                    "category": ext,
                    "metadata": {**(getattr(section, "metadata", {}) or {}), "filename": file.name},
                }
            )
        return out
