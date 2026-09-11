import sqlite3
import tempfile
import unittest
from pathlib import Path

from stillpoint.db import CompanyDB

ROOT=Path(__file__).resolve().parents[1]


def schema_signature(conn):
    rows=conn.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
    # migration ledger contents differ by timestamp, schema should not.
    return [(r[0],r[1],r[2]) for r in rows]

class MigrationUpgradeTests(unittest.TestCase):
    def test_v2_upgrade_reaches_same_schema_as_fresh(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);legacy=tmp/'legacy.sqlite';fresh=tmp/'fresh.sqlite'
            c=sqlite3.connect(legacy)
            # Apply v1/v2 exactly as historical migration files and record versions.
            c.executescript((ROOT/'migrations'/'001_baseline_v5.sql').read_text());c.execute("INSERT INTO schema_migrations VALUES(1,'old')")
            c.executescript((ROOT/'migrations'/'002_packet2_artifacts.sql').read_text());c.execute("INSERT INTO schema_migrations VALUES(2,'old')");c.commit();c.close()
            old=CompanyDB(legacy);new=CompanyDB(fresh)
            self.assertEqual(old.schema_version,new.schema_version)
            self.assertEqual(schema_signature(old.conn),schema_signature(new.conn))
            old.close();new.close()

if __name__=='__main__':unittest.main()
