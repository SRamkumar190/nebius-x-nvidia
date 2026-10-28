"""Runtime-token checks run offline and never print token content."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from triage.credentials import gmail_from_token, ROOT, SCOPES


class RuntimeTokenTest(unittest.TestCase):
    def test_valid_private_token_reuses_existing_gmail_constructor(self):
        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / "runtime.json"
            token.write_text(json.dumps(self.token()))
            token.chmod(0o600)
            with patch("triage.credentials.LiveGmail.from_token_file", return_value="adapter") as builder:
                self.assertEqual(gmail_from_token(token, run_id="triage"), "adapter")
            builder.assert_called_once_with(token, run_id="triage")

    @staticmethod
    def token():
        return {
            "refresh_token": "synthetic", "client_id": "synthetic", "client_secret": "synthetic",
            "token_uri": "https://oauth2.googleapis.com/token", "scopes": list(SCOPES),
        }

    @unittest.skipIf(os.name == "nt", "POSIX file modes; Gmail mode runs on WSL or Linux")
    def test_rejects_broad_permissions_and_credentials_inside_checkout(self):
        with self.assertRaises(ValueError):
            gmail_from_token(ROOT / "secrets/google-token.json", run_id="test")
        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / "runtime.json"
            token.write_text(json.dumps(self.token()))
            token.chmod(0o644)
            with self.assertRaises(ValueError):
                gmail_from_token(token, run_id="test")
            token.chmod(0o600)
            token.parent.chmod(0o755)
            with self.assertRaises(ValueError):
                gmail_from_token(token, run_id="test")

    def test_rejects_missing_fields_scopes_and_untrusted_refresh_endpoint(self):
        invalid = [
            [], {**self.token(), "refresh_token": ""},
            {**self.token(), "token_uri": "https://evil.example/steal"},
            {**self.token(), "scopes": ["https://www.googleapis.com/auth/gmail.insert"]},
            {**self.token(), "scopes": [None]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / "runtime.json"
            for data in invalid:
                token.write_text(json.dumps(data))
                token.chmod(0o600)
                with self.subTest(data=data), patch("triage.credentials.LiveGmail.from_token_file") as builder:
                    with self.assertRaises(ValueError):
                        gmail_from_token(token, run_id="test")
                    builder.assert_not_called()

    @unittest.skipIf(os.name == "nt", "symlinks need admin rights on Windows")
    def test_rejects_symlink_or_oversized_credential(self):
        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / "runtime.json"
            token.write_text("x" * 64001)
            token.chmod(0o600)
            with self.assertRaises(ValueError):
                gmail_from_token(token, run_id="test")
            link = Path(directory) / "link.json"
            link.symlink_to(token)
            with self.assertRaises(ValueError):
                gmail_from_token(link, run_id="test")
