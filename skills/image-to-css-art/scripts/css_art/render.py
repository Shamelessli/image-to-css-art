"""Build a static document with only inline CSS and HTML contour elements."""

import html
import math

import cv2
import numpy as np

from .geometry import bridge_rings, component_rings, hex_color, mask_polygon, number, polygon_css
from .regions import quantize


def paint_for_region(reference, mask, x, y, width, height, gradients):
    ys, xs = np.nonzero(mask)
    samples = reference[y + ys, x + xs].astype(float)
    solid = hex_color(samples.mean(axis=0))
    if not gradients or len(xs) < 45 or min(width, height) < 5:
        return solid, False
    if len(xs) > 6000:
        step = math.ceil(len(xs) / 6000)
        xs, ys, samples = xs[::step], ys[::step], samples[::step]
    design = np.column_stack((xs + .5 - width / 2, ys + .5 - height / 2, np.ones(len(xs))))
    coeff, _, _, _ = np.linalg.lstsq(design, samples, rcond=None)
    axes, _, _ = np.linalg.svd(coeff[:2], full_matrices=False)
    direction = axes[:, 0]
    slope = direction @ coeff[:2]
    length = abs(direction[0]) * width + abs(direction[1]) * height
    low, high = np.percentile(samples, (3, 97), axis=0)
    start = np.clip(coeff[2] - slope * length / 2, low, high)
    end = np.clip(coeff[2] + slope * length / 2, low, high)
    if np.max(np.abs(end - start)) < 3:
        return solid, False
    angle = math.degrees(math.atan2(direction[0], -direction[1])) % 360
    return f"linear-gradient({number(angle, 1)}deg,{hex_color(start)},{hex_color(end)})", True


def color_order(labels, palette):
    return sorted(np.unique(labels), key=lambda i: (-float(palette[i] @ np.array([.2126, .7152, .0722])), int(i)))


def same_as_matte(rgb, background):
    return int(np.abs(rgb.astype(np.int16) - background).max()) <= 3


