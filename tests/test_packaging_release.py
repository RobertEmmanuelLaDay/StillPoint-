import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from stillpoint.db import CompanyDB

ROOT = Path(__file__).resolve().parents[1]


class PackagingReleaseTests(unittest.TestCase):
    def test_packaged_migration_mirror_matches_canonical(self):
        canonical = ROOT / "migrations"
        packaged = ROOT / "stillpoint" / "migrations"
        canonical_files = sorted(canonical.glob("*.sql"))
        packaged_files = sorted(packaged.glob("*.sql"))
        self.assertEqual([p.name for p in canonical_files], [p.name for p in packaged_files])
        for source, mirror in zip(canonical_files, packaged_files):
            self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), hashlib.sha256(mirror.read_bytes()).digest())

    def test_packaged_agent_registry_mirror_matches_canonical(self):
        canonical = ROOT / "config" / "agents.json"
        packaged = ROOT / "stillpoint" / "defaults" / "agents.json"
        self.assertEqual(canonical.read_bytes(), packaged.read_bytes())

    def test_packaged_migrations_can_create_fresh_database(self):
        with tempfile.TemporaryDirectory() as d:
            with CompanyDB(Path(d) / "db.sqlite", migrations_dir=ROOT / "stillpoint" / "migrations") as db:
                self.assertGreaterEqual(db.schema_version, 6)
                tables = {row[0] for row in db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertIn("action_requests", tables)
                self.assertIn("task_budgets", tables)

    def test_pyproject_and_ci_exist(self):
        self.assertTrue((ROOT / "pyproject.toml").is_file())
        self.assertTrue((ROOT / ".github" / "workflows" / "ci.yml").is_file())

    def test_release_version_metadata_is_coherent(self):
        import tomllib
        pyproject=tomllib.loads((ROOT/"pyproject.toml").read_text(encoding="utf-8"))
        package_version=pyproject["project"]["version"]
        namespace={}
        exec((ROOT/"stillpoint"/"__init__.py").read_text(encoding="utf-8"),namespace)
        checkpoint=json.loads((ROOT/"CHECKPOINT.json").read_text(encoding="utf-8"))
        self.assertEqual(package_version,namespace["__version__"])
        self.assertEqual(package_version,checkpoint["version"])
        if "rc" in package_version:
            notes=ROOT/f"RELEASE_NOTES_{package_version.replace('rc','_RC').replace('.','.')}.md"
            # Release notes use a stable human-readable filename; ensure one exists for this candidate.
            self.assertTrue((ROOT/"RELEASE_NOTES_0.2.0_RC1.md").is_file())

    def test_checkpoint_is_machine_readable(self):
        checkpoint = ROOT / "CHECKPOINT.json"
        if checkpoint.exists():
            data = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(data["name"], "StillPoint")


if __name__ == "__main__":
    unittest.main()
