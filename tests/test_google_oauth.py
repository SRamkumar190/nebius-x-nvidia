import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.google_oauth import REPO_ROOT, SCOPES, validate_client_secrets, validate_token_payload, write_token


def synthetic_token():
    return {
        "token": "synthetic-access-token",
        "refresh_token": "synthetic-refresh-token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "synthetic-client-id",
        "client_secret": "synthetic-client-secret",
        "scopes": list(SCOPES),
    }


class GoogleAuthorizationTest(unittest.TestCase):
    def test_requires_desktop_client_and_exact_runtime_scopes(self):
        with tempfile.TemporaryDirectory() as directory:
            client = Path(directory) / "client.json"
            client.write_text(json.dumps({"web": {"client_id": "x", "client_secret": "y"}}))
            with self.assertRaisesRegex(ValueError, "Desktop app"):
                validate_client_secrets(client)
            client.write_text(json.dumps({"installed": {"client_id": "x", "client_secret": "y"}}))
            validate_client_secrets(client)
        validate_token_payload(synthetic_token())
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            validate_client_secrets(REPO_ROOT / "secrets" / "desktop-client.json")
        for extra in ("https://www.googleapis.com/auth/gmail.send",
                      "https://www.googleapis.com/auth/gmail.insert"):
            token = synthetic_token()
            token["scopes"].append(extra)
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, "scopes"):
                validate_token_payload(token)
        token = synthetic_token()
        token.pop("refresh_token")
        with self.assertRaisesRegex(ValueError, "refresh_token"):
            validate_token_payload(token)

    def test_private_output_does_not_overwrite_or_enter_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "google-token.json"
            serialized = json.dumps(synthetic_token())
            write_token(path, serialized)
            self.assertEqual(json.loads(path.read_text()), synthetic_token())
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                write_token(path, serialized)
            self.assertEqual(json.loads(path.read_text()), synthetic_token())
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            write_token(REPO_ROOT / "secrets" / "google-token.json", json.dumps(synthetic_token()))

    def test_validator_cli_rejects_missing_refresh_token_without_echoing_token(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "token.json"
            token = synthetic_token()
            token.pop("refresh_token")
            path.write_text(json.dumps(token))
            script = REPO_ROOT / "scripts" / "validate_google_token.py"
            result = subprocess.run([sys.executable, str(script), str(path)],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn(token["token"], result.stdout + result.stderr)
            self.assertIn("refresh_token", result.stderr)

    def test_installer_stages_private_copy_and_preserves_other_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            token_path = root / "token.json"
            token_path.write_text(json.dumps(synthetic_token()))
            binary = root / "bin"
            binary.mkdir()
            log = root / "calls.jsonl"
            fake = binary / "nemohermes"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, stat, sys\n"
                "from pathlib import Path\n"
                "args = sys.argv[1:]\n"
                "if args[1] == 'upload':\n"
                "    source = Path(args[2])\n"
                "    assert stat.S_IMODE(source.stat().st_mode) == 0o600\n"
                "    assert json.loads(source.read_text()) == json.loads(Path(os.environ['FAKE_TOKEN']).read_text())\n"
                "with Path(os.environ['FAKE_LOG']).open('a') as output:\n"
                "    output.write(json.dumps(args) + '\\n')\n"
            )
            fake.chmod(0o700)
            env = {**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"],
                   "FAKE_LOG": str(log), "FAKE_TOKEN": str(token_path)}
            installer = REPO_ROOT / "agent" / "openshell" / "install-google-token.sh"
            result = subprocess.run(["bash", str(installer), str(token_path), "keeper"],
                                    env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("synthetic-refresh-token", result.stdout + result.stderr)
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertTrue(any(call[1:3] == ["exec", "--"] and "chmod" in call for call in calls))
            self.assertTrue(any(call[1] == "upload" for call in calls))
            self.assertFalse(any("rm" in call for call in calls))


if __name__ == "__main__":
    unittest.main()
