#!/usr/bin/env python3
"""
profile_app.py — comprehensive CDK-python synth profiler.

Runs against a single benchmark app and decomposes where synth time goes, so
you can attribute the lazy-import / check_type savings to specific causes.

It measures, in one fresh process:

  1. Build detection      — is the installed aws_cdk the lazy or eager build?
  2. Import cost          — aws_cdk core + each service module the app imports
                            (one-time startup cost; does NOT scale with resources)
  3. Synth cost (cProfile)— full app.py execution, attributed to the runtime
                            hot-spots that lazy loading / check_type touch:
                              - typing.get_type_hints   (per-construct annotations)
                              - jsii check_type          (per-argument validation)
                              - register_type/reference  (metaclass registration)
                              - proxy_for                (interface proxy build)
                              - importlib.import_module  (module loading)
                              - kernel IPC (process.py)  (NOT improved by this branch)
  4. Call counts          — how many times the per-resource hot-spots fire,
                            which is what makes the savings scale with resources.

Output: a single JSON object (to stdout or --out FILE) so results from several
apps can be accumulated and compared.

Usage (with the app's OWN venv python):
    APP=/path/to/app-1
    "$APP/.venv/bin/python" profile_app.py "$APP" --stacks 5 --resources 400 --out app-1.json

Notes:
  - Run with each app's own venv python so the installed aws_cdk/jsii is the one
    measured.
  - --stacks / --resources override NUM_STACKS / RESOURCES_PER_STACK. Use a small
    value (e.g. 5 stacks) for fast, representative profiling; the per-resource
    costs scale linearly so you don't need the full 400-stack workload.
"""

import argparse
import cProfile
import importlib
import io
import json
import os
import pstats
import re
import sys
import time


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def detect_build(site_pkg_aws_cdk_init):
    """Return 'lazy' if the generated code uses _LAZY_CLASSES, else 'eager'."""
    try:
        # Sample a representative service module rather than the package root.
        sample = os.path.join(
            os.path.dirname(site_pkg_aws_cdk_init), "aws_ssm", "__init__.py"
        )
        with open(sample, encoding="utf-8") as f:
            head = f.read(20000)
        return "lazy" if "_LAZY_CLASSES" in head else "eager"
    except OSError:
        return "unknown"


def detect_checktype_style(jsii_pkg_dir):
    """Return 'cached' (this branch) or 'per-call' (main) for check_type."""
    try:
        with open(
            os.path.join(jsii_pkg_dir, "_type_checking.py"), encoding="utf-8"
        ) as f:
            src = f.read()
        return "cached" if "_resolved_check" in src else "per-call"
    except OSError:
        return "unknown"


def parse_service_modules(app_py_src):
    """Extract aws_cdk.aws_* service modules imported by the app (skip core)."""
    mods = re.findall(r"\baws_(\w+)\s+as\s+", app_py_src)
    return [f"aws_cdk.aws_{m}" for m in mods if m != "cdk"]


def ms(seconds):
    return round(seconds * 1000.0, 1)


# --------------------------------------------------------------------------
# Profiling phases
# --------------------------------------------------------------------------
def measure_imports(service_modules):
    """Measure one-time import cost. Must run before anything imports aws_cdk."""
    t0 = time.perf_counter()
    import aws_cdk  # noqa: F401

    t_core = time.perf_counter() - t0

    per_module = {}
    t0 = time.perf_counter()
    for m in service_modules:
        s = time.perf_counter()
        try:
            importlib.import_module(m)
            per_module[m] = ms(time.perf_counter() - s)
        except Exception as e:  # noqa: BLE001
            per_module[m] = f"ERROR: {e}"
    t_services = time.perf_counter() - t0

    return {
        "aws_cdk_path": aws_cdk.__file__,
        "core_ms": ms(t_core),
        "services_ms": ms(t_services),
        "total_ms": ms(t_core + t_services),
        "service_count": len(service_modules),
        "per_module_ms": per_module,
    }


# Hot-spots to attribute. Matched against (filename, function-name).
HOTSPOTS = [
    ("get_type_hints", lambda fn, name: name == "get_type_hints"),
    ("check_type", lambda fn, name: fn.endswith("_type_checking.py")),
    ("register_type", lambda fn, name: name == "register_type"),
    ("register_reference", lambda fn, name: name == "register_reference"),
    ("proxy_for", lambda fn, name: name == "proxy_for"),
    ("import_module", lambda fn, name: name == "import_module"),
    (
        "kernel_ipc",
        lambda fn, name: fn.replace("\\", "/").endswith(
            "_kernel/providers/process.py"
        ),
    ),
    ("lazy_getattr", lambda fn, name: name == "__getattr__" and "aws_cdk" in fn),
]


