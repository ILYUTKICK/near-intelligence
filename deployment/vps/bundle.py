#!/usr/bin/env python3
"""Package tracked source plus the explicit VPS handoff, never local state."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
from datetime import datetime, timezone

EXTRAS = (
    'docs/VPS_DEPLOYMENT.md',
    'docs/LOCAL_PREVIEW_RECOVERY.md',
    'docs/verification/ni-090.md',
    'deployment/vps/compose.yaml',
    'deployment/vps/Caddyfile',
    'deployment/vps/.env.example',
    'deployment/vps/env.py',
    'deployment/vps/ops.py',
    'deployment/vps/bundle.py',
    'deployment/vps/verify_source.py',
    'deployment/vps/backup_daily.py',
    'deployment/vps/tests/test_env.py',
    'deployment/vps/tests/test_operations.py',
    'deployment/vps/systemd/near-exports.service',
    'deployment/vps/systemd/near-exports.timer',
    'deployment/vps/systemd/near-export-sweep.service',
    'deployment/vps/systemd/near-export-sweep.timer',
    'deployment/vps/systemd/near-backup.service',
    'deployment/vps/systemd/near-backup.timer',
)
DENIED_PARTS = {'.git', '.local', '.aws', '.codex', 'node_modules', '.venv', '__pycache__', '.next', 'output', 'artifacts', 'private-exports'}


def allowed(name: str) -> bool:
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or any(x in DENIED_PARTS for x in p.parts):
        return False
    if any(x.startswith('.env') and x != '.env.example' for x in p.parts):
        return False
    if p.suffix.lower() in {'.pem', '.key', '.p12', '.pfx', '.log', '.pid', '.dump', '.tar', '.gz'}:
        return False
    if name == 'docker-compose.override.yml':
        return False
    if p.parts[0] == 'research':
        return p.suffix == '.md' or bool(re.fullmatch(r'research/models/(?:readiness|fit|diagnostics)\.py|research/models/(?:configs|fit_configs|diagnostics_configs)/[\w-]+\.json', name))
    if p.parts[0] == 'product-plan':
        return p.suffix in {'.md', '.svg', '.png'}
    return True


def collect(root: Path) -> dict[str, bytes]:
    names = set(subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z']).decode().split('\0')) - {''}
    for extra in EXTRAS:
        p = root / extra
        if p.is_file():
            names.add(extra)
    result = {}
    for name in sorted(names):
        p = root / name
        if not allowed(name) or not p.exists():
            continue
        if p.is_symlink() or root.resolve() not in p.resolve().parents:
            raise ValueError(f'Refusing source symlink: {name}')
        result[name] = p.read_bytes()
    required = {'Dockerfile.web', 'Dockerfile.api', 'pnpm-lock.yaml', 'apps/api/uv.lock', 'deployment/vps/compose.yaml', 'deployment/vps/env.py', 'deployment/vps/ops.py'}
    if required - result.keys():
        raise ValueError('Incomplete source handoff: ' + ', '.join(sorted(required-result.keys())))
    return result


def create(root: Path, out: Path) -> dict:
    files = collect(root)
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    manifest = {'format': 1, 'git_commit': subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD']).decode().strip(), 'source_sha256': digest, 'release_tag': f'{stamp}-{digest[:16]}', 'files': hashes}
    out.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive output: never overwrite an older handoff silently.
    with out.open('xb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0, filename='') as compressed, tarfile.open(fileobj=compressed, mode='w|') as archive:
        entries = {**files, 'SOURCE_MANIFEST.json': (json.dumps(manifest, indent=2, sort_keys=True)+'\n').encode()}
        for name, data in sorted(entries.items()):
            info = tarfile.TarInfo('near-intelligence/'+name)
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = create(args.root.resolve(), args.output.resolve())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'Bundle failed: {exc}\n')
    print(json.dumps({'output': str(args.output), 'release_tag': manifest['release_tag'], 'source_sha256': manifest['source_sha256'], 'file_count': len(manifest['files'])}, indent=2))
