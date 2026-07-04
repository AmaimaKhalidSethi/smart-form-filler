"""
CLI for the Smart Form Filler.

Usage:
    python -m smart_form_filler --form job_application \\
        --text "I'm Jane Doe, jane@example.com, applying for the Backend Engineer role."

    python -m smart_form_filler --interactive

    python -m smart_form_filler --text "..." --auto-detect --out result.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from .agent import run_form_filler
from .groq_client import DEFAULT_MODEL, GroqFormExtractor
from .schemas import FORM_REGISTRY


def _cli_answer_callback(question: str) -> str:
    print("\n" + question)
    return input("> ")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smart Form Filler")
    parser.add_argument(
        "--form",
        choices=list(FORM_REGISTRY.keys()),
        default=None,
        help="Form type to fill. Omit with --auto-detect to let the agent classify it.",
    )
    parser.add_argument("--auto-detect", action="store_true", help="Auto-detect the form type.")
    parser.add_argument("--text", type=str, default=None, help="Natural-language description.")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for the description and any clarifications on the terminal.",
    )
    parser.add_argument(
        "--no-clarify",
        action="store_true",
        help="Disable the clarification loop (single extraction pass only).",
    )
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Groq model id to use.")
    parser.add_argument("--out", type=str, default=None, help="Path to write the resulting JSON.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show pipeline transcript.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    if args.form is None and not args.auto_detect:
        parser.error("Provide --form <type> or pass --auto-detect.")

    description = args.text
    if args.interactive or description is None:
        print("Describe what you'd like to fill out:")
        description = input("> ")

    extractor = GroqFormExtractor(model=args.model)
    answer_cb = None if args.no_clarify else _cli_answer_callback

    try:
        result = run_form_filler(
            description=description,
            form_type=args.form,
            extractor=extractor,
            answer_callback=answer_cb,
        )
    except Exception as exc:  # noqa: BLE001 - top-level CLI boundary
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.verbose:
        print("\n--- transcript ---")
        print("\n".join(result.transcript))

    output = {
        "form_type": result.form_type,
        "complete": result.fully_complete,
        "clarification_rounds_used": result.rounds_used,
        "data": result.data.model_dump(),
    }
    text = json.dumps(output, indent=2, default=str)
    print("\n--- result ---")
    print(text)

    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
        print(f"\nWritten to {args.out}")

    return 0 if result.fully_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
