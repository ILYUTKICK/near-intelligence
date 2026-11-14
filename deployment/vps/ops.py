#!/usr/bin/env python3
"""Explicit VPS operations. No ingestion, automatic migration or volume deletion."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile

from env import ValidationError, compose_environment, validate_compose, validate_env_file

ARTIFACTS = '/var/lib/near-intelligence/artifacts'
DUMP = ['exec', '-T', 'db', '/bin/sh', '-ec', 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom']
RESTORE = ['exec', '-T', 'db', '/bin/sh', '-ec', 'exec pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --role=near_migrator --exit-on-error']
PACK = "import sys,tarfile; t=tarfile.open(fileobj=sys.stdout.buffer,mode='w|'); t.add('/var/lib/near-intelligence/artifacts',arcname='artifacts'); t.close()"
UNPACK = "import sys,tarfile; t=tarfile.open(fileobj=sys.stdin.buffer,mode='r|'); t.extractall('/var/lib/near-intelligence',filter='data'); t.close()"
SCHEMA_CHECK = """import os
from sqlalchemy import create_engine,text
from alembic.config import Config
from alembic.script import ScriptDirectory
expected=set(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())
with create_engine(os.environ['MIGRATION_DATABASE_URL']).connect() as c:
 actual=set(c.execute(text('select version_num from app.alembic_version')).scalars())
 if actual != expected: raise SystemExit('Migration revision mismatch')
