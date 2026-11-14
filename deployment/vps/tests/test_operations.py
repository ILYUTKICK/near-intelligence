import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

VPS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(VPS))
import bundle
# env.py is staged by config handoff before running this suite.
import ops


class Boundaries(unittest.TestCase):
    def test_package_rejects_private_state_and_keeps_preregistered_configs(self):
        for name in ('.env', '.env.vps', 'apps/web/.env.local', 'deployment/vps/.env.vps', '.aws/credentials', 'research/near-dollar/raw.json', 'research/foo/analysis.py', 'research/raw.sql', 'output/backup.json', 'docker-compose.override.yml', 'deployment/vps/key.pem', '../x'):
            self.assertFalse(bundle.allowed(name),name)
        for name in ('apps/web/public/illustrations/overview-research-desk.png', 'research/models/configs/true_revenue_daily_v1.json', 'research/models/fit.py', 'research/near-dollar/FINDINGS.md', 'deployment/vps/.env.example'):
            self.assertTrue(bundle.allowed(name),name)

    def test_restore_checks_both_archives_and_forbids_links(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'database.dump').write_bytes(b'synthetic-test-only')
            for member_name, kind in [('artifacts/a.txt','file'), ('../escape','file'), ('artifacts/link','link')]:
                with tarfile.open(root/'artifacts.tar','w') as archive:
                    info=tarfile.TarInfo(member_name)
                    if kind=='link':
                        info.type=tarfile.SYMTYPE; info.linkname='/etc/passwd'
                        archive.addfile(info)
                    else:
                        info.size=1; archive.addfile(info,io.BytesIO(b'x'))
                metadata={'format':1,'files':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ('database.dump','artifacts.tar')}}
                (root/'backup.json').write_text(json.dumps(metadata))
                if member_name=='artifacts/a.txt':
                    ops.safe_backup(root)
                    (root/'database.dump').write_bytes(b'changed')
                    with self.assertRaisesRegex(ValueError,'hash mismatch'): ops.safe_backup(root)
                    (root/'database.dump').write_bytes(b'synthetic-test-only')
                else:
                    with self.assertRaisesRegex(ValueError,'Unsafe'): ops.safe_backup(root)

    def test_release_gate_is_card_specific(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'docs').mkdir()
            p=root/'docs/TASKS.md'
            p.write_text('### NI-078 — prior\n- **Status:** DONE\n### NI-079 — acceptance\n- **Status:** TODO\n### NI-080 — next\n- **Status:** DONE\n')
            self.assertFalse(ops.accepted(root))
            p.write_text(p.read_text().replace('**Status:** TODO','**Status:** DONE'))
            self.assertTrue(ops.accepted(root))

    def test_restore_refuses_in_place_before_docker(self):
        op=object.__new__(ops.Operator); op.rehearsal=False
        with patch('ops.subprocess.run') as run:
            with self.assertRaisesRegex(ValueError,'new isolated'): op.restore(Path('/unused'))
            run.assert_not_called()

class SourceIntegrity(unittest.TestCase):
    def test_untracked_private_handoff_file_is_never_collected(self):
        required=['Dockerfile.web','Dockerfile.api','pnpm-lock.yaml','apps/api/uv.lock','deployment/vps/compose.yaml','deployment/vps/env.py','deployment/vps/ops.py']
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name in required:
                p=root/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b'test-source')
            secret=root/'deployment/vps/private-state.json'; secret.write_bytes(b'private local state')
            with patch('bundle.subprocess.check_output',return_value=('\0'.join(required)+'\0').encode()):
                files=bundle.collect(root)
            self.assertNotIn('deployment/vps/private-state.json',files)
            (root/'apps/api/uv.lock').unlink()
            (root/'apps/api/uv.lock').symlink_to(secret)
            with patch('bundle.subprocess.check_output',return_value=('\0'.join(required)+'\0').encode()):
                with self.assertRaisesRegex(ValueError,'symlink'): bundle.collect(root)

    def test_source_manifest_rejects_changed_and_added_build_inputs(self):
        import verify_source
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'apps/web').mkdir(parents=True); (root/'packages').mkdir()
            code=root/'apps/web/index.ts'; code.write_text('original')
            hashes={'apps/web/index.ts':hashlib.sha256(code.read_bytes()).hexdigest()}
            digest=hashlib.sha256(json.dumps(hashes,sort_keys=True,separators=(',', ':')).encode()).hexdigest()
            manifest={'format':1,'files':hashes,'source_sha256':digest,'release_tag':'20261114T120000Z-'+digest[:16]}
            (root/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest))
            verify_source.verify(root)
            code.write_text('changed')
            with self.assertRaisesRegex(ValueError,'hash mismatch'): verify_source.verify(root)
            code.write_text('original'); (root/'apps/web/extra.ts').write_text('unmanifested')
            with self.assertRaisesRegex(ValueError,'Unmanifested'): verify_source.verify(root)


class BackupWriterGuard(unittest.TestCase):
    def test_orphan_one_shot_writer_refuses_snapshot(self):
        import subprocess
        op=object.__new__(ops.Operator);op.project='near-vps-rehearsal-test';op.environment={}
        with tempfile.TemporaryDirectory() as d:
            destination=Path(d)/'backup'
            with patch('ops.subprocess.run',return_value=subprocess.CompletedProcess([],0,stdout='db\nworker\n')):
                with self.assertRaisesRegex(ValueError,'one-shot writer'): op.backup(destination)
            self.assertFalse(destination.exists())


if __name__=='__main__': unittest.main()
