"""Model-specific presentation; keep the timeline text intact for validation."""
import re

MINIMAX_SECTIONS = ('subject_definitions', 'summary', 'retention_analysis',
                    'detailed_description', 'overall_soundscape', 'non_diegetic_music')


MINIMAX_BASE_SECTIONS = ('integrated_multimodal_description', 'overall_soundscape', 'non_diegetic_music')


def minimax_format(profile):
    value = profile.get('prompt_format', 'auto')
    if value not in ('auto', 'base', 'reference'):
        raise ValueError('MiniMax prompt_format must be auto, base or reference.')
    return ('base' if profile['image_mode'] == 'native_keyframes' else 'reference') if value == 'auto' else value


def minimax_sections(text, format=None):
    # Accept presentation-only Markdown from chat models without a second LLM
    # call. Keep names, ordering, duplicate and nonempty checks strict.
    text = re.sub(r'^\s*```[^\n]*\n|\n\s*```\s*$', '', text.strip())
    all_names = '|'.join(dict.fromkeys(MINIMAX_SECTIONS + MINIMAX_BASE_SECTIONS))
    text = re.sub(
        r'^\s*(?:#{1,6}\s+)?(?:\*\*|__)?(' + all_names + r')(?:\*\*|__)?\s*:(?:\*\*|__)?[ \t]*',
        lambda m: m[1].lower() + ': ', text, flags=re.M | re.I)
    names = (MINIMAX_BASE_SECTIONS if format == 'base' or (format is None and re.search(r'^integrated_multimodal_description:', text, re.M)) else MINIMAX_SECTIONS)
    pattern = r'^(?:' + '|'.join(dict.fromkeys(MINIMAX_SECTIONS + MINIMAX_BASE_SECTIONS)) + r'):\s*'
    matches = list(re.finditer(pattern, text, re.M))
    if [m[0].split(':')[0] for m in matches] != list(names):
        return None
    parts = {name: text[m.end():matches[i+1].start() if i+1 < len(matches) else len(text)].strip()
             for i, (name, m) in enumerate(zip(names, matches))}
    return parts if all(parts.values()) else None


def minimax_compiler_instruction(canonical, references, direct=False, format="reference"):
    if format not in ("base", "reference"):
        raise ValueError("Unknown MiniMax prompt format")
    from utils.prompt_templates import compose_system
    context = compose_system('MiniMax_References.txt', references=references) if references else compose_system('MiniMax_No_References.txt')
    if format == 'base':
        return compose_system('MiniMax_Base_Compiler.txt', canonical=canonical)
    return compose_system('MiniMax_Compiler.txt', canonical=canonical, reference_context=context)


def minimax_prompt(text, references=0):
    text = str(text or '').strip()
    if all(re.search(r'^' + name + r':', text, re.M) for name in MINIMAX_SECTIONS):
        return text
    subject = ''
    if text.startswith('Subject and scene: ') and '\n\n' in text:
        subject, text = text.split('\n\n', 1)
        subject = subject.removeprefix('Subject and scene: ').strip()
    audio = re.search(r'\nAudio:\s*(.*)\Z', text, re.S)
    sound = audio[1].strip() if audio else ''
    if audio:
        text = text[:audio.start()].strip()
    refs = ' '.join(f'<Picture {i}> is a visual reference.' for i in range(1, references + 1))
    from utils.prompt_templates import compose_system
    return compose_system('MiniMax_Legacy_Format.txt', subject=subject, refs=refs, text=text, sound=sound)



def _outside_quotes(text, transform):
    # Literal dialogue/lettering must survive conversions verbatim.
    return ''.join(piece if i % 2 else transform(piece) for i, piece in
                   enumerate(re.split(r'(<d>.*?</d>|"[^"\n]*")', text, flags=re.S)))


def _resolve_subjects(text, definitions):
    mapping = {}
    for match in re.finditer(r'(?m)^\s*(<Subject \d+>)\s*(?:is\s+|:\s*)?(.+)', definitions):
        description = re.sub(r'\s+(?:in|from|shown in)\s*<Picture \d+>', '', match[2]).strip().rstrip('.')
        mapping[match[1]] = description
    def replace(match):
        if match[0] not in mapping:
            raise ValueError('Undefined MiniMax subject reference. Recreate the video prompt for the selected model.')
        value = mapping[match[0]]
        if re.search(r'<Subject \d+>', value):
            raise ValueError('Nested MiniMax subject references. Recreate the video prompt.')
        return value
    return _outside_quotes(text, lambda part: re.sub(r'<Subject \d+>', replace, part))


