"""Model-specific chat options without changing user or system instructions."""


def format_model_chat(processor, messages, model_name):
    options = dict(tokenize=False, add_generation_prompt=True)
    if any(family in str(model_name).lower() for family in ('qwen3.5', 'qwen3.8')):
        # Qwen3.5/3.8 default to an open thinking block. Studio needs the final
        # artifact within its generation budget, including for image prompts.
        options['enable_thinking'] = False
    return processor.apply_chat_template(messages, **options)
