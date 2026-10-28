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
    from utils.prompt_templates import compose_system
    context = compose_system('MiniMax_References.txt', references=references) if references else compose_system('MiniMax_No_References.txt')
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
