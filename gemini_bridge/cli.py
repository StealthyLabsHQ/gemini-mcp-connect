"""
cli.py — Command-line interface entry point.

Usage:
    gemini-bridge-cli "your prompt"
    gemini-bridge-cli --tier flash "your prompt"
    gemini-bridge-cli --status
"""

import sys
from .core import call_gemini, get_status, TIERS


def main() -> None:
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print(__doc__, file=sys.stderr)
        sys.exit(0)

    if "--status" in args:
        sys.stdout.buffer.write(get_status().encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        return

    tier = "pro"
    if "--tier" in args:
        idx = args.index("--tier")
        if idx + 1 >= len(args):
            print("Error: --tier requires a value: lite | flash | pro", file=sys.stderr)
            sys.exit(1)
        tier = args[idx + 1].lower()
        args = args[:idx] + args[idx + 2:]

    if tier not in TIERS:
        print(f"Error: unknown tier '{tier}'. Choose from: {', '.join(TIERS)}", file=sys.stderr)
        sys.exit(1)

    if not args:
        print("Error: no prompt provided.", file=sys.stderr)
        sys.exit(1)

    prompt = " ".join(args)
    result = call_gemini(prompt, tier)

    sys.stdout.buffer.write(result.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")


if __name__ == "__main__":
    main()
