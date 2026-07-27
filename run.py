#!/usr/bin/env python3
"""Entry point for the local AI girlfriend voice assistant.

Usage:
    python run.py                 # use config.yaml
    python run.py --config my.yaml
    python run.py --list-devices  # print available audio devices and exit
"""
from __future__ import annotations

import argparse
import sys

from src.config import Config


def list_devices() -> None:
    import sounddevice as sd

    print(sd.query_devices())


def main() -> int:
    parser = argparse.ArgumentParser(description="Local AI girlfriend (voice-to-voice)")
    parser.add_argument("--config", default="config.yaml", help="path to config file")
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="list audio input/output devices and exit",
    )
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        return 0

    cfg = Config.load(args.config)

    # Import here so --list-devices / --help do not load heavy ML deps.
    from src.pipeline import Pipeline

    Pipeline(cfg).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
