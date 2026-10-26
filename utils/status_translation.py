"""Translate known UI status templates while preserving their runtime values."""
import re
import string


def translate_status(message, language, dictionaries):
    if not message:
        return message
    for phase_marker in (' · Fase corrente', ' · Current phase'):
        if phase_marker in message:
            prefix, phase = message.split(phase_marker, 1)
            label = ' · Fase corrente' if language == 'IT' else ' · Current phase'
            return translate_status(prefix, language, dictionaries) + label + phase
    target = dictionaries.get(language, {})
    for source in dictionaries.values():
        for key, template in source.items():
            translated = target.get(key)
            if not isinstance(template, str) or not isinstance(translated, str):
                continue
            if template == message:
                return translated
            if '{' not in template:
                continue
            try:
                parts = list(string.Formatter().parse(template))
                fields = []
                pattern = ''
                for literal, field, spec, conversion in parts:
                    pattern += re.escape(literal)
                    if field is not None:
                        if not field.isidentifier():
                            raise ValueError('Unsupported format')
                        if field in fields:
                            pattern += f'(?P={field})'
                        else:
                            pattern += f'(?P<{field}>.*?)'
                            fields.append(field)
                match = re.fullmatch(pattern, message, flags=re.DOTALL)
                if match:
                    # Values are already rendered (for example a duration with .1f).
                    # Preserve them instead of formatting captured strings as numbers.
                    values = match.groupdict()
                    return ''.join(literal + (values[field] if field is not None else '')
                                   for literal, field, _, _ in string.Formatter().parse(translated))
            except (ValueError, KeyError):
                continue
    return message
