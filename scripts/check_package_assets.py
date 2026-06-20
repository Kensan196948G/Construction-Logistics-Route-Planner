"""Assert the built wheel ships every static asset the app serves at runtime.

A non-recursive ``package-data`` glob (``static/*``) once silently dropped the
vendored Leaflet tree (``static/vendor/leaflet/**``). Editable installs used by
CI/dev kept working because they import straight from the source tree, so the
gap was invisible there -- but ``pip install .`` (the Docker deployment path)
shipped a wheel without Leaflet, breaking the route map in production.

This guard rebuilds that invariant: it inspects a built wheel and fails if any
asset the UI loads is missing from the package. Run it in CI right after
``python -m build --wheel``; locally, pass a wheel path explicitly.
"""

from __future__ import annotations

import glob
import sys
import zipfile

# Assets the served UI references at runtime; all must survive packaging.
REQUIRED = (
    "app/static/index.html",
    "app/static/app.js",
    "app/static/component.js",
    "app/static/dc-runtime.js",
    "app/static/styles.css",
    "app/static/vendor/leaflet/leaflet.js",
    "app/static/vendor/leaflet/leaflet.css",
    "app/static/vendor/leaflet/images/marker-icon.png",
    "app/static/vendor/leaflet/images/marker-shadow.png",
)


def main(argv: list[str]) -> int:
    wheels = argv[1:] or glob.glob("dist/*.whl")
    if not wheels:
        print(
            "no wheel found; build one first with `python -m build --wheel`",
            file=sys.stderr,
        )
        return 1

    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as zf:
        names = set(zf.namelist())
    missing = [asset for asset in REQUIRED if asset not in names]
    if missing:
        print(f"{wheel}: missing {len(missing)} required static asset(s):")
        for asset in missing:
            print(f"  - {asset}")
        return 1

    print(f"{wheel}: all {len(REQUIRED)} required static assets packaged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
