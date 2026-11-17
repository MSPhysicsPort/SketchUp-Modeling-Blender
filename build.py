"""Build the installable Extension .zip and validate it (T0).

Usage: python3 build.py
Output: build/sketchup_modeling-<version>.zip

Validates: manifest TOML + required fields, tagline rules, zip
top-level structure (manifest + __init__.py at the top, no extra
folder, no tests, no __pycache__).
"""

import re
import sys
import zipfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11 fallback.
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent
ADDON_DIR = ROOT / "addon"
BUILD_DIR = ROOT / "build"

REQUIRED_FIELDS = [
    "schema_version",
    "id",
    "version",
    "name",
    "tagline",
    "maintainer",
    "type",
    "blender_version_min",
    "license",
]


def load_manifest():
    manifest_path = ADDON_DIR / "blender_manifest.toml"
    with open(manifest_path, "rb") as handle:
        return tomllib.load(handle)


def validate_manifest(manifest):
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in manifest:
            errors.append("missing manifest field: %s" % field)
    if manifest.get("schema_version") != "1.0.0":
        errors.append("schema_version must be '1.0.0'")
    addon_id = manifest.get("id", "")
    if not re.fullmatch(r"[a-z0-9_]+", addon_id):
        errors.append("id must be lowercase letters, digits, underscores: %r" % addon_id)
    version = manifest.get("version", "")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        errors.append("version must be semantic (x.y.z): %r" % version)
    tagline = manifest.get("tagline", "")
    if len(tagline) > 64:
        errors.append("tagline exceeds 64 characters")
    if tagline and tagline[-1] in ".!?":
        errors.append("tagline must not end with punctuation")
    if manifest.get("type") != "add-on":
        errors.append("type must be 'add-on'")
    if manifest.get("blender_version_min") != "4.2.0":
        errors.append("blender_version_min must be '4.2.0' (D6)")
    if errors:
        raise ValueError("manifest validation failed:\n" + "\n".join(errors))
    return manifest


def build_zip():
    manifest = validate_manifest(load_manifest())
    BUILD_DIR.mkdir(exist_ok=True)
    zip_path = BUILD_DIR / ("sketchup_modeling-%s.zip" % manifest["version"])
    files = []
    for path in sorted(ADDON_DIR.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        files.append(path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ADDON_DIR).as_posix())
    validate_zip(zip_path)
    return zip_path, files


def validate_zip(zip_path):
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
    top_level = {name.split("/")[0] for name in names}
    errors = []
    if "blender_manifest.toml" not in names:
        errors.append("manifest not at zip top level")
    if "__init__.py" not in names:
        errors.append("__init__.py not at zip top level")
    if len(top_level) == 1 and names[0].count("/") > 0:
        errors.append("zip wraps everything in an extra folder")
    if any(name.startswith("tests/") or "/tests/" in name for name in names):
        errors.append("tests must not ship in the zip")
    if any("__pycache__" in name or name.endswith(".pyc") for name in names):
        errors.append("bytecode must not ship in the zip")
    if errors:
        raise ValueError("zip validation failed:\n" + "\n".join(errors))
    return names


def validate_imports(files):
    """Root-level addon modules must use single-dot relative
    imports: ``from ..x`` from the package root resolves outside
    the extension (bl_ext.user_default.x) and breaks install.
    Caught three times the hard way; now a build error."""
    import re

    errors = []
    pattern = re.compile(r"^from \.\.(core|data|i18n|draw|tools|operators)\b", re.M)
    for path in files:
        if path.suffix != ".py" or path.parent != ADDON_DIR:
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            errors.append(
                "%s: double-dot relative import in a root module"
                % path.relative_to(ADDON_DIR)
            )
    if errors:
        raise ValueError("import validation failed:\n" + "\n".join(errors))


def main():
    zip_path, files = build_zip()
    print("built %s (%d files)" % (zip_path, len(files)))
    for path in files:
        print("  " + path.relative_to(ADDON_DIR).as_posix())
    validate_imports(files)
    print("T0 manifest+zip validation: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
