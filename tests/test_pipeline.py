import contextlib
import errno
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/image-to-css-art/scripts"))
from css_art.audit import audit_html
from css_art.cli import atomic_write, main
from css_art.geometry import bridge_rings
from css_art.regions import label_components, load_reference, merge_regions


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "中文路径 with spaces"
        self.root.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            result = main(list(map(str, args)))
        return result, output.getvalue(), error.getvalue()

    def convert(self, image, *extra):
        source, output = self.root / "参考.png", self.root / "插画.html"
        image.save(source)
        result, stdout, stderr = self.run_cli("convert", source, "-o", output, "--quiet", *extra)
        self.assertEqual(result, 0, stderr)
        document = output.read_text(encoding="utf-8")
        return document, json.loads(stdout)

    def test_white_and_single_pixel(self):
        for color in ("white", "red"):
            with self.subTest(color=color):
                document, report = self.convert(Image.new("RGB", (1, 1), color), "--force")
                self.assertTrue(audit_html(document)["valid"])
                self.assertEqual(report["original_size"], [1, 1])
                self.assertEqual(report["shapes"] == 0, color == "white")

    def test_transparent_matte_and_orientation(self):
        source = self.root / "透明.png"
        Image.new("RGBA", (10, 20), (255, 0, 0, 0)).save(source)
        reference, size = load_reference(source, 100, (24, 48, 64))
        self.assertEqual(size, (10, 20))
        np.testing.assert_array_equal(reference, np.full((20, 10, 3), (24, 48, 64), dtype=np.uint8))
        image = Image.new("RGB", (20, 10), "blue")
        exif = Image.Exif()
        exif[274] = 6
        source = self.root / "方向.jpg"
        image.save(source, exif=exif)
        _, size = load_reference(source, 100, (255, 255, 255))
        self.assertEqual(size, (10, 20))

    def test_tall_reference_is_bounded(self):
        source = self.root / "tall.png"
        Image.new("RGB", (10, 1000), "blue").save(source)
        reference, _ = load_reference(source, 100, (255, 255, 255))
        self.assertEqual(reference.shape[:2], (200, 2))

    def test_holes_survive_and_output_is_deterministic(self):
        image = Image.new("RGB", (96, 96), "white")
        draw = ImageDraw.Draw(image)
        draw.ellipse((8, 8, 88, 88), fill="#173d49")
        draw.ellipse((26, 26, 70, 70), fill="white")
        document, report = self.convert(image, "--colors", "16")
        self.assertGreater(report["interior_holes"], 0)
        self.assertIn("polygon(evenodd,", document)
        again, _ = self.convert(image, "--colors", "16", "--force")
        self.assertEqual(document, again)
        self.assertGreater(report["underpainting_shapes"], 0)

    def test_bridge_does_not_change_evenodd_filled_area(self):
        rings = [np.array([[0, 0], [10, 0], [10, 10], [0, 10]]),
                 np.array([[3, 3], [7, 3], [7, 7], [3, 7]]),
                 np.array([[12, 1], [14, 1], [14, 3], [12, 3]])]
        def inside(point, polygon):
            x, y = point
            result = False
            for a, b in zip(polygon, np.roll(polygon, -1, axis=0)):
                if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
                    result = not result
            return result
        joined = bridge_rings(rings)
        for y in np.arange(.25, 11, .5):
            for x in np.arange(.25, 15, .5):
                expected = sum(inside((x, y), ring) for ring in rings) % 2 == 1
                self.assertEqual(inside((x, y), joined), expected, (x, y))

    def test_gradients_and_safe_title(self):
        values = np.linspace(20, 230, 128).astype(np.uint8)
        array = np.empty((64, 128, 3), np.uint8)
        array[:] = np.stack((values, values, np.full(128, 170)), axis=1)
        title = '测试 <script>alert("x")</script> & CSS'
        document, report = self.convert(Image.fromarray(array), "--colors", "8", "--title", title)
        self.assertGreater(report["gradient_fills"], 0)
        self.assertNotIn("<script>", document)
        self.assertIn("&lt;script&gt;", document)
        self.assertTrue(report["audit"]["valid"])

    def test_distant_detail_is_not_merged(self):
        labels = np.zeros((12, 12), np.uint8)
        labels[5, 5] = 1
        palette = np.array([[230, 210, 190], [10, 30, 40]], np.uint8)
        result = merge_regions(labels, palette)
        self.assertEqual(result[5, 5], 1)

    def test_component_labeling_matches_per_color_reference(self):
        rng = np.random.default_rng(11)
        for trial in range(40):
            height = int(rng.integers(1, 14))
            width = int(rng.integers(1, 14))
            count = int(rng.integers(1, 6))
            labels = rng.integers(0, count, (height, width), dtype=np.uint8)
            ids, colors, areas = label_components(labels)
            expected_ids = np.zeros(labels.shape, np.int32)
            expected_colors, expected_areas = [0], [0]
            offset = 0
            for color in np.unique(labels):
                components, local, stats, _ = cv2.connectedComponentsWithStats(
                    (labels == color).astype(np.uint8), connectivity=8
                )
                selected = local > 0
                expected_ids[selected] = local[selected] + offset
                expected_colors.extend([int(color)] * (components - 1))
                expected_areas.extend(stats[1:, cv2.CC_STAT_AREA])
                offset += components - 1
            values, first = np.unique(ids.ravel(), return_index=True)
            mapping = np.zeros(int(ids.max()) + 2, np.int64)
            mapping[values] = expected_ids.ravel()[first]
            self.assertEqual(len(set(mapping[values].tolist())), len(values), trial)
            self.assertTrue(np.array_equal(mapping[ids], expected_ids), trial)
            self.assertEqual(
                sorted(zip(colors[1:].tolist(), areas[1:].tolist())),
                sorted(zip(np.asarray(expected_colors)[1:].tolist(), np.asarray(expected_areas)[1:].tolist())),
                trial,
            )

    def test_no_overwrite_or_partial_file_when_budget_exceeded(self):
        source, output = self.root / "in.png", self.root / "out.html"
        Image.new("RGB", (16, 16), "red").save(source)
        status, _, _ = self.run_cli("convert", source, "-o", output, "--max-output-mb", ".0001", "--quiet")
        self.assertEqual(status, 1)
        self.assertFalse(output.exists())
        output.write_text("keep me", encoding="utf-8")
        status, _, _ = self.run_cli("convert", source, "-o", output, "--quiet")
        self.assertEqual(status, 1)
        self.assertEqual(output.read_text(), "keep me")
        status, _, _ = self.run_cli("convert", source, "-o", output, "--report", source, "--force")
        self.assertEqual(status, 1)
        with Image.open(source) as image:
            self.assertEqual(image.size, (16, 16))

    def test_unexpected_conversion_errors_are_reported(self):
        source, output = self.root / "in.png", self.root / "out.html"
        Image.new("RGB", (8, 8), "red").save(source)
        with mock.patch("css_art.cli.convert", side_effect=MemoryError()):
            status, _, stderr = self.run_cli("convert", source, "-o", output, "--quiet")
        self.assertEqual(status, 1)
        self.assertIn("MemoryError", stderr)
        self.assertFalse(output.exists())

    def test_atomic_write_survives_filesystems_without_hardlinks(self):
        target = self.root / "no-links.html"
        with mock.patch("os.link", side_effect=OSError(errno.EPERM, "hard links unavailable")):
            atomic_write(target, "first", False)
            self.assertEqual(target.read_text(encoding="utf-8"), "first")
            target.write_text("keep", encoding="utf-8")
            with self.assertRaises(OSError):
                atomic_write(target, "second", False)
        self.assertEqual(target.read_text(encoding="utf-8"), "keep")

    def test_audit_rejects_forbidden_resources(self):
        document, _ = self.convert(Image.new("RGB", (8, 8), "blue"))
        for injection in ('<script>alert(1)</script>', '<img src="x.png">', '<svg></svg>',
                          '<canvas></canvas>', '<div style="background:url(x)"></div>',
                          '<div onclick="x()"></div>', '<meta http-equiv="refresh" content="0;url=https://example.org">'):
            self.assertFalse(audit_html(document.replace("</main>", injection + "</main>"))["valid"], injection)

    def test_multipage_is_rejected(self):
        source, output = self.root / "animation.gif", self.root / "out.html"
        Image.new("RGB", (8, 8), "red").save(source, save_all=True, append_images=[Image.new("RGB", (8, 8), "blue")])
        status, _, stderr = self.run_cli("convert", source, "-o", output)
        self.assertEqual(status, 1)
        self.assertIn("multipage", stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
