"""Standalone modal-flow runner: install the built zip, run the
modal scenarios, exit with the result code. For fast iteration.

Usage (Blender): blender --background --factory-startup
    --python-exit-code 1 --python tests/run_modal_standalone.py -- <zip_path>
"""

import importlib
import sys
import zipfile
from pathlib import Path

import bpy

ADDON_ID = "sketchup_modeling"


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :]
    zip_path = Path(argv[0])
    try:
        bpy.ops.extensions.package_install_files(
            filepath=str(zip_path),
            repo="user_default",
            enable_on_install=True,
            overwrite=True,
        )
    except Exception as exc:
        print("operator install failed (%r); manual fallback" % (exc,))
        repo_dir = None
        for repo in bpy.context.preferences.extensions.repos:
            if repo.name == "User Default":
                repo_dir = Path(repo.directory)
                break
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(repo_dir / ADDON_ID)
        bpy.ops.extensions.repo_refresh_all()
        bpy.ops.preferences.addon_enable(module="bl_ext.user_default." + ADDON_ID)
    module_key = None
    for entry in bpy.context.preferences.addons:
        if entry.module == ADDON_ID or entry.module.endswith("." + ADDON_ID):
            module_key = entry.module
            break
    module = importlib.import_module(module_key)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import modal_flows
    import p6_flows
    import shape_flows
    import transform_flows

    code = modal_flows.run(module)
    code += shape_flows.run(module)
    code += transform_flows.run(module)
    code += p6_flows.run(module)
    return code


if __name__ == "__main__":
    sys.exit(main())
