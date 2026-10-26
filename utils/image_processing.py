# utils/image_processing.py

import os
import re
import numpy as np
from PIL import Image

from core import config, log


class StoryboardLayoutError(ValueError):
    """The generated grid cannot be split reliably into the requested panels."""


def verifica_layout_storyboard(filepath, count):
    with Image.open(filepath) as image:
        return _rileva_disposizione(image, count)


def taglia_storyboard_pil(filepath, layout):
    """Divide la griglia in ordine di lettura, riconoscendo righe, colonne e divisori."""
    if not filepath or not os.path.exists(filepath):
        return []
        
    try:
        with Image.open(filepath) as im_raw:
            im = im_raw.copy()
            
        w, h = im.size
        
        if isinstance(layout, (int, float)):
            num_pannelli = int(layout)
        elif isinstance(layout, str):
            match = re.search(r'(\d+)', layout)
            num_pannelli = int(match.group(1)) if match else 3
        else:
            num_pannelli = 3
        
        num_pannelli = max(2, min(4, num_pannelli))

        columns, rows, x_cuts, y_cuts = _rileva_disposizione(im, num_pannelli)
        slices = []
        x_ranges = _intervalli_pannelli(w, x_cuts)
        y_ranges = _intervalli_pannelli(h, y_cuts)
        for top, bottom in y_ranges:
            for left, right in x_ranges:
                slices.append(im.crop((left, top, right, bottom)))
        log.registra(f"Storyboard: detected layout {columns} columns × {rows} rows.")

        salvati_paths = []
        if slices:
            local_dir = os.path.join(config.STUDIO_OUTPUT_DIR, config.STUDIO_IMG_SUBDIR)
            os.makedirs(local_dir, exist_ok=True)
            nome_base = os.path.splitext(os.path.basename(filepath))[0]
            
            for idx, sl in enumerate(slices):
                prefisso = f"{nome_base}_panel_{idx+1}"
                nuovo_nome = config.genera_nome_univoco(local_dir, prefisso, "png")
                dest_path = os.path.abspath(os.path.join(local_dir, nuovo_nome))
                sl.save(dest_path, "PNG")
                salvati_paths.append(dest_path)
                
        return salvati_paths
        
    except StoryboardLayoutError:
        raise
    except Exception as e:
        log.registra(f"Storyboard slicing error: {e}", "WARNING")
        return []


def _analizza_divisori(pixels, count):
    """Find full-span seams near equal panel boundaries along the first axis."""
    # Explicit neutral gutters can be far from equally spaced boundaries.
    # Inspect the entire axis before using local contrast peaks. Require a
    # narrow, full-span strip and reject missing/extra separators instead of
    # guessing a cut through the scene.
    length = pixels.shape[0]
    means = pixels.mean(axis=(1, 2))
    neutral = (pixels.std(axis=(1, 2)) < 6) & ((means >= 240) | (means <= 15))
    edges = np.flatnonzero(np.diff(np.r_[False, neutral, False].astype(int)))
    gutters = [(int(a), int(b)) for a, b in zip(edges[::2], edges[1::2])
               if a > length * .05 and b < length * .95 and 2 <= b-a <= length * .08]
    if gutters:
        if len(gutters) != count - 1:
            return [], 0.
        widths = [b-a for a, b in _intervalli_pannelli(length, gutters)]
        if min(widths) < length / count * .35:
            return [], 0.
        return gutters, 100.
    if count == 1:
        return [], float("inf")
    length = pixels.shape[0]
    step = length / count
    difference = np.abs(np.diff(pixels, axis=0)).mean(axis=2)
    # A seam must cross most of the image, rather than one foreground object.
    strength = np.quantile(difference, .25, axis=1)
    baseline = max(1., float(np.median(strength)))
    cuts, scores = [], []
    for i in range(1, count):
        target = i * step
        start = max(0, int(target - step * .12))
        end = min(length - 1, int(target + step * .12) + 1)
        if end <= start:
            return [], 0.
        seam = start + int(np.argmax(strength[start:end]))
        scores.append(float(strength[seam]) / baseline)
        boundary = seam + 1
        # Exclude a narrow white/black gutter, if present next to the seam.
        means = pixels.mean(axis=(1, 2))
        flat = pixels.std(axis=(1, 2)) < 6
        gutter = flat & ((means >= 240) | (means <= 15))
        lo, hi = boundary, boundary
        candidate = next((j for j in (seam, seam + 1) if gutter[j]), None)
        if candidate is not None:
            lo, hi = candidate, candidate + 1
            while lo > 0 and gutter[lo - 1]:
                lo -= 1
            while hi < length and gutter[hi]:
                hi += 1
            if hi - lo > step * .08:
                lo = hi = boundary
        cuts.append((lo, hi))
    return cuts, min(scores)


def _rileva_disposizione(image, count):
    pixels = np.asarray(image.convert("RGB"), dtype=np.float32)
    # A strong seam on both axes identifies a 2x2 grid even when the model
    # ignored a request for two or three frames. Never refine merged shots.
    if count < 4:
        _, xs = _analizza_divisori(pixels.transpose(1, 0, 2), 2)
        _, ys = _analizza_divisori(pixels, 2)
        if min(xs, ys) >= 12:
            raise StoryboardLayoutError("Detected a 2x2 grid instead of the requested panel count")
    candidates = []
    for columns, rows in ([(count, 1), (1, count)] + ([(2, 2)] if count == 4 else [])):
        x_cuts, x_score = _analizza_divisori(pixels.transpose(1, 0, 2), columns)
        y_cuts, y_score = _analizza_divisori(pixels, rows)
        candidates.append((min(x_score, y_score), columns, rows, x_cuts, y_cuts))
    score, columns, rows, x_cuts, y_cuts = max(candidates, key=lambda entry: entry[0])
    if score < 6:
        # Equal-width fallback silently cuts through shots when the model
        # generates extra panels or irregular layouts. Preserve the preview.
        raise StoryboardLayoutError("Requested panel boundaries could not be identified reliably")
    return columns, rows, x_cuts, y_cuts


def _intervalli_pannelli(length, cuts):
    starts = [0] + [end for _, end in cuts]
    ends = [start for start, _ in cuts] + [length]
    return list(zip(starts, ends))
