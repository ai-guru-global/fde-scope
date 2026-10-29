<!-- fde-scope mirror · repo: calmrocks/ai-engineer-notebooks · license: MIT · commit: 3bf1d778bb97439b9e6ac5bb6de7d4799abe3dd6
     upstream path: utils/README.md · retrieved: 2026-10-06 · verbatim; report issues upstream. -->

# utils

Shared setup now lives in the `aien` package at the repo root (installed by
each notebook's first cell): `from aien import setup`. It does one thing:
load the API key and hand back a ready Groq client.

Deliberately minimal. The moment shared code grows abstractions over the
concepts the notebooks teach, it has failed. Resist building a framework.
This folder is kept as a home for any future notebook-only helper (e.g.
pretty-printing) that isn't worth packaging.
