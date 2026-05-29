"""
scripts/build_dist.py — NitroFind distribution archive assembler.

Copies the pre-extracted Elasticsearch 8.18 directory alongside the
PyInstaller onedir output (dist/NitroFind/), then zips everything into
the final distributable archive.

Two-step operation:
  1. Copy the ES directory (from ES_BUNDLE) into dist/NitroFind/ as a sibling
     of NitroFind.exe and _internal/
  2. Zip the entire dist/NitroFind/ tree to dist/NitroFind-v1.0-windows-x86_64.zip

Usage:
    ES_BUNDLE=/path/to/elasticsearch-8.18.0 python scripts/build_dist.py
    # On Windows:
    # set ES_BUNDLE=C:\\path\\to\\elasticsearch-8.18.0
    # python scripts\\build_dist.py

Prerequisites:
    - pyinstaller nitrofind.spec must have been run first
    - dist/NitroFind/ must exist (PyInstaller onedir output)
    - ES_BUNDLE env var must point to an extracted elasticsearch-8.18.0 directory

Security: build-time only script; no untrusted inputs; PKG-01.
Source: RESEARCH.md Pattern 5 "Post-Build Archive Assembly"
"""

import os
import re
import shutil
import sys
import zipfile
from pathlib import Path


def main() -> None:
    # -----------------------------------------------------------------------
    # Constants — local to main() following setup_es.py style
    # -----------------------------------------------------------------------
    DIST_DIR = Path("dist") / "NitroFind"
    OUT_ZIP  = Path("dist") / "NitroFind-v1.0-windows-x86_64.zip"

    # -----------------------------------------------------------------------
    # Input validation — validate inputs before acting (setup_es.py pattern)
    # -----------------------------------------------------------------------
    es_bundle = os.environ.get("ES_BUNDLE")
    if not es_bundle:
        print("ES_BUNDLE is not set. Set it to your elasticsearch-8.18.0 directory.")
        sys.exit(1)

    if not os.path.isdir(es_bundle):
        print("ES_BUNDLE is not a valid directory: %s" % es_bundle)
        sys.exit(1)

    if not DIST_DIR.exists():
        print("dist/NitroFind/ not found. Run pyinstaller nitrofind.spec first.")
        sys.exit(1)

    es_src = Path(es_bundle)

    # WR-01: Validate directory name matches expected pattern before proceeding.
    # A name that collides with an existing sub-path of dist/NitroFind/ (e.g.
    # "_internal") would cause shutil.rmtree(es_dest) to silently destroy the
    # PyInstaller bundle. The pattern also ensures resolve_es_home() can find
    # the directory at runtime via its elasticsearch-8.* glob.
    if not re.match(r"^elasticsearch-8\.\d+", es_src.name):
        print(
            "ES_BUNDLE directory name must match 'elasticsearch-8.*' "
            f"(got '{es_src.name}'). This is required so resolve_es_home() "
            "can find it at runtime."
        )
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Step 1 — Copy ES directory alongside PyInstaller output
    # Preserves the elasticsearch-8.18.0 directory name from ES_BUNDLE so
    # resolve_es_home() can glob for elasticsearch-8.* at runtime (PKG-01).
    # -----------------------------------------------------------------------
    es_dest = DIST_DIR / es_src.name   # e.g., dist/NitroFind/elasticsearch-8.18.0
    if es_dest.exists():
        print("Removing existing %s" % es_dest)
        shutil.rmtree(es_dest)

    shutil.copytree(str(es_src), str(es_dest))
    print("Copied %s -> %s" % (es_src, es_dest))

    # -----------------------------------------------------------------------
    # Step 2 — Zip the NitroFind/ folder into the distributable archive
    # All entries are rooted under NitroFind/ — no absolute paths, no ..
    # components (T-05-04: zip slip mitigation).
    # -----------------------------------------------------------------------
    if OUT_ZIP.exists():
        print("Removing existing %s" % OUT_ZIP)
        OUT_ZIP.unlink()

    # PKG-01: ZIP_DEFLATED level 6 balances compression ratio vs build time;
    # standard .zip extractable by Windows Explorer natively.
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:  # Source: RESEARCH.md Pattern 5
        for f in DIST_DIR.rglob("*"):
            if f.is_file():
                zf.write(f, Path("NitroFind") / f.relative_to(DIST_DIR))

    print("Created: %s  (%d MB)" % (OUT_ZIP, OUT_ZIP.stat().st_size // 1024**2))


if __name__ == "__main__":
    main()