def _definition_prose(definitions):
    return re.sub(r'(?m)^\s*<Subject \d+>\s*(?:is\s+|:\s*)?', '', definitions).strip()


def _plain_references(text):
    # Keep the role, never invent the appearance of an unseen image.
    return _outside_quotes(text, lambda part: re.sub(r'<Picture (\d+)>', r'reference image \1', part))


def _reference_content(parts):
    definitions = parts['subject_definitions']
    # Summary/retention can contain user constraints absent from the action spans.
    context = '\n'.join((parts['summary'], parts['retention_analysis']))
    return '\n'.join((_definition_prose(definitions),
                      _resolve_subjects(context, definitions),
                      _resolve_subjects(parts['detailed_description'], definitions)))


def _minimax_timed_prose(text):
    """Render cuts from validated boundaries; intervals alone never create cuts."""
    from utils.director_prompt import TIMECODE
    def convert(part):
        matches = list(TIMECODE.finditer(part))
        if not matches:
            return part
        result = [part[:matches[0].start()]]
        for index, match in enumerate(matches):
            end = matches[index+1].start() if index+1 < len(matches) else len(part)
            body = part[match.end():end].strip()
            shot = re.search(r'\[Shot (\d+)\]', body)
            if shot:
                body = body[:shot.start()] + body[shot.end():]
                # A model's rounded cut time must not override timeline boundaries.
                body = re.sub(r'\bAt \d{1,2}:\d{2}(?:\.\d+)?\s*,?\s*', '', body, count=1)
                if shot[1] == '1':
                    lead = '[Shot 1] '
                else:
                    millis = round(float(match[1]) * 1000)
                    minutes, remaining = divmod(millis, 60000)
                    seconds, fraction = divmod(remaining, 1000)
                    lead = f'[Shot {shot[1]}] At {minutes:02d}:{seconds:02d}.{fraction:03d}, '
            else:
                lead = f'From {float(match[1]):g} to {float(match[2]):g} seconds, '
            result.append(lead + body.strip())
        return '\n'.join(result).strip()
    # Work on whole spans so quotes cannot split timing boundaries, but mask
    # literal strings while looking for structural markers.
    protected = []
    def mask(match):
        protected.append(match[0])
        return f'@@STUDIO_LITERAL_{len(protected)-1}@@'
    masked = re.sub(r'<d>.*?</d>|"[^"\n]*"', mask, text, flags=re.S)
    result = convert(masked)
    for index, literal in enumerate(protected):
        result = result.replace(f'@@STUDIO_LITERAL_{index}@@', literal)
    return result


def _timed_prose(text):
    from utils.director_prompt import TIMECODE
    return _outside_quotes(text, lambda part: TIMECODE.sub(
        lambda m: f'From {float(m[1]):g} to {float(m[2]):g} seconds,', part))


def ltx_prompt(text):
    """Translate transport notation without deleting identity or spoken words."""
    parts = minimax_sections(text)
    if parts:
        body = parts.get('detailed_description', parts.get('integrated_multimodal_description', ''))
        if 'subject_definitions' in parts:
            body = _reference_content(parts)
        text = '\n'.join((body, 'Audio: ' + parts['overall_soundscape'],
                          'Music: ' + parts['non_diegetic_music']))
    text = _resolve_subjects(text, '')
    text = _plain_references(text)
    def clean(part):
        part = re.sub(r'\[/?VISUAL\]', '', part, flags=re.I)
        part = re.sub(r'\[SPEECH\]', 'Dialogue: ', part, flags=re.I)
        part = re.sub(r'\[SOUNDS\]', 'Sound: ', part, flags=re.I)
        part = re.sub(r'\[/(?:SPEECH|SOUNDS)\]', '', part, flags=re.I)
        return re.sub(r'\[Shot \d+\]', '', part)
    text = _outside_quotes(text, clean)
    text = re.sub(r'<d>\[([^]\n]+)\]\s*(.*?)</d>', r'In \1: "\2"', text, flags=re.S)
    text = re.sub(r'<d>(.*?)</d>', r'"\1"', text, flags=re.S)
    return _timed_prose(text).strip()


