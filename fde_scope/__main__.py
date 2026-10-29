"""``python -m fde_scope`` — the same entry point as the ``fde-scope`` script.

Exists so a course lab can invoke the CLI without assuming the console script
is on ``PATH``: the verifier falls back to ``sys.executable -m fde_scope`` when
``shutil.which("fde-scope")`` comes up empty (editable checkouts, bare venvs).
"""

from .cli import main

if __name__ == "__main__":
    main()
