import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gui import build_convert_cmd, parse_dnd_data, resolve_output_names, scan_images, worker_tag


class BuildConvertCmdTests(unittest.TestCase):
    def test_script_mode_uses_venv_and_cli(self):
        cmd = build_convert_cmd(Path("a.png"), Path("a.html"), "faithful", frozen=False)
        self.assertTrue(str(cmd[0]).endswith("python.exe"))
        self.assertTrue(str(cmd[1]).endswith("image_to_css.py"))
        self.assertEqual(cmd[2:6], ["convert", "a.png", "-o", "a.html"])

    def test_frozen_mode_self_exec(self):
        cmd = build_convert_cmd(Path("a.png"), Path("a.html"), "preview", frozen=True)
        self.assertEqual(cmd[1:3], ["--convert-worker", "convert"])

    def test_force_always_present(self):
        for frozen in (False, True):
            cmd = build_convert_cmd(Path("a.png"), Path("a.html"), "faithful", frozen=frozen)
            self.assertIn("--force", cmd)

    def test_bg_and_fit_appended_only_when_nonempty(self):
        cmd = build_convert_cmd(Path("a.png"), Path("a.html"), "faithful", bg="#f00", fit="20", frozen=True)
        self.assertIn("--background", cmd)
        self.assertIn("#f00", cmd)
        self.assertIn("--fit", cmd)
        self.assertIn("20", cmd)
        cmd = build_convert_cmd(Path("a.png"), Path("a.html"), "faithful", frozen=True)
        self.assertNotIn("--background", cmd)
        self.assertNotIn("--fit", cmd)


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

    def test_three_same_basename_distinct_dirs_no_duplicates(self):
        names = resolve_output_names([Path("d1/a.jpg"), Path("d2/a.jpg"), Path("d3/a.jpg")])
        self.assertEqual(names, ["a.html", "a.jpg.html", "a.jpg-2.html"])
        self.assertEqual(len(names), len(set(names)))

    def test_many_conflicts_get_incremented_numbers(self):
        names = resolve_output_names([Path("d1/a.jpg"), Path("d2/a.jpg"), Path("d3/a.jpg"), Path("d4/a.jpg")])
        self.assertEqual(names, ["a.html", "a.jpg.html", "a.jpg-2.html", "a.jpg-3.html"])
        self.assertEqual(len(names), len(set(names)))


IMAGE_EXTS_TEST = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}


class ScanImagesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "a.png").write_bytes(b"x")
        (self.root / "b.JPG").write_bytes(b"x")
        (self.root / "c.txt").write_bytes(b"x")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "d.png").write_bytes(b"x")

    def tearDown(self):
        self.tmp.cleanup()

    def test_mixed_files_and_dir_top_level_only(self):
        result = scan_images([self.root / "a.png", self.root / "c.txt", self.root])
        self.assertEqual(result, [(self.root / "a.png").resolve(), (self.root / "b.JPG").resolve()])

    def test_dir_does_not_recurse(self):
        result = scan_images([self.root])
        self.assertNotIn((self.root / "sub" / "d.png").resolve(), result)

    def test_duplicates_removed(self):
        result = scan_images([self.root / "a.png", self.root / "a.png"])
        self.assertEqual(result, [(self.root / "a.png").resolve()])

    def test_case_insensitive_extensions(self):
        result = scan_images([self.root / "b.JPG"])
        self.assertEqual(result, [(self.root / "b.JPG").resolve()])


class ParseDndDataTests(unittest.TestCase):
    def test_simple_paths(self):
        self.assertEqual(parse_dnd_data("a.png b.jpg"), ["a.png", "b.jpg"])

    def test_braced_paths_with_spaces(self):
        self.assertEqual(parse_dnd_data(r"{my folder\a.png} {b.jpg}"), [r"my folder\a.png", "b.jpg"])

    def test_adjacent_braces(self):
        self.assertEqual(parse_dnd_data(r"{x y}{z}"), ["x y", "z"])

    def test_empty_items_skipped(self):
        self.assertEqual(parse_dnd_data("  a.png  "), ["a.png"])


class WorkerTagTests(unittest.TestCase):
    def test_format(self):
        self.assertEqual(worker_tag(1), "[W1]")
        self.assertEqual(worker_tag(12), "[W12]")


if __name__ == "__main__":
    unittest.main()