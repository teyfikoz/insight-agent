import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from dashboard import server


class DistributionTests(unittest.TestCase):
    def test_settings_are_write_only_and_blanks_preserve_keys(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server, "ROOT", Path(directory)):
            env = Path(directory) / ".env"
            env.write_text("GROQ_API_KEY=synthetic-test-value\nDEFAULT_REPORT=full\n")
            with patch.dict(server.os.environ, {}, clear=True), TestClient(server.app) as client:
                response = client.get("/api/settings")
                self.assertNotIn("synthetic-test-value", response.text)
                self.assertTrue(response.json()["configured"]["GROQ_API_KEY"])
                self.assertEqual(client.post("/api/settings", json={"GROQ_API_KEY": ""}).status_code, 200)
                self.assertIn("synthetic-test-value", env.read_text())
                self.assertEqual(env.stat().st_mode & 0o777, 0o600)
                self.assertEqual(client.post("/api/settings", json={"PATH": "bad"}).status_code, 400)
                self.assertEqual(client.post("/api/settings", json={"GROQ_API_KEY": "value\nOTHER=bad"}).status_code, 400)

    def test_dashboard_supports_proxy_prefix(self):
        with TestClient(server.app) as client:
            response = client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertIn("/insight-agent/", response.text)
            self.assertIn("X-Command-Center-CSRF", response.text)


if __name__ == "__main__":
    unittest.main()
