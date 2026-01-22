"""
Entry point for running worker as module.

Usage:
    python -m worker.cli <command>
"""

from worker.cli import cli

if __name__ == "__main__":
    cli()
