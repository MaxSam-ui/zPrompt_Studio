"""Keep timeline intervals and selected framing authoritative in AI direction."""
import re
import math

TIMECODE = re.compile(r'\[\s*(\d+(?:\.\d+)?)\s*s?\s*-\s*(\d+(?:\.\d+)?)\s*s?\s*\]')


def align_numbered_clips(text, scenes):
    """Attach application-owned times to translated, explicitly identified clips.

    Never infer clip boundaries from prose or copy untranslated source actions.
    Legacy timed output remains supported by the existing strict aligner.
    """
    markers = list(re.finditer(r'^\s*\[\[CLIP_(\d+)\]\][ \t]*', text, re.M))
    if not markers:
        return align_director_prompt(text, scenes)
    if [int(m[1]) for m in markers] != list(range(1, len(scenes) + 1)):
        return None
    prefix = text[:markers[0].start()].strip()
    if TIMECODE.search(prefix):
        return None
    output = [prefix] if prefix else []
    elapsed = 0.0
    for i, (marker, scene) in enumerate(zip(markers, scenes)):
        limit = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        body = text[marker.end():limit].strip()
        # A model may redundantly echo the source interval after the ID.
        body = TIMECODE.sub('', body, count=1).strip() if TIMECODE.match(body) else body
        duration = float(scene[0])
        if not body or TIMECODE.search(body) or not math.isfinite(duration) or duration <= 0:
            return None
        end = elapsed + duration
        output.append(f'[{elapsed:.1f}s - {end:.1f}s] [{scene[1]}; {scene[2]}] {body}')
        elapsed = end
    return '\n'.join(output)


def align_director_prompt(text, scenes):
    if not text.strip() or not scenes:
        return None
    # Accept typographic variants without relaxing the clip/duration checks.
    text = re.sub(r'\[\s*(\d+(?:[.,]\d+)?)\s*(?:s|sec|seconds)?\s*[-–—−]\s*(\d+(?:[.,]\d+)?)\s*(?:s|sec|seconds)?\s*\]',
                  lambda m: m[0] if TIMECODE.fullmatch(m[0]) else '[' + m[1].replace(',', '.') + 's-' + m[2].replace(',', '.') + 's]', text, flags=re.I)
    matches = list(TIMECODE.finditer(text))
    if not matches and len(scenes) == 1:
        text = f'[0.0s - {float(scenes[0][0]):.1f}s] ' + text
        matches = list(TIMECODE.finditer(text))
    if len(matches) != len(scenes):
        return None
    previous = 0.0
    generated_end = 0.0
    spans = []
    for index, (match, scene) in enumerate(zip(matches, scenes)):
        duration = float(scene[0])
        end = previous + duration
        start, stop = float(match[1]), float(match[2])
        # One continuous, ordered span per scene can be retimed locally. The
        # timeline owns timing; an LLM's rounded durations must not trigger a
        # second generation. Ambiguous/missing/reordered spans still need repair.
        if (not math.isfinite(duration) or duration <= 0
                or not math.isfinite(stop) or stop <= start
                or abs(start - generated_end) > .15):
            return None
        limit = matches[index+1].start() if index+1 < len(matches) else len(text)
        body = text[match.end():limit].strip()
        if not body:
            return None
        # Framing often disappears in otherwise correct generated prose. The
        # timeline's explicit choices must reach the video model in every span.
        spans.append(f'[{previous:.1f}s - {end:.1f}s] [{scene[1]}; {scene[2]}] {body}')
        previous = end
        generated_end = stop
    prefix = text[:matches[0].start()].strip()
    body = '\n'.join(spans)
    # Downstream sanitizing/preflight split the subject at a blank line. Keep
    # that boundary explicit even when the model returns only one newline.
    return prefix + '\n\n' + body if prefix else body


def preserve_identity_tokens(text, source):
    tokens = dict.fromkeys(re.findall(r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b", source or ""))
    missing = [token for token in tokens if not re.search(r"(?<!\w)" + re.escape(token) + r"(?!\w)", text)]
    return text + ("\nIdentity references: " + ", ".join(missing) + "." if missing else "")


def finalize_director_subject(compiled, subject, fallback=False):
    """Do not reinsert untranslated input after a successful English compile."""
    if not subject:
        return compiled
    if fallback:
        # Source-only recovery intentionally preserves the user's exact details.
        return "Subject and scene: " + " ".join(subject.split()) + "\n\n" + compiled
    return preserve_identity_tokens(compiled, subject)


def timeline_fallback_prompt(scenes, subject="", frame_context="", audio=""):
    """Use only supplied source material when the model cannot preserve clip boundaries."""
    parts = [part.strip() for part in (subject, frame_context) if part and part.strip()]
    elapsed = 0.0
    for scene in scenes:
        end = elapsed + float(scene[0])
        action = str(scene[3] or "").strip()
        sound = str(scene[4] or "").strip() if len(scene) > 4 else ""
        parts.append(f"[{elapsed:.1f}s - {end:.1f}s] [{scene[1]}; {scene[2]}] {action}" + (f" Audio: {sound}" if sound else ""))
        elapsed = end
    if audio and audio.strip():
        parts.append("Audio: " + audio.strip())
    return "\n".join(parts)
