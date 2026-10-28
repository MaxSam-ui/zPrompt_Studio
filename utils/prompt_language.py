from utils.prompt_templates import system_template
"""Output-language rules for visual prompts, independent of the UI language."""

def output_language():
    return system_template('Output_Language.txt', allow_empty=True)


def english_visual_request(system, user):
    rule = output_language()
    return ((system or '').strip() + '\n\n' + rule,
            (user or '').strip() + '\n\n' + rule)
