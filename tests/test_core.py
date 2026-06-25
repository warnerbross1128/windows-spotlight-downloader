from pathlib import Path
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
