"""Read-only bundled assets: repo checkout first, wheel ``_data`` second.

A source checkout keeps its assets where an author expects them — at the repo
root (``docs/``, ``GTM/``, ``course-level-1/``). A wheel cannot: it ships only
``fde_scope/``, so anything the app reads at runtime has to be copied inside
the package by ``pyproject.toml``'s ``force-include``.

Before this module the two halves had drifted apart:

* ``web/course.py`` resolved the lessons against both bases and worked;
* ``web/deps.py`` (catalog, GTM, GitHub resources) and
  ``web/docs_reader.py`` (``/docs/<slug>``) resolved against the repo root
  only, so an installed app answered all of them with an in-app "not
  available in this install" notice. ``course doctor`` G0 passed, and the
  reading room, the 122-page handbook, the GTM site and 20 documents were
  empty — on the *installed* product, which is the one users get.

Every read-only asset root now resolves through :func:`asset_root`, so there is
one answer to "where is the checkout copy" and one answer to "where is the
packaged copy", and a new asset cannot be added to the build without also being
findable.
"""

from __future__ import annotations

# ``docs_reader`` has no top-level dependency on this module (it resolves the
# base lazily inside ``render``), so importing its slug table here is safe and
# keeps the shipped list and the served list from being two hand-kept copies.
from pathlib import Path

from .web.docs_reader import _DOCS

#: Directories ``force-include`` copies into ``fde_scope/_data/``. Listed here
#: (not only in ``pyproject.toml``) because ``tests/test_architecture_guard.py``
#: checks the two agree — a build entry without a resolver entry ships bytes
#: nobody can find, which is how the catalog became an empty notice page.
#: Sources ``force-include`` copies. ``GTM`` is deliberately absent: the
#: marketing board is a 2.6 MB checkout-only asset (fonts included) and an
#: install without it degrades to a notice page, which is an acceptable answer
#: for a link that leaves the product. Everything a *reader* of the app needs
#: inside it — lessons, handbook, documents, smoke fixtures — is here.
PACKAGED_ASSETS: tuple[str, ...] = (
    "course-level-1",
    "docs/skills-catalog/site",
    "examples/quickstart_csv",
    "examples/quickstart_manufacturing",
    "examples/README.md",
) + tuple(path for _slug, path, *_ in _DOCS)


def _candidates() -> tuple[Path, ...]:
    """The bases, in precedence order.

    Checkout first so an author editing a lesson sees it without rebuilding;
    the packaged copy second so an install has something to find. Returned
    lazily as ``Path`` values built from ``__file__`` so a relocation of the
    package (zip import, frozen bundle) still resolves relative to itself.
    """
    here = Path(__file__).resolve()
    # fde_scope/assets.py -> parents[1] is the repo root in a checkout, and the
    # package dir itself in a wheel (where every asset lives under _data/).
    return (here.parents[1], here.parent / "_data")


def asset_root(rel: str) -> Path | None:
    """Directory for a read-only asset, or ``None`` when neither base has it.

    ``rel`` is repo-relative (``"docs/skills-catalog/site"``). Returning ``None``
    rather than raising keeps the callers' existing contract: a missing asset
    degrades to the in-app notice instead of a 500.
    """
    rel_path = Path(rel)
    for base in _candidates():
        candidate = base / rel_path
        if candidate.is_dir():
            return candidate
    return None
