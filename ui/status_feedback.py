"""Safe, read-only presentation of status messages emitted by operations."""

import html
import re


def render_status_feedback(message, language="IT"):
    message = str(message or "").strip()
    copy_prefix = ""
    copy_match = re.match(r"^(\[[^\]]+\]\s*)(.*)$", message, flags=re.DOTALL)
    if copy_match:
        copy_prefix, message = copy_match.groups()
    from core import lingua
    from utils.status_translation import translate_status
    message = translate_status(message, language, lingua.LINGUE)
    message = message.replace("Current phase", "Fase corrente") if language == "IT" else message.replace("Fase corrente", "Current phase")
    english = language != "IT"
    if not message:
        message = "Waiting…" if english else "In attesa…"
    escaped = html.escape(copy_prefix + message)
    if message.startswith(("⏹", "🛑")):
        stopped = "⏹️ Stopped." if english else "⏹️ Generazione interrotta."
        return f'<div class="studio-feedback studio-feedback-warning" role="status">{stopped}</div>'
    if message.startswith("❌"):
        heading = "Operation failed" if english else "Operazione non riuscita"
        hint = ""
        if "offline" in message.lower():
            hint = ("Start ComfyUI and wait for it to become available before retrying."
                    if english else "Avvia ComfyUI e attendi che sia disponibile prima di riprovare.")
        return (f'<div class="studio-feedback studio-feedback-error" role="status">'
                f'<strong>{heading}</strong><div>{escaped}</div>'
                + (f'<small>{hint}</small>' if hint else '') + '</div>')
    if message.startswith(("⚠", "⏹", "🛑")):
        return f'<div class="studio-feedback studio-feedback-warning" role="status">{escaped}</div>'
    if message.startswith(("✅", "📸")):
        return f'<div class="studio-feedback studio-feedback-success" role="status">{escaped}</div>'
    match = re.search(r"(?<![\d.,])(\d{1,3}(?:[.,]\d+)?)\s*%", message)
    if match:
        percent = max(0, min(100, float(match.group(1).replace(",", "."))))
        phase_label = "Current phase" if english else "Fase corrente"
        if "Fase corrente" not in message and "Current phase" not in message:
            escaped = f"{phase_label} · {escaped}"
        if percent >= 100:
            pending = "Phase finished; processing continues…" if english else "Fase terminata; elaborazione ancora in corso…"
            escaped += f"<small>{pending}</small>"
        return (f'<div class="studio-feedback" role="status"><div>{escaped}</div>'
                f'<progress max="100" value="{percent}" aria-label="{html.escape(message)}"></progress></div>')
    return f'<div class="studio-feedback" role="status">{escaped}</div>'


def update_status_feedback(message):
    from core import sessione
    language = sessione.carica_ultima_sessione().get("lingua_selezionata", "EN")
    return render_status_feedback(message, language)
