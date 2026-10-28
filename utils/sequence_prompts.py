from utils.prompt_templates import compose_system
"""Parse numbered photo prompts without inventing people or dropping shots."""
import re

PHOTO = re.compile(r"^[ \t]*(?:\*\*)?(?:Photo|Foto|Shot|Frame|Scatto)[ \t]*#?[ \t]*(\d+)(?:\*\*)?[ \t]*[:.)-][ \t]*(?:\*\*)?", re.I | re.M)
HEADER = re.compile(r"^[ \t]*(?:\*\*)?(Characters?\s*/\s*Cast|Characters?|Cast|Personaggi|Soggetti|Environment\s*&\s*Outfit|Environment|Ambiente|Scenografia)(?:\*\*)?[ \t]*:[ \t]*", re.I | re.M)


def split_sequence(text):
    text = re.sub(r"^```[^\n]*\n|\n```$", "", (text or "").strip()).strip()
    markers = list(PHOTO.finditer(text))
    context = text[:markers[0].start()] if markers else text
    shots = [(int(m[1]), text[m.end():markers[i+1].start() if i+1 < len(markers) else len(text)].strip()) for i, m in enumerate(markers)]
    return context, shots


def sequence_complete(text, count):
    _, shots = split_sequence(text)
    return [n for n, _ in shots] == list(range(1, count + 1)) and all(s for _, s in shots)


def _context_fields(context):
    markers = list(HEADER.finditer(context))
    cast, environment = [], ""
    for i, match in enumerate(markers):
        value = context[match.end():markers[i+1].start() if i+1 < len(markers) else len(context)]
        value = re.sub(r"(?m)^\s*\[[^\n]*\]\s*$", "", value).strip()
        if match[1].lower().startswith(('environment', 'ambiente', 'scenografia')):
            environment = value
        else:
            cast = [re.sub(r"^\s*[-*]\s*", "", line).strip() for line in value.splitlines() if line.strip()]
            cast = [line for line in cast if line.lower().strip('. ') not in ('none', 'nessuno', 'n/a', 'no people')]
    return cast, environment


def _aliases(reference):
    label, _, description = reference.partition(':')
    names = [re.sub(r'\([^)]*\)', '', label).strip()]
    # Catalog display labels can differ from the actual name in the description.
    first = description.strip().split(',')[0].strip()
    if first and len(first.split()) <= 4 and not re.match(r'^(?:a|an|the)\s', first, re.I):
        names.append(first)
    return [name for name in names if name]


def extract_sequence_prompts(text):
    context, shots = split_sequence(text)
    if not sequence_complete(text, len(shots)) or not shots:
        return []
    cast, environment = _context_fields(context)
    prompts = []
    for _, action in shots:
        visible = [line for line in cast if any(re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', action, re.I) for name in _aliases(line))]
        no_cast = bool(re.search(r'\b(?:no (?:people|characters|cast)|object-only|empty landscape|unoccupied)\b', action, re.I))
        # An unnamed action must not pull every catalog character into a shot.
        # A single recurring subject remains unambiguous for legacy prompts.
        references = [] if no_cast else visible or (cast if len(cast) == 1 else [])
        parts = []
        if references:
            parts.append('Identity references for participating subjects only: ' + '; '.join(references))
        if environment:
            parts.append('Shared setting (explicit shot changes take precedence): ' + environment)
            if references:
                primary = _aliases(cast[0])[0]
                parts.append(compose_system('Sequence_Wardrobe.txt', primary=primary))
        # Preserve explicit counts if authored; never guess one from all catalog entries.
        parts.append(action)
        if len(cast) > 1 and not visible and not no_cast:
            parts.append(compose_system('Sequence_Participants.txt'))
        prompts.append('. '.join(parts))
    return prompts


def normalize_catalog_sequence(source, generated, count, style=''):
    from utils.storyboard_utils import normalizza_storyboard_catalogo, separa_pannelli_storyboard, stile_per_pannello
    sections = re.split(r'(?m)^(CHARACTERS / CAST|ENVIRONMENT & OUTFIT|SCENE ACTIONS):\s*\n', source or '')
    if len(sections) == 1:
        return generated
    fields = dict(zip(sections[1::2], sections[2::2]))
    _, shots = split_sequence(generated)
    board = '\n'.join(f'panel{n}: {action}' for n, action in shots)
    normalized = normalizza_storyboard_catalogo(source, board, count, style)
    _, panels = separa_pannelli_storyboard(normalized)
    cast = fields.get('CHARACTERS / CAST', '').strip() or 'None'
    environment = fields.get('ENVIRONMENT & OUTFIT', '').strip()
    visual = stile_per_pannello(style)
    result = f'[CONTEXT & IDENTITY LOCK]\nCharacters / Cast:\n{cast}\nEnvironment: {environment} {visual}\n[SEQUENCE SHOTS]\n'
    return result + '\n'.join(f'Photo {n}: {panels.get(n, "")}' for n in range(1, count + 1))
