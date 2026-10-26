"""Shared prompt contracts. Preset examples never replace the requested scene."""
import re
from pathlib import Path

from core import config


SCENE_CONTRACT = """SCENE AND STYLE PRIORITIES:
- Follow the required output format and count. Explicit user choices of cast, actions, setting, camera, visual medium and aspect ratio take precedence over preset examples.
- Pixel dimensions and aspect ratio are controlled by the app. Do not impose a preset's example ratio; include a ratio only when explicitly requested by the task or scene. Preserve the required storyboard layout header.
- A style preset supplies presentation, lighting and mood. Its examples of people, props, locations, actions or camera moves are optional, not additions to the story. If a preset offers alternatives, choose the one compatible with the scene.
- An explicitly selected identity profile is a reference for its designated subject, not a visual style to apply to everyone. Preserve distinct people in a multi-character cast. In image analysis, do not replace observed identities with preset examples unless the user explicitly requests that transformation.
- Preserve names, identity references and literal model/LoRA trigger words. Write visual descriptions in English; keep requested signs and spoken dialogue in their original language.
- Do not add people to object-only, landscape or animal scenes. Describe clothes and human anatomy only when relevant. An illustration stays an illustration; fantasy stays possible when requested.
- Keep each character's identity and outfit attached to that character. Explicit wardrobe instructions override default garments, not physical identity. Unassigned wardrobe applies to the primary subject unless the user says otherwise.
- Keep setting and appearance consistent unless explicit actions require a change of place, time or clothing. Do not turn a temporary pose mentioned in an outfit reference into an action repeated in every shot.
- Camera motion and subject motion are independent: a static/locked camera does not make a moving subject stationary. Preserve the subject's action, direction and speed throughout every rewrite.
- Use concrete visible actions and audible sounds. Do not replace requested water sounds, footsteps or other sound sources with poetic metaphors. No dialogue/music does not mean no ambient sound. Preserve every explicitly requested sound source.
- For still images, express camera motion as framing and a visible moment. Do not force new poses or camera angles when the user requests a static shot, time-lapse, detail insert or repeated framing.
"""


def render_template(template, **values):
    """Substitute once: braces inside inserted user/preset text remain literal."""
    return re.sub(r"\{([A-Za-z_][A-Za-z_0-9]*)\}",
                  lambda match: str(values.get(match[1], match[0])), template)


def system_template(filename, fallback):
    path = Path(config.SUGGESTION_SYSTEM_DIR) / filename
    try:
        return path.read_text(encoding="utf-8-sig").strip() or fallback
    except OSError:
        return fallback


def build_vision_prompt(preset="-", text_only=False, max_tokens=None):
    task = ("Develop the user's requested scene into one English image prompt."
            if text_only else
            "Describe the supplied image faithfully in one English image prompt. Do not invent unseen details or actions.")
    filename = "Text_Only_Template.txt" if text_only else "Master_Vision_Template.txt"
    template = system_template(filename, task + "\n{regole_estetiche_vision}")
    style = config.leggi_contenuto_suggerimento(config.SUGGESTION_VISION_DIR, preset) if preset and preset != "-" else "Preserve the requested or observed visual medium."
    result = render_template(template, regole_estetiche_vision=style)
    result += "\n\n" + SCENE_CONTRACT
    if max_tokens is not None:
        result += f"\nLENGTH LIMIT: At most {int(max_tokens)} tokens. Be concise; do not pad the prompt to fill this limit."
    return result
