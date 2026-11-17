#!/usr/bin/env bash
# T2 version matrix: 4.5 LTS + 5.1.2 + 5.2 LTS (baseline), 5.3.0 smoke-only.
# Each run gets an isolated HOME so the real user config is untouched.
set -u
set -o pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ZIP="$(ls -t "$ROOT"/build/sketchup_modeling-*.zip 2>/dev/null | head -1)"
if [ -z "$ZIP" ]; then echo "no built zip; run: python3 build.py"; exit 1; fi
echo "zip: $ZIP"
FAIL=0
for V in 4.5.16 5.1.2 5.2.4; do
  BL="$ROOT/tools/blender-$V-linux-x64/blender"
  TMP="$(mktemp -d)"
  echo "===== T2 Blender $V ====="
  if HOME="$TMP" XDG_CONFIG_HOME="$TMP/.config" "$BL" --background --factory-startup \
      --python-exit-code 1 --python "$ROOT/tests/run_t2.py" -- "$ZIP" 2>&1 | grep -v "^Fra:\|^Saved:\|Time:"; then
    echo "T2 $V: PASS"
  else
    echo "T2 $V: FAIL"; FAIL=1
  fi
  rm -rf "$TMP"
done
BL="$ROOT/tools/blender-5.3.0-linux-x64/blender"
TMP="$(mktemp -d)"
echo "===== T2 Blender 5.3.0 (smoke only) ====="
if HOME="$TMP" XDG_CONFIG_HOME="$TMP/.config" "$BL" --background --factory-startup \
    --python-exit-code 1 --python "$ROOT/tests/run_t2.py" -- "$ZIP" 2>&1 | grep -v "^Fra:\|^Saved:\|Time:"; then
  echo "T2 5.3.0 smoke: PASS"
else
  echo "T2 5.3.0 smoke: FAIL (non-baseline, warning only)"
fi
rm -rf "$TMP"
exit $FAIL
