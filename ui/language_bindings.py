"""Complete language updates for static UI properties absent from tab callbacks."""
import gradio as gr
from gradio.context import get_blocks_context
from core import lingua
from ui.status_feedback import render_status_feedback


def connect_remaining_labels(event, language_selector, dashboard):
    context = get_blocks_context()
    owned = set()
    for dependency in context.fns.values():
        if getattr(dependency.fn, '__module__', '') == 'core.lingua':
            owned.update(component._id for component in dependency.outputs)
    reverse = {}
    for dictionary in lingua.LINGUE.values():
        for key, text in dictionary.items():
            if isinstance(text, str) and text:
                reverse.setdefault(text, key)
    bindings = []
    for component in list(context.blocks.values()):
        props = {}
        for prop in ('label', 'info', 'placeholder'):
            if prop == 'label' and component._id in owned:
                continue
            value = getattr(component, prop, None)
            if isinstance(value, str) and value in reverse:
                props[prop] = reverse[value]
        if isinstance(component, (gr.Markdown, gr.Button)) and component._id not in owned:
            value = getattr(component, 'value', None)
            if isinstance(value, str) and value in reverse:
                props['value'] = reverse[value]
        choices = None
        if isinstance(component, (gr.Dropdown, gr.Radio)) and component._id not in owned:
            original = component.choices or []
            if any(label in reverse for label, _ in original):
                choices = [(reverse.get(label), label, value) for label, value in original]
        if props or choices:
            bindings.append((component, props, choices))
    statuses = [c for c in context.blocks.values() if hasattr(c, '_studio_feedback')]

    def refresh(lang, *messages):
        d = lingua.ottieni_dizionario_lingua(lang)
        updates = []
        for _, props, choices in bindings:
            values = {prop: d[key] for prop, key in props.items() if key in d}
            if choices:
                values['choices'] = [(d.get(key, label), value) for key, label, value in choices]
            updates.append(gr.update(**values))
        from ui.tab_log import compila_dashboard_modelli_html
        updates.append(compila_dashboard_modelli_html())
        for message in messages:
            key = reverse.get(message or '')
            localized = d.get(key, message) if message else d.get('in_attesa', '')
            updates.append(render_status_feedback(localized, lang))
        return updates

    event.then(refresh, inputs=[language_selector, *statuses],
               outputs=[*[c for c, _, _ in bindings], dashboard, *[c._studio_feedback for c in statuses]],
               show_progress='hidden')
