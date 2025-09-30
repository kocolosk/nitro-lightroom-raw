#!/usr/bin/env python3
"""
Lightweight test harness for nitro_to_crs_converter.py.

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

        # If an explicit cropRect is provided, test the rotation+crop path via nitro semantics
        if "cropRect" in case:
            cropRect = case["cropRect"]
            nitro_json = {
                "cropRect": cropRect,
                "orientationIsRelative": False,
                "numeric": {"straighten": deg},
                "aspectRatioType": 0,
            }
            crs = conv.nitro_crop_to_crs(nitro_json, int(W), int(H))
            cl = float(crs.get('crs:CropLeft', 0.0))
            ct = float(crs.get('crs:CropTop', 0.0))
            cr = float(crs.get('crs:CropRight', 1.0))
            cb = float(crs.get('crs:CropBottom', 1.0))
        else:
            cl, ct, cr, cb = conv.compute_lightroom_crop_unit_square(int(W), int(H), float(deg))

        rw = W * (cr - cl)
        rh = H * (cb - ct)
        ar = (rw / rh) if rh else float("inf")
        ar0 = (W / H) if H else float("inf")

        # Validate Lightroom margins if provided
        ltrb_status = None
        if expected and all(k in expected for k in ("left", "top")):
            el = float(expected["left"])  # expected left
            et = float(expected["top"])   # expected top
            ok_l = approx_equal(cl, el, tol)
            ok_t = approx_equal(ct, et, tol)
            ok_r = ok_b = True
            er = eb = None
            if expected and all(k in expected for k in ("right", "bottom")):
                er = float(expected["right"])  # expected right
                eb = float(expected["bottom"]) # expected bottom
                ok_r = approx_equal(cr, er, tol)
                ok_b = approx_equal(cb, eb, tol)
            ltrb_status = ok_l and ok_t and ok_r and ok_b

        # If cropRect given, also validate AABB size and lower-left (x1,y1) under LR fit-to-height scale
        aabb_status = None
        if "cropRect" in case:
            ew, eh = case["cropRect"][1]
            x1, y1 = case["cropRect"][0]

            # Pre-rotation crop in pixels
            xmin = cl * W
            xmax = cr * W
            ymin = (1.0 - cb) * H
            ymax = (1.0 - ct) * H

            # Rotate corners around image center to get final AABB, then apply uniform fit-to-height scale
            theta = math.radians(float(deg))
            cth = math.cos(theta)
            sth = math.sin(theta)
            cx = W * 0.5
            cy = H * 0.5
            pts = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]

            r = W / H
            s_fh = 1.0 / (abs(math.cos(theta)) + r * abs(math.sin(theta)))

            def fwd(px, py):
                dx = px - cx
                dy = py - cy
                rx = dx * cth - dy * sth
                ry = dx * sth + dy * cth
                return (cx + s_fh * rx, cy + s_fh * ry)

            rot = [fwd(px, py) for (px, py) in pts]
            rxmin = min(p[0] for p in rot)
            rymin = min(p[1] for p in rot)
            rxmax = max(p[0] for p in rot)
            rymax = max(p[1] for p in rot)

            rw2 = rxmax - rxmin
            rh2 = rymax - rymin

            ok_w = approx_equal(rw2, ew, max(1.0, tol * W))
            ok_h = approx_equal(rh2, eh, max(1.0, tol * H))
            ok_x = approx_equal(rxmin, float(x1), max(2.0, tol * W))
            ok_y = approx_equal(rymin, float(y1), max(2.0, tol * H))
            aabb_status = ok_w and ok_h and ok_x and ok_y

        # Final status aggregates both checks (when present)
        if ltrb_status is not None or aabb_status is not None:
            status = "PASS" if ((ltrb_status is None or ltrb_status) and (aabb_status is None or aabb_status)) else "FAIL"
            if status == "FAIL":
                failures += 1
            lines = [
                f"[{idx}] {name}: {status}",
                f"  Input:   W={W}, H={H}, rot={deg}°",
            ]
            if expected and all(k in expected for k in ("left", "top")):
                if expected and all(k in expected for k in ("right", "bottom")):
                    lines.append(f"  Expect:  LTRB=({el:.6f},{et:.6f},{er:.6f},{eb:.6f}) (±{tol:g})")
                else:
                    lines.append(f"  Expect:  Left={el:.6f}, Top={et:.6f} (±{tol:g})")
                lines.append(f"  Actual:  LTRB=({cl:.6f},{ct:.6f},{cr:.6f},{cb:.6f})")
            if "cropRect" in case:
                lines.append(f"  Expect:  AABB {ew:.3f}x{eh:.3f} at ({x1:.3f},{y1:.3f})")
                lines.append(f"  Actual:  AABB {rw2:.3f}x{rh2:.3f} at ({rxmin:.3f},{rymin:.3f})")
            lines.append(f"  Result:  size={rw:.0f}x{rh:.0f}, AR={ar:.6f}, original AR={ar0:.6f}")
            print("\n".join(lines) + "\n")
        else:
            # fallback print when no expectations provided
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
