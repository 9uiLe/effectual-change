"""Fictional local development-assistant CLI used as an editing fixture."""

import argparse
import json


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps({"ready": True}))


if __name__ == "__main__":
    main()