def minimax_payload(text, *, format, duration, first=False, last=False, middle=False):
    """Render validated, editable timed text at the workflow boundary, no LLM pass."""
    from utils.prompt_templates import compose_system
    parts = minimax_sections(text)
    if format == 'reference':
        if parts and 'subject_definitions' not in parts:
            raise ValueError('MiniMax reference mode needs a reference prompt. Recreate the video prompt after changing the workflow profile.')
        if not parts:
            text = minimax_prompt(text, references=int(first)+int(last)+int(middle))
            parts = minimax_sections(text)
        if not parts:
            raise ValueError('Incomplete MiniMax reference prompt. Recreate the video prompt.')
        roles = []
        if first:
            roles.append('<Picture 1>: opening composition')
        if last:
            roles.append(f'<Picture {2 if first else 1}>: ending composition')
        if middle:
            roles.append(f'<Picture {int(first)+int(last)+1}>: intermediate scene state')
        if roles:
            parts['summary'] += '\n' + compose_system('MiniMax_Reference_Roles.txt', roles='; '.join(roles))
        parts['detailed_description'] = _minimax_timed_prose(parts['detailed_description'])
        if parts['non_diegetic_music'].strip().lower() in ('none', 'no music'):
            parts['non_diegetic_music'] = 'N/A'
        return '\n\n'.join(f'{key}: {parts[key]}' for key in MINIMAX_SECTIONS)
    if format != 'base':
        raise ValueError('Unknown MiniMax prompt format')
    if parts:
        body = parts.get('integrated_multimodal_description', parts.get('detailed_description', ''))
        if 'subject_definitions' in parts:
            body = _reference_content(parts)
        sound, music = parts['overall_soundscape'], parts['non_diegetic_music']
    else:
        # Legacy free prose stays intact; do not guess which sounds are music.
        body, sound, music = text, compose_system('MiniMax_Legacy_Audio.txt'), compose_system('MiniMax_Legacy_Music.txt')
    body = _resolve_subjects(body, '')
    body = _plain_references(body)
    body = _minimax_timed_prose(body)
    if not re.search(r'\[Shot 1\]', body):
        body = '[Shot 1] ' + body
    unquoted = re.sub(r'<d>.*?</d>|"[^"\n]*"', '', body, flags=re.S)
    last_shot = max([int(n) for n in re.findall(r'\[Shot (\d+)\]', unquoted)] or [1])
    alignment = ''
    if first and last:
        alignment = compose_system('MiniMax_Align_First_Last.txt', duration=f'{duration:.2f}', shot=last_shot)
    elif first:
        alignment = compose_system('MiniMax_Align_First.txt')
    elif last:
        alignment = compose_system('MiniMax_Align_Last.txt', duration=f'{duration:.2f}', shot=last_shot)
    if middle:
        # Native AddGuide supplies a latent keyframe, not an extra encoder Picture token.
        body += '\n' + compose_system('MiniMax_Middle_Guide.txt')
    if music.strip().lower() in ('none', 'no music', 'n/a'):
        music = 'N/A'
    result = '\n\n'.join(f'{key}: {value}' for key,value in zip(MINIMAX_BASE_SECTIONS,(body,sound,music)))
    return (alignment + '\n\n' if alignment else '') + result


def selected_video_frames(state, saved, text_only=False):
    """Same storyboard selection used when assembling the video workflow."""
    state = state or {}
    if text_only:
        return None, None, None
    frames = state.get('lista_frame_storyboard_attivi', [])
    if (not state.get('is_extension', False) and
            'storyboard' in str(saved.get('generation_mode', '')).lower() and len(frames) >= 2):
        return frames[0], frames[-1], frames[len(frames)//2] if len(frames) >= 3 else None
    return (state.get('percorso_immagine_selezionata') or saved.get('percorso_immagine_selezionata'),
            state.get('percorso_immagine_destinazione') or saved.get('percorso_immagine_destinazione'), None)
