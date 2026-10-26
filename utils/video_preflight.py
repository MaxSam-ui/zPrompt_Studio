"""Cheap checks performed before loading models or submitting a workflow."""
import math
import re


def validate_video_request(prompt, duration, english=False):
    if not str(prompt or '').strip():
        return ('❌ Enter or create a video prompt before generating.' if english else
                '❌ Inserisci o crea il prompt video prima di generare.')
    try:
        seconds = float(duration)
    except (TypeError, ValueError):
        seconds = 0
    if not math.isfinite(seconds) or seconds <= 0:
        return ('❌ Set a valid video duration greater than zero.' if english else
                '❌ Imposta una durata video valida maggiore di zero.')
    timing_text = str(prompt)
    if timing_text.startswith('Subject and scene: ') and '\n\n' in timing_text:
        timing_text = timing_text.split('\n\n', 1)[1]
    spans = re.findall(r'\[\s*(\d+(?:[.,]\d+)?)\s*(?:s|sec|seconds)?\s*[-–—−]\s*(\d+(?:[.,]\d+)?)\s*(?:s|sec|seconds)?\s*\]', timing_text, flags=re.I)
    if spans:
        end = 0.0
        for start, stop in spans:
            start, stop = float(start.replace(',', '.')), float(stop.replace(',', '.'))
            if abs(start - end) > .15 or stop <= start:
                return ('❌ Prompt timecodes overlap or have gaps. Recreate the video prompt from the timeline.' if english else
                        '❌ I tempi del prompt si sovrappongono o hanno intervalli vuoti. Ricrea il prompt video dalla timeline.')
            end = stop
        if abs(end - seconds) > .15:
            return (f'❌ The prompt covers {end:g}s, but the video requires {seconds:g}s. Align the timeline or recreate the video prompt.' if english else
                    f'❌ Il prompt copre {end:g}s, ma il video richiede {seconds:g}s. Allinea la timeline oppure ricrea il prompt video.')
    return None
