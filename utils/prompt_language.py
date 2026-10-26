"""Output-language rules for visual prompts, independent of the UI language."""

ENGLISH_VISUAL_OUTPUT = """OUTPUT LANGUAGE: English.
The source description and requested changes may be written in any language.
Translate all visual and technical descriptions into English. Do not mirror the
language of the input. Return only the complete resulting prompt in the required
format, without commentary or a translation preface.
Preserve proper names, identity identifiers, literal model/LoRA trigger words,
timecodes and structural tags. Keep explicitly requested lettering, quotations
and spoken dialogue in their requested language. These exceptions do not change
the language of the surrounding visual description.
For refinement, retain all unaffected scene facts and apply only the requested
changes; translating the description must not invent or remove scene details."""


def english_visual_request(system, user):
    return ((system or '').strip() + '\n\n' + ENGLISH_VISUAL_OUTPUT,
            (user or '').strip() + '\n\n' + ENGLISH_VISUAL_OUTPUT)
