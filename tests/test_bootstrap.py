import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from groupctl import cli


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        result = subprocess.run(["git", "init", "-b", "main"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def tearDown(self):
        self.temp.cleanup()

    def run_in_repo(self, command):
        with patch.object(cli, "repository_root", return_value=self.root):
            return cli.main(command)

    def test_init_creates_required_layout_and_envelope_fields(self):
        rc = self.run_in_repo(["init", "--group-id", "G-12", "--person-id", "P17", "--name", "Test Student"])
        self.assertEqual(rc, 0)
        group = self.root / ".group"
        config = json.loads((group / "group.json").read_text())
        self.assertEqual(config, {
            "protocol_version": "0.1",
            "group_id": "G-12",
            "canonical_branch": "main",
            "assignment_file": ".group/assignment/assignment.md",
        })
        member = json.loads((group / "members" / "P17.json").read_text())
        self.assertEqual(member["person_id"], "P17")
        self.assertEqual(member["protocol_version"], "0.1")
        self.assertTrue(member["joined_at"].endswith("Z"))
        self.assertTrue((group / "assignment" / "assignment.md").exists())
        self.assertTrue((group / "events" / ".gitkeep").exists())
        self.assertTrue((group / "final" / ".gitkeep").exists())
        self.assertTrue((group / "local" / "identity.json").exists())

    def test_refuses_to_overwrite_existing_group(self):
        command = ["init", "--group-id", "G-12", "--person-id", "P17", "--name", "Test Student"]
        self.assertEqual(self.run_in_repo(command), 0)
        self.assertEqual(self.run_in_repo(command), 1)

    def test_rejects_path_traversal_in_person_id(self):
        command = ["init", "--group-id", "G-12", "--person-id", "../other", "--name", "Bad"]
        self.assertEqual(self.run_in_repo(command), 1)
        self.assertFalse((self.root / ".group").exists())

    def test_join_new_person_with_existing_config(self):
        self.assertEqual(self.run_in_repo(["init", "--group-id", "G-12", "--person-id", "P17", "--name", "A"]), 0)
        # A second clone would not contain the first person's ignored identity.
        (self.root / ".group" / "local" / "identity.json").unlink()
        self.assertEqual(self.run_in_repo(["join", "--person-id", "P22", "--name", "B"]), 0)
        self.assertTrue((self.root / ".group" / "members" / "P22.json").exists())

    def test_status_before_first_commit_is_safe(self):
        self.assertEqual(self.run_in_repo(["init", "--group-id", "G-12", "--person-id", "P17", "--name", "A"]), 0)
        self.assertEqual(self.run_in_repo(["status"]), 0)


if __name__ == "__main__":
    unittest.main()
