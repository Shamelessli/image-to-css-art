import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gui import resolve_output_names


class OutputNameTests(unittest.TestCase):
    def test_unique_stems(self):
        self.assertEqual(resolve_output_names([Path("a.jpg")]), ["a.html"])

    def test_same_stem_different_suffix(self):
        names = resolve_output_names([Path("a.jpg"), Path("a.png")])
        self.assertEqual(names, ["a.html", "a.png.html"])

    def test_stem_with_dots(self):
        self.assertEqual(resolve_output_names([Path("photo.v1.png")]), ["photo.v1.html"])

    def test_leading_space_kept(self):
        self.assertEqual(resolve_output_names([Path(" (1).jpg")]), [" (1).html"])


if __name__ == "__main__":
    unittest.main()