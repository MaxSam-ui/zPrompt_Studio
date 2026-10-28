"""Shared prompt contracts. Preset examples never replace the requested scene."""
import re
from pathlib import Path

from core import config


def scene_contract():
    return system_template('Scene_Consistency.txt', allow_empty=True)


def render_template(template, **values):
    """Substitute once: braces inside inserted user/preset text remain literal."""
    missing = set(re.findall(r'\{([A-Za-z_][A-Za-z_0-9]*)\}', template)) - values.keys()
    if missing:
        raise ValueError('Unknown system-template placeholders: ' + ', '.join(sorted(missing)))
    return re.sub(r"\{([A-Za-z_][A-Za-z_0-9]*)\}",
                  lambda match: str(values.get(match[1], match[0])), template)


def system_template(filename, *, allow_empty=False):
    """Read on every request. Local overrides survive Git updates.

    A missing/invalid template fails visibly instead of silently injecting
    different instructions. Empty optional rule files explicitly disable them.
    """
    if Path(filename).name != filename:
        raise ValueError('System template must be a filename')
    base = Path(config.SUGGESTION_SYSTEM_DIR)
    custom = base / 'custom' / filename
    path = custom if custom.exists() else base / filename
    try:
        text = path.read_text(encoding='utf-8-sig').strip()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f'Cannot read system template: {path}. Restore the file or fix its UTF-8 encoding.') from exc
    if not text and not allow_empty:
        raise ValueError(f'Empty system template: {path}. Restore its contents or remove the custom override.')
    return text


def compose_system(filename, **values):
    template = system_template(filename)
    missing = set(re.findall(r'\{([A-Za-z_][A-Za-z_0-9]*)\}', template)) - values.keys()
    if missing:
        raise ValueError(f'Unknown placeholders in {filename}: {", ".join(sorted(missing))}')
    return render_template(template, **values)


def build_vision_prompt(preset="-", text_only=False, max_tokens=None):
    filename = "Text_Only_Template.txt" if text_only else "Master_Vision_Template.txt"
    template = system_template(filename)
    style = config.leggi_contenuto_suggerimento(config.SUGGESTION_VISION_DIR, preset) if preset and preset != "-" else ""
    result = render_template(template, regole_estetiche_vision=style)
    result += "\n\n" + scene_contract()
    if max_tokens is not None:
        result += f"\nLENGTH LIMIT: At most {int(max_tokens)} tokens. Be concise; do not pad the prompt to fill this limit."
    return result
