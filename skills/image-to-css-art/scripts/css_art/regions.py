"""Image preparation and conservative, adjacency-constrained region merging."""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps


def load_reference(path: Path, max_width: int, background: tuple[int, int, int]):
    with Image.open(path) as image:
        if getattr(image, "n_frames", 1) > 1:
            raise ValueError("Animated/multipage inputs are unsupported; export one frame first.")
        image = ImageOps.exif_transpose(image)
        original_size = image.size
        # Preserve alpha until it has been composited onto the explicit CSS matte.
        rgba = image.convert("RGBA")
        matte = Image.new("RGBA", rgba.size, (*background, 255))
        image = Image.alpha_composite(matte, rgba).convert("RGB")
        # A longest-edge bound prevents very tall references from bypassing the limit.
        scale = min(1.0, max_width / image.width, 2 * max_width / max(image.size))
        size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        if image.size != size:
            image = image.resize(size, Image.Resampling.LANCZOS)
        reference = np.array(image)
    if min(reference.shape[:2]) >= 3:
        reference = cv2.bilateralFilter(reference, 7, 22, 4)
        reference = cv2.bilateralFilter(reference, 9, 24, 5)
    return reference, original_size


def quantize(reference: np.ndarray, colors: int):
    image = Image.fromarray(reference).quantize(
        colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
    )
    labels = np.array(image)
    palette = np.asarray(image.getpalette(), dtype=np.uint8).reshape(-1, 3)
    return labels, palette


def label_components(labels):
    """Label 8-connected same-color components in one pass over the image.

    Components are numbered by ascending color value exactly like the previous
    per-color full-image cv2 labeling, while only the per-color bounding-box
    crops make the pass cheaper. Returns the int32 component image (0 outside
    components) plus parallel color and area arrays indexed by component id,
    with a placeholder at index 0.
    """
    width = labels.shape[1]
    ids = np.zeros(labels.shape, np.int32)
    flat = labels.ravel()
    order = np.argsort(flat, kind="stable")
    grouped = flat[order]
    starts = np.flatnonzero(np.concatenate(([True], grouped[1:] != grouped[:-1])))
    colors = grouped[starts]
    ends = np.concatenate((starts[1:], [grouped.size]))
    component_colors, component_areas = [0], [0]
    offset = 0
    for color, start, end in zip(colors, starts, ends):
        span = order[start:end]
        ys = span // width
        xs = span - ys * width
        y0, y1 = int(ys.min()), int(ys.max())
        x0, x1 = int(xs.min()), int(xs.max())
        crop = (labels[y0:y1 + 1, x0:x1 + 1] == color).astype(np.uint8)
        count, local, stats, _ = cv2.connectedComponentsWithStats(crop, connectivity=8)
        if count == 1:
            continue
        region = ids[y0:y1 + 1, x0:x1 + 1]
        foreground = local > 0
        region[foreground] = local[foreground] + offset
        component_colors.extend([int(color)] * (count - 1))
        component_areas.extend(stats[1:, cv2.CC_STAT_AREA].tolist())
        offset += count - 1
    return ids, np.asarray(component_colors), np.asarray(component_areas)


def merge_regions(labels, palette, passes=4, progress=lambda _: None):
    """Merge tiny components into adjacent, larger, similar-colored components.

    The original palette label bounds cumulative drift across passes. Small dark
    eye/hair lines cannot be replaced by a spatially close but unrelated fill.
    """
    labels = labels.copy()
    original = labels.copy()
    for iteration in range(passes):
        ids, component_colors, component_areas = label_components(labels)
        component_colors = np.asarray(component_colors)
        component_areas = np.asarray(component_areas)
        proposals = []
        for dy, dx in [(0, 1), (1, 0), (1, 1), (1, -1)]:
            ya, yb = (slice(0, -1), slice(1, None)) if dy else (slice(None), slice(None))
            if dx == 1:
                xa, xb = slice(0, -1), slice(1, None)
            elif dx == -1:
                xa, xb = slice(1, None), slice(0, -1)
            else:
                xa, xb = slice(None), slice(None)
            one, two = ids[ya, xa].ravel(), ids[yb, xb].ravel()
            boundary = one != two
            one, two = one[boundary], two[boundary]
            for src, dst in [(one, two), (two, one)]:
                candidate = (component_areas[src] < 16) & (
                    (component_areas[dst] > component_areas[src])
                    | ((component_areas[dst] == component_areas[src]) & (dst > src))
                )
                src, dst = src[candidate], dst[candidate]
                if not len(src):
                    continue
                diff = palette[component_colors[src]].astype(np.float32) - palette[
                    component_colors[dst]
                ].astype(np.float32)
                accepted = np.max(np.abs(diff), axis=1) <= 18
                src, dst, diff = src[accepted], dst[accepted], diff[accepted]
                if len(src):
                    proposals.append(np.column_stack((src, dst, np.sum(diff * diff, axis=1))))
        if not proposals:
            break
        candidates = np.concatenate(proposals)
        # Explicit tie-breaking keeps the result repeatable in one dependency environment.
        ordered = candidates[np.lexsort((candidates[:, 1], candidates[:, 2], candidates[:, 0]))]
        _, first = np.unique(ordered[:, 0], return_index=True)
        best = ordered[first]
        new_colors = component_colors.copy()
        new_colors[best[:, 0].astype(int)] = component_colors[best[:, 1].astype(int)]
        updated = new_colors[ids].astype(np.uint8)
        drift = np.abs(palette[updated].astype(np.int16) - palette[original].astype(np.int16)).max(axis=2)
        updated[drift > 23] = labels[drift > 23]
        changes = int(np.count_nonzero(updated != labels))
        labels = updated
        progress(f"Merge {iteration + 1}/{passes}: {changes} pixels")
        if not changes:
            break
    return labels