print('Database connectivity, runtime grant and migration revision: OK')
"""


def accepted(root: Path) -> bool:
    tasks = (root/'docs/TASKS.md').read_text()
    card = tasks.split('### NI-079 —', 1)[1].split('\n### ', 1)[0]
    return bool(re.search(r'^- \*\*Status:\*\* DONE\s*$', card, re.M))


def safe_backup(path: Path) -> dict:
    if path.is_symlink():
        raise ValueError('Backup directory must not be a symlink')
    metadata = json.loads((path/'backup.json').read_text())
    if metadata.get('format') != 1 or set(metadata.get('files', {})) != {'database.dump', 'artifacts.tar'}:
        raise ValueError('Unknown backup format')
    for name, digest in metadata['files'].items():
        p = path/name
        if p.is_symlink() or not p.is_file() or sha256(p) != digest:
            raise ValueError('Backup file missing or hash mismatch: '+name)
    with tarfile.open(path/'artifacts.tar') as archive:
        for member in archive:
            parts = Path(member.name).parts
            if not parts or parts[0] != 'artifacts' or '..' in parts or Path(member.name).is_absolute() or not (member.isfile() or member.isdir()):
                raise ValueError('Unsafe artifact backup member')
    return metadata


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


class Operator:
    def __init__(self, root: Path, env_file: Path, project: str, rehearsal: bool):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,60}', project):
            raise ValueError('Invalid Compose project name')
        if rehearsal and not project.startswith('near-vps-rehearsal-'):
            raise ValueError('Rehearsal requires a separate near-vps-rehearsal-* project')
        self.root, self.project, self.rehearsal = root, project, rehearsal
        self.values = validate_env_file(env_file)
        self.environment = compose_environment(self.values)
        self.base = ['docker', 'compose', '--project-name', project, '--env-file', str(env_file), '-f', str(root/'deployment/vps/compose.yaml')]
        result = self.run(['--profile', 'migrate', '--profile', 'worker', 'config', '--format', 'json'])
        validate_compose(json.loads(result.stdout), self.values)
        # Stable across candidate/env directories for this host operator user.
        lock_dir = Path('/tmp') / f'near-intelligence-vps-{os.getuid()}'
        lock_dir.mkdir(mode=0o700, exist_ok=True)
        info = lock_dir.lstat()
        if lock_dir.is_symlink() or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('Unsafe shared operator lock directory')
        self.lock = lock_dir / f'{project}.lock'

    def run(self, args, *, stdout=subprocess.PIPE, stdin=None):
        result = subprocess.run(self.base+args, env=self.environment, stdin=stdin, stdout=stdout, stderr=subprocess.PIPE)
        if result.returncode:
            # Never echo resolved config, exception DSNs or raw provider responses.
            raise RuntimeError('Docker operation failed; inspect restricted service logs on the host')
        return result

    def gate(self):
        if not self.rehearsal and not accepted(self.root):
            raise ValueError('NI-079 is not DONE for this candidate; remote rollout remains gated')

    @contextmanager
    def exclusive(self):
        fd = os.open(self.lock, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def worker(self, sweep=False):
        self.gate()
        if sweep:
            command = 'exec .venv/bin/python -m near_api.exports.worker --database-url "$DATABASE_URL" --operator-database-url "$OPERATOR_DATABASE_URL" --sweep'
            self.run(['run', '--rm', '-T', '--no-deps', 'worker', '/bin/sh', '-ec', command])
        else:
            self.run(['run', '--rm', '-T', '--no-deps', 'worker'])

    def check(self):
        self.run(['exec', '-T', 'db', 'pg_isready', '-U', 'near_bootstrap', '-d', 'near_intelligence'])
        self.run(['exec', '-T', 'api', '.venv/bin/python', '-c', "import os; from sqlalchemy import create_engine,text; c=create_engine(os.environ['DATABASE_URL']).connect(); assert c.execute(text('select current_user')).scalar()=='near_app'; c.execute(text('select count(*) from app.dataset_versions')); c.close()"])
        self.run(['run', '--rm', '-T', '--no-deps', '--entrypoint', '.venv/bin/python', 'migrate', '-c', SCHEMA_CHECK])
        self.run(['exec', '-T', 'api', '.venv/bin/python', '-c', f"import os; assert os.path.isdir('{ARTIFACTS}'); assert os.access('{ARTIFACTS}',os.R_OK)"])
        self.run(['run', '--rm', '-T', '--no-deps', '--entrypoint', '.venv/bin/python', 'worker', '-c', f"import tempfile,os; p=tempfile.NamedTemporaryFile(dir='{ARTIFACTS}',delete=False); p.write(b'readiness'); p.close(); assert open(p.name,'rb').read()==b'readiness'; os.unlink(p.name)"])
        self.run(['exec', '-T', 'web', 'node', '-e', "Promise.all(['/health','/','/blog','/research','/illustrations/overview-research-desk.png'].map(async p=>{let r=await fetch('http://127.0.0.1:3000'+p);if(!r.ok)throw Error(p)})).catch(()=>process.exit(1))"])
        print('DB/schema/artifact permissions and internal web routes: OK. Final TLS/auth/data flows still need release acceptance.')

    def backup(self, destination: Path):
        # All deployed writers must use this operator lock. No refresh is scheduled.
        active = subprocess.run(['docker', 'ps', '--filter', f'label=com.docker.compose.project={self.project}', '--format', '{{.Label \"com.docker.compose.service\"}}'], env=self.environment, capture_output=True, text=True, check=True).stdout.split()
        if any(service in {'worker', 'migrate'} for service in active):
            raise ValueError('A one-shot writer is still running; stop timers and wait before backup')
        destination.mkdir(mode=0o700, parents=True, exist_ok=False)
        os.chmod(destination, 0o700)
        running = self.run(['ps', '--services', '--status', 'running']).stdout.decode().split()
        writers = [s for s in ('api', 'web') if s in running]
        if 'db' not in running:
            raise ValueError('Database is not running')
        try:
            if writers:
                self.run(['stop', *writers])
            with (destination/'database.dump').open('xb') as out:
                self.run(DUMP, stdout=out)
            with (destination/'artifacts.tar').open('xb') as out:
                self.run(['run', '--rm', '-T', '--no-deps', '--entrypoint', '.venv/bin/python', 'worker', '-c', PACK], stdout=out)
            metadata = {'format': 1, 'created_at': datetime.now(timezone.utc).isoformat(), 'release_tag': self.values['RELEASE_TAG'], 'project': self.project, 'files': {n: sha256(destination/n) for n in ('database.dump', 'artifacts.tar')}}
            (destination/'backup.json').write_text(json.dumps(metadata, indent=2)+'\n')
            safe_backup(destination)
        finally:
            if writers:
                self.run(['start', *writers])
        print('Coherent private backup written and hashed: '+str(destination))

    def restore(self, source: Path):
        # Deliberately no in-place production restore / no down -v anywhere.
        if not self.rehearsal:
            raise ValueError('Restore only supports a new isolated rehearsal project; cutover needs a reviewed recovery plan')
        safe_backup(source)
        for suffix in ('near_db_data', 'near_artifacts', 'caddy_data', 'caddy_config'):
            found = subprocess.run(['docker', 'volume', 'inspect', f'{self.project}_{suffix}'], env=self.environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if found.returncode == 0:
                raise ValueError('Restore refuses an existing target volume')
        self.run(['up', '-d', '--wait', 'db'])
        with (source/'database.dump').open('rb') as data:
            self.run(RESTORE, stdin=data)
        with (source/'artifacts.tar').open('rb') as data:
            self.run(['run', '--rm', '-T', '--no-deps', '--entrypoint', '.venv/bin/python', 'worker', '-c', UNPACK], stdin=data)
        print('Backup restored into isolated project. Run api/web, check schema and compare evidence before any cutover.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument('--env-file', type=Path)
    p.add_argument('--project', default='near-intelligence-vps')
    p.add_argument('--rehearsal', action='store_true', help='Only for a separate local disposable project; never enables TLS proxy')
    sub = p.add_subparsers(dest='command', required=True)
    for name in ('validate', 'build', 'db', 'migrate', 'up', 'status', 'check', 'worker', 'sweep'):
        sub.add_parser(name)
    sub.add_parser('backup').add_argument('directory', type=Path)
    sub.add_parser('restore').add_argument('directory', type=Path)
    rollback = sub.add_parser('rollback')
    rollback.add_argument('--tag', required=True)
    rollback.add_argument('--schema-compatible', action='store_true', required=True)
    args = p.parse_args()
    os.umask(0o077)
    root = args.root.resolve()
    try:
        op = Operator(root, (args.env_file or root/'.env.vps').absolute(), args.project, args.rehearsal)
        with op.exclusive():
            if args.command == 'validate':
                print('Environment and service isolation: OK')
            elif args.command == 'build':
                from verify_source import verify
                manifest = verify(root)
                if manifest['release_tag'] != op.values['RELEASE_TAG']:
                    raise ValueError('Environment release tag differs from the verified source')
                op.run(['build', 'api', 'web'])
            elif args.command == 'status':
                # Config/status never display credentials.
                print(op.run(['ps', '--format', 'table']).stdout.decode())
            elif args.command == 'check':
                op.check()
            elif args.command == 'backup':
                op.backup(args.directory.resolve())
            elif args.command == 'restore':
                op.restore(args.directory.resolve())
            elif args.command in ('worker', 'sweep'):
                op.worker(args.command == 'sweep')
            elif args.command == 'rollback':
                op.gate()
                if not re.fullmatch(r'\d{8}T\d{6}Z-[0-9a-f]{12,64}', args.tag):
                    raise ValueError('Invalid rollback release tag')
                # Override only the images, never migrations/data pointers.
                op.environment['RELEASE_TAG'] = args.tag
                op.run(['up', '-d', '--no-deps', '--no-build', '--wait', 'api', 'web'])
                print('Prior images started. Update the private env release tag after verified smoke checks before enabling timers.')
            else:
                op.gate()
                commands = {'db': ['up', '-d', '--wait', 'db'], 'migrate': ['run', '--rm', '-T', 'migrate'], 'up': ['up', '-d', '--no-build', '--wait', 'db', 'api', 'web'] + ([] if args.rehearsal else ['proxy'])}
                op.run(commands[args.command])
        return 0
    except (ValidationError, ValueError, RuntimeError, OSError, subprocess.SubprocessError, KeyError, IndexError, json.JSONDecodeError) as exc:
        # Exception text from validation is key names only. Never print subprocess stderr.
        p.exit(1, f'Operation refused: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
