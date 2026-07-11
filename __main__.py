import argparse
from pathlib import Path
from .core import DEFAULT_ROOTS, ROOT
from .api import run_server


def main():
    ap = argparse.ArgumentParser(
        description="Read-only live dashboard for echo-chamber run outputs: "
                    "browses every run_meta.json-marked run under the given roots.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--interval", type=float, default=5.0,
                    help="GUI-mode refresh period, seconds (web UI has its own control)")
    ap.add_argument("--root", action="append", default=None,
                    help="run-output root to scan (repeatable; "
                         "default: data/ and data_hdd1/ if present)")
    ap.add_argument("--serve", action="store_true",
                    help="serve the interactive web dashboard (the supported mode)")
    ap.add_argument("--host", default="127.0.0.1", help="--serve bind address")
    ap.add_argument("--port", type=int, default=8765, help="--serve port")
    args = ap.parse_args()

    roots = args.root if args.root else DEFAULT_ROOTS
    roots = [Path(r) if Path(r).is_absolute() else ROOT / r for r in roots]
    roots = [r for r in roots if r.is_dir()]
    if not roots:
        raise SystemExit(f"no existing run-output roots among: "
                         f"{args.root or DEFAULT_ROOTS} (relative to {ROOT})")

    if args.serve:
        run_server(roots, args.host, args.port)
    else:
        # gui.py is kept as-is from upstream; it reads the upstream results/
        # layout and is not wired to the echo-chamber data layer.
        try:
            from .gui import run_gui
        except ImportError:
            raise SystemExit("GUI mode is not supported on the echo-chamber "
                             "data layer; use --serve.")
        run_gui(ROOT / "logs", None, args.interval)


if __name__ == "__main__":
    main()