def measure_synth(app_dir, app_py_src):
    """cProfile the full synth and attribute cumulative/self time + call counts."""
    code = compile(app_py_src, os.path.join(app_dir, "app.py"), "exec")
    globs = {"__name__": "__main__", "__file__": os.path.join(app_dir, "app.py")}

    pr = cProfile.Profile()
    t0 = time.perf_counter()
    pr.enable()
    exec(code, globs)
    pr.disable()
    wall = time.perf_counter() - t0

    stats = pstats.Stats(pr)
    # stats.stats: {(file, line, name): (call_count, ncalls, tottime, cumtime, callers)}
    attribution = {}
    for label, pred in HOTSPOTS:
        calls = 0
        tottime = 0.0
        cumtime = 0.0
        for (fn, _ln, name), (_cc, nc, tt, ct, _callers) in stats.stats.items():
            if pred(fn, name):
                calls += nc
                tottime += tt
                cumtime += ct
        attribution[label] = {
            "calls": calls,
            "self_ms": ms(tottime),
            "cum_ms": ms(cumtime),
        }

    # Top 15 functions by cumulative time, for an at-a-glance view.
    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(15)
    top = [
        line.strip()
        for line in s.getvalue().splitlines()
        if line.strip() and "/" in line
    ][:15]

    return {"wall_ms": ms(wall), "attribution": attribution, "top15": top}


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("app_dir", help="Path to the benchmark app folder")
    ap.add_argument("--stacks", type=int, default=5, help="NUM_STACKS (default 5)")
    ap.add_argument(
        "--resources", type=int, default=400, help="RESOURCES_PER_STACK (default 400)"
    )
    ap.add_argument("--out", help="Write JSON result here (default: stdout)")
    args = ap.parse_args()

    app_dir = os.path.abspath(args.app_dir)
    app_py = os.path.join(app_dir, "app.py")
    if not os.path.isfile(app_py):
        sys.exit(f"No app.py in {app_dir}")

    # Configure workload BEFORE importing/executing the app.
    os.environ["NUM_STACKS"] = str(args.stacks)
    os.environ["RESOURCES_PER_STACK"] = str(args.resources)

    # Make the app's local packages (benchmark/) importable and run from its dir
    # so cdk.out lands in the right place.
    sys.path.insert(0, app_dir)
    os.chdir(app_dir)

    with open(app_py, encoding="utf-8") as f:
        app_py_src = f.read()
    service_modules = parse_service_modules(app_py_src)

    # Phase 2 (imports) must precede everything that touches aws_cdk.
    imports = measure_imports(service_modules)

    # Build detection (after we know where aws_cdk lives).
    aws_cdk_init = imports["aws_cdk_path"]
    site_packages = os.path.dirname(os.path.dirname(aws_cdk_init))
    build = detect_build(aws_cdk_init)
    checktype = detect_checktype_style(os.path.join(site_packages, "jsii"))

    # Phase 3+4 (synth + attribution).
    synth = measure_synth(app_dir, app_py_src)

    result = {
        "app": os.path.basename(app_dir),
        "app_dir": app_dir,
        "python": sys.version.split()[0],
        "build": build,  # lazy | eager
        "check_type": checktype,  # cached | per-call
        "workload": {"stacks": args.stacks, "resources_per_stack": args.resources},
        "total_resources": args.stacks * args.resources,
        "imports": imports,
        "synth": synth,
    }

    text = json.dumps(result, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        # Brief human-readable summary to stderr so parallel runs show progress.
        a = synth["attribution"]
        print(
            f"[{result['app']}] build={build} check_type={checktype} "
            f"synth={synth['wall_ms']}ms import={imports['total_ms']}ms "
            f"get_type_hints={a['get_type_hints']['cum_ms']}ms "
            f"check_type={a['check_type']['cum_ms']}ms "
            f"ipc={a['kernel_ipc']['cum_ms']}ms -> {args.out}",
            file=sys.stderr,
        )
    else:
        print(text)


if __name__ == "__main__":
    main()
