from __future__ import annotations

import unittest

import app.main as main_module


class HealthTest(unittest.TestCase):
    def test_health_keys(self) -> None:
        h = main_module.health()
        self.assertIsInstance(h, dict)
        self.assertEqual(h.get("status"), "ok")
        self.assertEqual(h.get("service"), "backend")
        self.assertIn("data_dir", h)
        self.assertIn("storage_dirs", h)
        self.assertIn("pdfs", h["storage_dirs"])
        self.assertIn("epubs", h["storage_dirs"])
        self.assertIn("thumbs", h["storage_dirs"])