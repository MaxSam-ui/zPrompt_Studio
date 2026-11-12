"""Carry explicit standalone restrictions through rewrites, without an LLM retry."""
import json
import re


def preserve_video_constraints(text, *sources):
    from utils.prompt_templates import system_template
    rules = json.loads(system_template('Video_Constraint_Phrases.json'))
    if not isinstance(rules, dict) or any(
            not isinstance(k, str) or not isinstance(v, list)
            or any(not isinstance(item, str) for item in v)
            for k, v in rules.items()):
        raise ValueError('Video_Constraint_Phrases.json must map output clauses to phrase lists.')
    def clauses(value):
        return {part.strip().casefold() for part in re.split(
            r'[.!?;,\n]+|\s+(?:and|e)\s+', str(value or ''), flags=re.I)}
    requested = set().union(*(clauses(source) for source in sources))
    existing = clauses(text)
    additions = []
    for output, phrases in rules.items():
        aliases = {p.strip().rstrip('.').casefold() for p in phrases}
        if requested & aliases and not existing & aliases and output.casefold() not in text.casefold():
            additions.append(output)
    return text.rstrip() + ('\n' + ' '.join(additions) if additions else '')
