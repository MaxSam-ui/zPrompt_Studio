"""Keep storyboard layout instructions out of cinematic scene descriptions."""
import re
from utils.storyboard_utils import separa_pannelli_storyboard


def scene_context(text):
    text = str(text or '').strip()
    layout = re.compile(r'\b(?:horizontal\s+\d+[- ]panel|\d+[- ]panel\s+horizontal|storyboard\s+grid|diptych|triptych|quadtych|four-panel strip)\b', re.I)
    if not layout.search(text) and not re.search(r'(?im)^\s*panel\s*\d+\s*:', text):
        return text
    base, panels = separa_pannelli_storyboard(text)
    result = '\n'.join([base, *panels.values()])
    result = layout.sub('', result)
    # Remove technical layout sentences, preserving cast, action and setting.
    sentences = re.split(r'(?<=[.!?])\s+|\n+', result)
    result = []
    for sentence in sentences:
        if re.search(r'\b(?:equal.sized panels|horizontal row|vertical borders|second row|extra panels|inset pictures|read left to right)\b', sentence, re.I):
            continue
        sentence = re.sub(r'^\s*(?:storyboard\s+)?grid\s*[,.:]?\s*', '', sentence, flags=re.I).strip(' ,')
        if sentence:
            result.append(sentence)
    return '\n'.join(result)
