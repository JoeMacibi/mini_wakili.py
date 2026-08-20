"""Command-line entry point for local Wakili research."""

import argparse

from .agent import ResearchAgent
from .agent.tools import CorpusTool
from .config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Wakili research scaffold")
    parser.add_argument("question", nargs="?", default="What documents are available?")
    args = parser.parse_args()
    print(ResearchAgent(CorpusTool(settings.corpus_path)).run(args.question))


if __name__ == "__main__":
    main()
