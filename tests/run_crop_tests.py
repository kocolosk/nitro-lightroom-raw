#!/usr/bin/env python3
"""
Lightweight test harness for compute_lightroom_crop in nitro_to_crs_converter.py.

Usage:
  python tests/run_crop_tests.py                      # uses tests/crop_tests.json if present
  python tests/run_crop_tests.py path/to/cases.json   # custom cases file

Case format (JSON array of objects):
[
  {
    "name": "optional label",
    "width": 6960,
    "height": 4640,
    "rotation_deg": -0.895569,
    "expected": { "left": 0.006364, "top": 0.022911 },  # optional; if omitted, we just print computed
    "tolerance": 0.0005                                   # optional per-case tolerance (default 1e-6)
  }
]

Notes:
- If expected is omitted, the harness prints the computed values to help you fill the JSON.
- PASS/FAIL only applies when expected values are provided.
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_cases(path: Path):
    if not path.exists():
        # Create a starter file to help the user
        starter = [
            {
                "name": "template - fill expected or add your own",
                "width": 6960,
                "height": 4640,
                "rotation_deg": -0.895569,
                # "expected": { "left": 0.006364, "top": 0.022911 },
                "tolerance": 0.0005
            }
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(starter, indent=2) + "\n", encoding="utf-8")
        print(f"Created starter test cases at {path}. Edit this file and re-run.")
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading cases from {path}: {e}")
        return []


def approx_equal(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


def main():
    # Ensure we can import the converter from project root
    root = project_root()
    sys.path.insert(0, str(root))

    try:
        from nitro_to_crs_converter import NitroToCRSConverter
    except Exception as e:
        print(f"Failed to import NitroToCRSConverter: {e}")
        sys.exit(2)

    cases_path = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "tests" / "crop_tests.json"
    cases = load_cases(cases_path)
    if not cases:
        # Starter written or no cases found
        sys.exit(0)

    conv = NitroToCRSConverter()
    failures = 0

    print(f"Running {len(cases)} test case(s) from {cases_path}...\n")

    for idx, case in enumerate(cases, 1):
        name = case.get("name") or f"case-{idx}"
        W = case.get("width")
        H = case.get("height")
        deg = case.get("rotation_deg")
        expected = case.get("expected")
        tol = float(case.get("tolerance", 1e-6))

        # Validate inputs
        if not all(isinstance(x, (int, float)) for x in (W, H, deg)):
            print(f"[{idx}] {name}: INVALID INPUT (width/height/rotation)")
            failures += 1
            continue

        cl, ct, cr, cb = conv.compute_lightroom_crop(int(W), int(H), float(deg))
        rw = W * (cr - cl)
        rh = H * (cb - ct)
        ar = (rw / rh) if rh else float("inf")
        ar0 = (W / H) if H else float("inf")

        if expected and all(k in expected for k in ("left", "top")):
            el = float(expected["left"])  # expected left
            et = float(expected["top"])   # expected top
            ok_l = approx_equal(cl, el, tol)
            ok_t = approx_equal(ct, et, tol)
            status = "PASS" if (ok_l and ok_t) else "FAIL"
            if status == "FAIL":
                failures += 1
            print(
                f"[{idx}] {name}: {status}\n"
                f"  Input:   W={W}, H={H}, rot={deg}°\n"
                f"  Expect:  Left={el:.6f}, Top={et:.6f} (±{tol:g})\n"
                f"  Actual:  Left={cl:.6f}, Top={ct:.6f} | Right={cr:.6f}, Bottom={cb:.6f}\n"
                f"  Result:  size={rw:.0f}x{rh:.0f}, AR={ar:.6f}, original AR={ar0:.6f}\n"
            )
        else:
            print(
                f"[{idx}] {name}: COMPUTED\n"
                f"  Input:   W={W}, H={H}, rot={deg}°\n"
                f"  Actual:  Left={cl:.6f}, Top={ct:.6f} | Right={cr:.6f}, Bottom={cb:.6f}\n"
                f"  Result:  size={rw:.0f}x{rh:.0f}, AR={ar:.6f}, original AR={ar0:.6f}\n"
                f"  Tip: add 'expected': {{ 'left': ..., 'top': ... }} to assert this case.\n"
            )

    if failures:
        print(f"\nSummary: {failures} failure(s).")
        sys.exit(1)
    else:
        print("\nSummary: all tests passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
