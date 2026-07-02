from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

import spotlight_downloader as app


class CoreHelpersTest(unittest.TestCase):
    def test_normalize_original_url_removes_wordpress_size_suffix(self):
        url = "https://windows10spotlight.com/wp-content/uploads/2026/01/example-1024x576.jpg?x=1"

        self.assertEqual(
            app.normalize_original_url(url),
            "https://windows10spotlight.com/wp-content/uploads/2026/01/example.jpg",
        )

    def test_version_parts_compare_semver_like_tags(self):
        self.assertGreater(app.version_parts("v1.0.0"), app.version_parts("0.3.0"))
        self.assertEqual(app.version_parts("0.3"), (0, 3, 0))

    def test_target_path_uses_date_title_and_portrait_suffix(self):
        item = {
            "date": "June 25, 2026",
            "title": "Maligne Lake / Alberta",
            "orientation": "portrait",
            "finalUrl": f"{app.BASE_URL}/wp-content/uploads/2026/06/maligne.jpg",
        }

        target = app.target_path_for_item(item, Path("Library"))

        self.assertEqual(target.name, "June-25-2026-Maligne-Lake-Alberta-portrait.jpg")

    def test_library_match_detects_numbered_variants(self):
        item = {
            "date": "June 25, 2026",
            "title": "Maligne Lake",
            "orientation": "landscape",
            "finalUrl": f"{app.BASE_URL}/wp-content/uploads/2026/06/maligne.jpg",
        }

        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp)
            (library / "June-25-2026-Maligne-Lake-2.jpg").write_bytes(b"image")

            self.assertEqual(
                app.library_match_for_item(item, library),
                library / "June-25-2026-Maligne-Lake-2.jpg",
            )

    def test_load_config_defaults_to_english(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "missing-config.json"

            with patch.object(app, "CONFIG_PATH", config_path):
                config = app.load_config()

            self.assertEqual(config["language"], "en")

    def test_save_config_persists_supported_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            library = Path(tmp) / "Library"

            with patch.object(app, "CONFIG_PATH", config_path):
                config = app.save_config({"libraryDir": str(library), "language": "fr"})

            self.assertEqual(config["language"], "fr")

    def test_save_config_falls_back_to_english_for_unknown_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            library = Path(tmp) / "Library"

            with patch.object(app, "CONFIG_PATH", config_path):
                config = app.save_config({"libraryDir": str(library), "language": "de"})

            self.assertEqual(config["language"], "en")

    def test_save_config_empty_library_error_uses_requested_language(self):
        with self.assertRaisesRegex(ValueError, "library folder is empty"):
            app.save_config({"libraryDir": "", "language": "en"})

        with self.assertRaisesRegex(ValueError, "bibliothèque est vide"):
            app.save_config({"libraryDir": "", "language": "fr"})

    def test_user_error_can_be_returned_in_english_or_french(self):
        error = urllib.error.HTTPError("https://example.com", 503, "Unavailable", {}, None)

        self.assertIn("source website returned HTTP error 503", app.user_error(error, "scan", "en"))
        self.assertIn("site source a répondu avec une erreur HTTP 503", app.user_error(error, "scan", "fr"))

    def test_runtime_translation_uses_config_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            library = Path(tmp) / "Library"

            with patch.object(app, "CONFIG_PATH", config_path):
                app.save_config({"libraryDir": str(library), "language": "fr"})
                self.assertEqual(app.tr("errors.image_url_refused"), "URL refusée")


if __name__ == "__main__":
    unittest.main()
