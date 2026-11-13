
import unittest

from groupctl.integration import validate_published_commit


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


if __name__ == "__main__":
    unittest.main()
