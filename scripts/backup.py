#!/usr/bin/env python3
"""One-shot backup entrypoint for the backup container / cron."""
from __future__ import annotations

import json
import sys

from app.deploy.backup import run_full_backup, list_backups


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        print(json.dumps(list_backups(), indent=2))
        return
    result = run_full_backup()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
