"""Command-line entry point for the grounded local research agent."""

import argparse
import json

from mini_wakili import MiniWakiliAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Mini-Wakili legal research locally")
    parser.add_argument("question", nargs="?", default="What documents are available?")
    args = parser.parse_args()
    print(json.dumps(MiniWakiliAgent().execute_research(args.question), indent=2))


if __name__ == "__main__":
    main()
