"""Entry point for ``python -m near_api.datasets`` (NI-028 operator CLI)."""

import sys

from near_api.datasets.cli import main

if __name__ == "__main__":
    sys.exit(main())
