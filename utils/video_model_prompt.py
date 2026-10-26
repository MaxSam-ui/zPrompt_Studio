"""Model-specific presentation; keep the timeline text intact for validation."""
import re

MINIMAX_SECTIONS = ('subject_definitions', 'summary', 'retention_analysis',
                    'detailed_description', 'overall_soundscape', 'non_diegetic_music')


def minimax_sections(text):
    pattern = r'^(?:' + '|'.join(MINIMAX_SECTIONS) + r'):\s*'
    matches = list(re.finditer(pattern, text, re.M))
    if [m[0].split(':')[0] for m in matches] != list(MINIMAX_SECTIONS):
        return None
    parts = {name: text[m.end():matches[i+1].start() if i+1 < len(matches) else len(text)].strip()
             for i, (name, m) in enumerate(zip(MINIMAX_SECTIONS, matches))}
    return parts if all(parts.values()) else None


def minimax_compiler_instruction(canonical, references, direct=False):
    return (
        ('Compile the supplied subject, reference descriptions and timeline directly into a final MiniMax H3 prompt in English. Translate visual descriptions faithfully; return only the prompt. ' if direct else
         'Rewrite this validated screenplay for MiniMax H3 in English. Return only the prompt. ') +
        'Use exactly these six section headers, in this order: ' + ', '.join(MINIMAX_SECTIONS) + '. '
        'Define each recurring person as <Subject 1>, <Subject 2>, etc.; preserve literal names, '
        'trigger tokens, age, clothing, appearance and action ownership. Do not invent people. '
        'Keep object-only scenes object-only. Never create empty or absent subject entries such as <Subject 2>: None. Subject definitions describe identity and appearance, '
        'not a new action or stationary pose. A static camera does not stop a moving subject. '
        'The supplied shot and camera motion are fixed decisions, not style suggestions. Keep the prose consistent with them: no orbit, pan, zoom or push-in inside a static shot, and no contradictory shot size. Subject movement may continue under a static camera. Do not introduce a cut at every interval boundary or force shot variety. '
        'summary describes the scene concisely. retention_analysis states which supplied details '
        'remain unchanged and which explicitly change. detailed_description contains every original '
        'time interval exactly once, unchanged, with its action and camera direction. Put timecodes '
        'only in detailed_description. Preserve every motion verb, direction and speed; this is a formatting '
        'pass, not a creative rewrite. Do not add new scenery or change gliding/drifting into remaining still. '
        'Preserve each explicitly requested ambient sound source, including water sounds even when there is no voice or music. '
        'Use <d>spoken words</d> only for explicitly supplied dialogue, '
        'preserving its original spoken language; do not invent dialogue. Describe delivery separately. '
        'overall_soundscape describes requested voice and ambient sound. non_diegetic_music contains '
        'only requested music, or None. Do not add negative instructions or new aesthetic constraints. '
        + (f'There are {references} reference images, identified as <Picture 1> through <Picture {references}>. '
           'Preserve any starting, intermediate or ending frame constraints stated in the screenplay. ' if references else
           'There are no reference images: do not mention Picture tokens. ')
        + '\nAUTHORITATIVE SCREENPLAY:\n' + canonical
    )


def minimax_prompt(text, references=0):
    text = str(text or '').strip()
    if all(re.search(r'^' + name + r':', text, re.M) for name in MINIMAX_SECTIONS):
        return text
    subject = ''
    if text.startswith('Subject and scene: ') and '\n\n' in text:
        subject, text = text.split('\n\n', 1)
        subject = subject.removeprefix('Subject and scene: ').strip()
    audio = re.search(r'\nAudio:\s*(.*)\Z', text, re.S)
    sound = audio[1].strip() if audio else 'Follow only the sounds and dialogue explicitly described in the scene.'
    if audio:
        text = text[:audio.start()].strip()
    refs = ' '.join(f'<Picture {i}> is a visual reference.' for i in range(1, references + 1))
    values = (subject or 'Use the subjects explicitly described below.',
              'Generate the chronological scene described below. ' + refs,
              'Preserve recurring identities and appearance unless an explicit change is requested. '
              'Respect the supplied image roles and any stated starting, intermediate or ending frame constraints.',
              text, sound, 'Use music only when explicitly requested in the soundscape or scene; otherwise none.')
    return '\n\n'.join(f'{key}:\n{value}' for key, value in zip(MINIMAX_SECTIONS, values))


def ltx_prompt(text):
    """Remove legacy transport tags, not dialogue or chronological directions."""
    parts = minimax_sections(text)
    if parts:
        text = '\n\n'.join((parts['subject_definitions'], parts['detailed_description'],
                            'Audio: ' + parts['overall_soundscape'],
                            'Music: ' + parts['non_diegetic_music']))
    text = re.sub(r'\[/?VISUAL\]', '', text, flags=re.I)
    text = re.sub(r'\[SPEECH\]', 'Dialogue: ', text, flags=re.I)
    text = re.sub(r'\[SOUNDS\]', 'Sound: ', text, flags=re.I)
    text = re.sub(r'<d>(.*?)</d>', r'"\1"', text, flags=re.S)
    return re.sub(r'\[/(?:SPEECH|SOUNDS)\]', '', text, flags=re.I).strip()
