#!/usr/bin/env python3
"""Private local backup; retention/offsite copy are explicit operator policy."""
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
destination = Path('/var/backups/near-intelligence')/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
raise SystemExit(subprocess.call([sys.executable, str(root/'deployment/vps/ops.py'), 'backup', str(destination)]))
