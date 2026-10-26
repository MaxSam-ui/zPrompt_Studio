# utils/storyboard_utils.py

import re
from utils.media_utils import calcola_hash_prompt


def is_vlm_status_message(text, dl):
    """Verifica se una stringa è un messaggio di stato/caricamento VLM per non corrompere i prompt."""
    from utils.vlm_status import VLMStatus
    if isinstance(text, VLMStatus):
        return True
    if not text:
        return False
    text_clean = text.strip()
    if any(text_clean.startswith(emoji) for emoji in ["⏳", "✅", "🧠", "🪄", "🎬", "⏹️"]):
        return True
    if dl:
        status_keys = [
            "vlm_loading", "vlm_ready_analisi", "vlm_ready_affinamento", 
            "vlm_ready_regia", "vlm_ready_idea", "vlm_elaborazione", 
            "vlm_affinamento", "vlm_regia", "vlm_idea"
        ]
        for key in status_keys:
            val = dl.get(key)
            if val and val.strip() == text_clean:
                return True
    return False


PANEL_MARKER = re.compile(
    r"^[ \t]*(?:#{1,4}[ \t]*)?(?:\*\*)?(?:(?:panel|pannel|pannello|frame|shot)[ \t]*#?[ \t]*(?P<number>\d+)|(?P<position>left|middle|center|right|top|bottom))\b(?:[ \t]*\([^\n)]*\))?(?:\*\*)?[ \t]*[:\-](?:\*\*)?[ \t]*",
    re.IGNORECASE | re.MULTILINE,
)


def separa_pannelli_storyboard(prompt):
    text = re.sub(r"^```[^\n]*\n|\n```$", "", (prompt or "").strip()).strip()
    # Remove the grid instruction as a whole; retain the shared cast paragraph.
    lines = text.splitlines()
    header_subject = ""
    if lines and re.search(r"\b(?:grid|triptych|diptych|quadtych)\b", lines[0], re.I):
        header_subject = re.sub(r"^.*?\b(?:grid|triptych|diptych|quadtych)\b(?:\s+of)?(?:\s+(?:realistic|cinematic))?(?:\s+(?:photos?|images?|illustrations?|shots?))?(?:\s+of)?\s*", "", lines[0], flags=re.I).strip(" ,.")
        text = "\n".join(lines[1:]).strip()
    markers = list(PANEL_MARKER.finditer(text))
    if not markers:
        return "\n\n".join(part for part in (header_subject, text) if part), {}
    base = "\n\n".join(part for part in (header_subject, text[:markers[0].start()].strip()) if part)
    panels = {}
    for index, marker in enumerate(markers):
        number = int(marker['number']) if marker['number'] else index + 1
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        panels[number] = text[marker.end():end].strip()
    return base, panels


def stile_per_pannello(preset):
    # Direction/action/layout instructions have already been resolved into the
    # individual shots by the compiler. Only shared visual style belongs here.
    lines = []
    for line in (preset or "").splitlines():
        match = re.match(r"^\s*[-*]?\s*(?:Visual Style|Atmosphere|Lighting|Color Palette|Style)\s*:\s*(.+)", line, re.I)
        if match and not re.search(r"\b(?:shifting|changing|transitions|panels|across|between)\b|->", match[1], re.I):
            lines.append(match[1])
    return " ".join(lines)


def estrai_prompt_pannello_robusto(flux_grid_prompt, idx, stile_preset=""):
    base, panels = separa_pannelli_storyboard(flux_grid_prompt)
    parts = ["A single full-frame cinematic shot"]
    if base:
        parts.append(base)
    if panels.get(idx + 1):
        parts.append(panels[idx + 1])
    style = stile_per_pannello(stile_preset)
    if style and style.lower() not in " ".join(parts).lower():
        parts.append("Visual style: " + style)
    return ", ".join(parts)


def storyboard_completo(prompt, count):
    _, panels = separa_pannelli_storyboard(prompt)
    return len(list(PANEL_MARKER.finditer(prompt or ""))) == count and set(panels) == set(range(1, count + 1)) and all(panels.values())


def normalizza_storyboard_catalogo(source, generated, count, preset=""):
    """Keep explicit catalog facts authoritative; AI contributes framing only."""
    sections = re.split(r"(?m)^(CHARACTERS / CAST|ENVIRONMENT & OUTFIT|SCENE ACTIONS):\s*\n", source or "")
    if len(sections) == 1:
        return generated
    fields = dict(zip(sections[1::2], sections[2::2]))
    _, generated_panels = separa_pannelli_storyboard(generated)
    actions = {}
    action_text = fields.get("SCENE ACTIONS", "")
    markers = list(re.finditer(r"(?m)^\s*(\d+)\)\s*", action_text))
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(action_text)
        actions[int(marker[1])] = action_text[marker.end():end].strip()
    baseline = []
    if fields.get("CHARACTERS / CAST", "").strip():
        baseline.append(fields["CHARACTERS / CAST"].strip())
        baseline.append("These are identity references; show only the characters participating in each panel's action. Keep identities and clothing consistent.")
    if fields.get("ENVIRONMENT & OUTFIT", "").strip():
        baseline.append(fields["ENVIRONMENT & OUTFIT"].strip())
        if fields.get("CHARACTERS / CAST", "").strip():
            baseline.append("Explicit outfit instructions take precedence over default garments in character references, while physical identities remain unchanged.")
            baseline.append("An unassigned outfit applies to the first listed character unless explicitly assigned otherwise; other characters retain their own outfits.")
    visual_style = stile_per_pannello(preset)
    if visual_style:
        baseline.append(visual_style)
    result = [f"horizontal {count}-panel storyboard grid,", "\n".join(baseline)]
    for index in range(1, count + 1):
        generated_action = generated_panels.get(index, "")
        action = actions.get(index)
        if action:
            framing = re.match(r"^((?:(?:extreme|medium|wide|tight|low-angle|high-angle|eye-level|over-the-shoulder|three-quarter|rear|front|profile|close|full|establishing|top-down|aerial|Dutch|wide-angle)\s+)*(?:shot|view|close-up))\b", generated_action, re.I)
            camera = framing[1] if framing else "medium shot"
            result.append(f"panel{index}: {camera}, {action}")
        elif generated_action:
            result.append(f"panel{index}: {generated_action}")
        else:
            # Missing unspecified panels must fail validation, not fabricate
            # a scene or silently renumber the user's explicit actions.
            result.append(f"panel{index}:")
    return "\n\n".join(result)