class ContourRenderer:
    def __init__(self, reference, background, epsilon, gradients, max_bytes):
        self.reference = reference
        self.height, self.width = reference.shape[:2]
        self.background = np.array(background)
        self.epsilon = epsilon
        self.gradients = gradients
        self.max_bytes = max_bytes
        self.byte_count = 0
        self.stats = {"shapes": 0, "gradient_fills": 0, "polygon_vertices": 0, "interior_holes": 0, "underpainting_shapes": 0}

    def account(self, text):
        self.byte_count += len(text.encode("utf-8"))
        if self.byte_count > self.max_bytes:
            raise ValueError("HTML exceeds --max-output-mb; reduce --max-width/--colors or raise the limit.")
        return text

    def shape(self, rings, paint):
        all_points = np.concatenate(rings)
        origin = all_points.min(axis=0)
        size = all_points.max(axis=0) - origin
        if np.any(size <= 0):
            return None
        points = bridge_rings(rings)
        clip = polygon_css(points, origin, size, len(rings) > 1)
        style = (
            f"left:{number(origin[0] / self.width * 100, 5)}%;top:{number(origin[1] / self.height * 100, 5)}%;"
            f"width:{number(size[0] / self.width * 100, 5)}%;height:{number(size[1] / self.height * 100, 5)}%;"
            f"background:{paint};clip-path:{clip}"
        )
        self.stats["shapes"] += 1
        self.stats["polygon_vertices"] += len(points)
        return self.account(f'<div class="shape" style="{style}"></div>')

    def foreground(self, labels, palette, progress):
        parts = []
        order = color_order(labels, palette)
        for position, color in enumerate(order):
            rgb = palette[color]
            if same_as_matte(rgb, self.background):
                continue
            count, ids, stats, centers = cv2.connectedComponentsWithStats(
                (labels == color).astype(np.uint8), connectivity=8
            )
            small_groups = {}
            for component in range(1, count):
                x, y, width, height, area = map(int, stats[component])
                mask = (ids[y:y + height, x:x + width] == component).astype(np.uint8)
                paint, gradient = paint_for_region(self.reference, mask, x, y, width, height, self.gradients) if area >= 24 else (hex_color(rgb), False)
                for rings in component_rings(mask, x, y, area, self.epsilon):
                    self.stats["interior_holes"] += len(rings) - 1
                    if area < 24:
                        key = tuple((centers[component] // 160).astype(int))
                        small_groups.setdefault(key, []).extend(rings)
                    else:
                        shape = self.shape(rings, paint)
                        if shape:
                            parts.append(shape)
                            self.stats["gradient_fills"] += int(gradient)
            for rings in small_groups.values():
                shape = self.shape(rings, hex_color(rgb))
                if shape:
                    parts.append(shape)
            if position % 32 == 0:
                progress(f"Trace {position + 1}/{len(order)} colors: {self.stats['shapes']} shapes")
        return "\n".join(parts)

    def underpainting(self):
        if min(self.width, self.height) < 8:
            return ""
        difference = np.abs(self.reference.astype(np.int16) - self.background).max(axis=2)
        silhouette = cv2.medianBlur((difference > 9).astype(np.uint8), 3)
        silhouette = cv2.erode(silhouette, np.ones((5, 5), np.uint8))
        clip, vertices = mask_polygon(silhouette, .5, 8)
        if not clip:
            return ""
        self.stats["polygon_vertices"] += vertices
        scale = min(1, 516 / self.width, 1 / 3)
        small = cv2.resize(self.reference, (max(2, round(self.width * scale)), max(2, round(self.height * scale))), interpolation=cv2.INTER_AREA)
        small = cv2.medianBlur(small, 3)
        labels, palette = quantize(small, 48)
        parts = []
        for color in color_order(labels, palette):
            rgb = palette[color]
            if same_as_matte(rgb, self.background):
                continue
            mask = cv2.dilate((labels == color).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
            polygon, vertices = mask_polygon(mask, .26, 1)
            if polygon:
                parts.append(self.account(f'<div class="shape" style="inset:0;background:{hex_color(rgb)};clip-path:{polygon}"></div>'))
                self.stats["polygon_vertices"] += vertices
                self.stats["shapes"] += 1
                self.stats["underpainting_shapes"] += 1
        return self.account(f'<div class="underpainting" aria-hidden="true" style="clip-path:{clip}">') + "\n" + "\n".join(parts) + "\n</div>"


def render_document(reference, labels, palette, original_size, *, background, title,
                    epsilon, gradients, underpainting, max_bytes, progress):
    renderer = ContourRenderer(reference, background, epsilon, gradients, max_bytes)
    foundation = renderer.underpainting() if underpainting else ""
    shapes = renderer.foreground(labels, palette, progress)
    width, height = original_size
    matte = hex_color(background)
    label = html.escape(title, quote=True)
    document = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; script-src 'none'; connect-src 'none'; font-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">
<title>{label}</title>
<style>
*{{box-sizing:border-box}}
html,body{{margin:0;min-height:100%;background:{matte}}}
.illustration{{position:relative;isolation:isolate;overflow:hidden;width:min(100%,{renderer.width}px);aspect-ratio:{width}/{height};margin:0 auto;background:{matte};contain:layout paint}}
.shape{{position:absolute;pointer-events:none}}
.underpainting{{position:absolute;inset:0;pointer-events:none}}
@media print{{@page{{margin:0}}.illustration{{width:100%;print-color-adjust:exact;-webkit-print-color-adjust:exact}}}}
</style>
</head>
<body>
<!-- Offline contour tracing. Every visible mark is an HTML/CSS layer. -->
<main class="illustration" role="img" aria-label="{label}">
{foundation}
{shapes}
</main>
</body>
</html>
'''
    if len(document.encode("utf-8")) > max_bytes:
        raise ValueError("HTML exceeds --max-output-mb; reduce --max-width/--colors or raise the limit.")
    return document, renderer.stats
