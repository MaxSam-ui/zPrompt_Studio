"""Describe node progress without presenting it as whole-workflow completion."""

def phase_progress(data):
    if isinstance(data, dict):
        percent = data.get('percent', 0)
        phase = data.get('phase')
    else:
        percent, phase = data, None
    from core import sessione
    english = sessione.carica_ultima_sessione().get('lingua_selezionata', 'IT') != 'IT'
    label = 'Current phase' if english else 'Fase corrente'
    return f"{percent}% · {label}" + (f": {phase}" if phase else "")
