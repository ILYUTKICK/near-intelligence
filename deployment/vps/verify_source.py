#!/usr/bin/env python3
"""Verify the extracted source manifest before building. No network or secrets."""
import hashlib
import json
from pathlib import Path
import re


def verify(root: Path) -> dict:
    manifest = json.loads((root/'SOURCE_MANIFEST.json').read_text())
    if not isinstance(manifest, dict):
        raise ValueError('Unsupported source manifest')
    hashes = manifest['files']
    if manifest.get('format') != 1 or not isinstance(hashes, dict):
        raise ValueError('Unsupported source manifest')
    for name, digest in hashes.items():
        path = root/name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink() or root.resolve() not in path.resolve().parents or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Unsafe source manifest')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Source hash mismatch: '+name)
    # Refuse additions that could silently change the image build context.
    for area in ('apps', 'packages'):
        for path in (root/area).rglob('*'):
            if path.is_symlink():
                raise ValueError('Build input symlink: '+str(path.relative_to(root)))
            if path.is_file() and str(path.relative_to(root)) not in hashes:
                raise ValueError('Unmanifested build input: '+str(path.relative_to(root)))
    actual = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if actual != manifest['source_sha256'] or not manifest['release_tag'].endswith('-'+actual[:16]):
        raise ValueError('Source manifest digest mismatch')
    return manifest


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument('--release-tag', action='store_true', help='print only the verified non-secret release tag')
    args = p.parse_args()
    try:
        manifest = verify(args.root.resolve())
    except (OSError, KeyError, TypeError, ValueError) as exc:
        p.exit(1, f'Source verification failed: {exc}\n')
    print(manifest['release_tag'] if args.release_tag else f"Source verified: {len(manifest['files'])} files, {manifest['release_tag']}")
