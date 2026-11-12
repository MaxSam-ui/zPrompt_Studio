"""Align explicit image-format annotations with the requested render size."""
import math
import re


def align_prompt_aspect(text, width, height):
    width, height = int(width), int(height)
    if width <= 0 or height <= 0:
        return text
    factor = math.gcd(width, height)
    ratio = f"{width // factor}:{height // factor}"
    # Quoted scene text (e.g. a sign) is content, not a format instruction.
    pattern = r'''("[^"\n]*"|“[^”\n]*”|'[^'\n]*')|((?:\baspect\s+ratio|\brapporto\s+d['’]aspetto)\s*[:=]?\s*)\d+(?:\.\d+)?\s*:\s*\d+(?:\.\d+)?'''
    return re.sub(pattern, lambda m: m.group(0) if m.group(1) else m.group(2) + ratio,
                  text, flags=re.I)
