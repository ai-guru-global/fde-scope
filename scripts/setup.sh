#!/bin/sh
# Meoo image deploy — build step. Runs as root in /code (Linux, Python 3.13)
# after the source archive is unpacked; it must leave every runtime dependency
# in place for scripts/start.sh.
set -e
cd /code

# Debian-managed Pythons refuse a bare `pip install` (PEP 668), so prefer a venv
# the image carries into the runtime stage.
if python3 -m venv /code/.venv 2>/dev/null; then
    PY=/code/.venv/bin/python
    "$PY" -m pip install --no-cache-dir --quiet --upgrade pip
    "$PY" -m pip install --no-cache-dir -e ".[web]"
else
    PY=python3
    python3 -m pip install --no-cache-dir --break-system-packages -e ".[web]"
fi

# Editable is load-bearing, not a convenience: fde_scope/web/deps.py resolves
# the skills-catalog portal and the GTM site as
# Path(__file__).resolve().parents[2]/docs/... and .../GTM, which only land on
# /code when the package points at the source tree. A wheel install would
# silently drop the /catalog and /GTM mounts.
FDE_SCOPE_HOME=/tmp/fde-scope-build "$PY" - <<'PYCODE'
from fde_scope.web.deps import catalog_site_dir, gtm_site_dir

catalog = catalog_site_dir()
assert catalog is not None, "docs/skills-catalog/site missing: /catalog would 404"

gtm = gtm_site_dir()
assert gtm is not None, "GTM/ missing: /GTM and the rail link would 404"

import fde_scope.web.app  # noqa: F401  (import-time mounts must not raise)

print(f"setup ok - catalog={catalog} gtm={gtm}")
PYCODE
