
import unittest

from groupctl.integration import validate_published_commit
from unittest.mock import patch
from subprocess import CompletedProcess
from groupctl.integration import check_integration_target
from groupctl.integration import preview_integration
from groupctl.integration import begin_integration
class TestIntegration(unittest.TestCase):

    def test_missing_commit(self):
        """Reject an event without a commit."""

        event = {
            "branch": "people/P17/setup"
        }

        with self.assertRaises(ValueError):
            validate_published_commit(event)

    def test_invalid_commit(self):
        """Reject a commit that does not exist."""

        event = {
            "branch": "people/P17/setup",
            "commit": "0" * 40
        }

        with self.assertRaises(ValueError):
            validate_published_commit(event)

    @patch("groupctl.integration.subprocess.run")
    def test_reject_main_branch(self, mock_run):
        """INT must reject the main branch."""

        mock_run.return_value = CompletedProcess(
            args=[],
            returncode=0,
            stdout="main\n",
            stderr=""
        )

        with self.assertRaises(ValueError):
            check_integration_target()
    
    @patch("groupctl.integration.subprocess.run")
    def test_reject_uncommitted_changes(self, mock_run):
        """INT must reject uncommitted changes."""

        mock_run.side_effect = [
            CompletedProcess(
                args=[],
                returncode=0,
                stdout="people/P22/int-command\n",
                stderr=""
            ),
            CompletedProcess(
                args=[],
                returncode=0,
                stdout=" M groupctl/integration.py\n",
                stderr=""
            )
        ]

        with self.assertRaises(ValueError):
            check_integration_target()
    
    @patch("groupctl.integration.subprocess.run")
    @patch(
        "groupctl.integration.validate_published_commit",
        return_value="abc123"
    )
    def test_preview_detects_conflict(
        self, mock_validate, mock_run
    ):
        """Detect a Git merge conflict."""

        mock_run.return_value = CompletedProcess(
            args=[],
            returncode=1,
            stdout="CONFLICT in groupctl/cli.py",
            stderr=""
        )

        event = {"commit": "abc123"}

        result = preview_integration(event)

        self.assertFalse(result["can_merge"])
        self.assertIn("CONFLICT", result["details"])

    @patch("groupctl.integration.subprocess.run")
    @patch("groupctl.integration.preview_integration")
    @patch("groupctl.integration.check_integration_target")
    def test_begin_integration_blocks_conflict(
        self, mock_target, mock_preview, mock_run
    ):
        """Do not merge when preview detects conflicts."""

        mock_target.return_value = "people/P22/int-command"

        mock_preview.return_value = {
            "can_merge": False,
            "details": "CONFLICT in groupctl/cli.py"
        }

        event = {"event_type": "change_published"}

        result = begin_integration(event)

        self.assertEqual(result["status"], "conflict")
        mock_run.assert_not_called()
    
    @patch("groupctl.integration.subprocess.run")
    @patch("groupctl.integration.preview_integration")
    @patch("groupctl.integration.check_integration_target")
    def test_begin_integration_success(
        self, mock_target, mock_preview, mock_run
    ):
        """Test a successful integration without changing files."""

        mock_target.return_value = "people/P22/int-command"

        mock_preview.return_value = {
            "can_merge": True,
            "commit": "abc123",
            "details": "Merge preview successful"
        }

        mock_run.return_value = CompletedProcess(
            args=[],
            returncode=0,
            stdout="Automatic merge went well",
            stderr=""
        )

        event = {"event_type": "change_published"}

        result = begin_integration(event)

        self.assertEqual(
            result["status"], "pending_verification"
        )
        self.assertEqual(result["commit"], "abc123")
        self.assertEqual(
            result["target_branch"],
            "people/P22/int-command"
        )

        mock_run.assert_called_once_with(
            [
                "git", "merge", "--no-ff",
                "--no-commit", "abc123"
            ],
            capture_output=True,
            text=True
        )



if __name__ == "__main__":
    unittest.main()


