# utils/timeline.py

import os
import html
import re  
import gradio as gr

from core import sessione, lingua


def _pulisci_scelta_ui(testo: str) -> str:
    """Rimuove prefissi e icone per non confondere l'LLM (es. '👤 [Shot] Close-up' -> 'Close-up')"""
    if not testo:
        return ""
    if "]" in testo:
        try:
            return testo.split("]", 1)[1].strip()
        except Exception:
            return testo
    return testo


def _mappa_valore_a_scelta_ui(valore: str, scelte_ui: list) -> str:
    """Mappa un valore grezzo alla stringa esatta ammessa dal dropdown Gradio."""
    if not valore:
        return scelte_ui[0] if scelte_ui else "-"
        
    valore_pulito = _pulisci_scelta_ui(valore).strip().lower()
    
    for scelta in scelte_ui:
        scelta_pulita = _pulisci_scelta_ui(scelta).strip().lower()
        if scelta_pulita == valore_pulito:
            return scelta
            
    for scelta in scelte_ui:
        scelta_pulita = _pulisci_scelta_ui(scelta).strip().lower()
        if valore_pulito in scelta_pulita or scelta_pulita in valore_pulito:
            return scelta
            
    return scelte_ui[0] if scelte_ui else "-"


def _safe_html_attr(valore: str) -> str:
    if not valore:
        return ""
    return html.escape(str(valore), quote=True)


def _pulisci_testo_grezzo_timeline(testo: str) -> str:
    if not testo:
        return ""
    t = re.sub(r'```(?:text|markdown)?', '', testo, flags=re.IGNORECASE)
    t = t.replace('```', '')
    
    match = re.search(r'\[\s*\d+(?:\.\d+)?\s*s?\s*-\s*\d+(?:\.\d+)?\s*s?\s*\]', t)
    if match:
        t = t[match.start():]
    return t.strip()


def _parse_timeline(testo: str) -> list:
    """
    Estrae con tolleranza universale gli spezzoni della timeline anche con prefissi (1. , Clip 1:, ecc.)
    generati da Qwen3-VL o altri modelli, garantendo la creazione delle schede editabili.
    """
    blocchi = []
    testo_pulito = _pulisci_testo_grezzo_timeline(testo)
    pattern_tempo = re.compile(r'\[\s*(\d+(?:\.\d+)?)\s*s?\s*-\s*(\d+(?:\.\d+)?)\s*s?\s*\]')
    
    for riga in testo_pulito.split("\n"):
        riga = riga.strip()
        if not riga:
            continue
            
        match = pattern_tempo.search(riga)
        if match:
            try:
                inizio = float(match.group(1))
                fine = float(match.group(2))
                dur = max(0.1, fine - inizio)
                
                # Prende tutto ciò che segue la chiusura della parentesi del timestamp
                dati_dopo_tempo = riga[match.end():].strip()
                dati_dopo_tempo = re.sub(r'^[\s:\-]+', '', dati_dopo_tempo).strip()
                
                if "|" in dati_dopo_tempo:
                    parti_dati = [p.strip() for p in dati_dopo_tempo.split("|", 3)]
                    blocchi.append({
                        "durata": dur,
                        "tipo": parti_dati[0],
                        "zoom": parti_dati[1] if len(parti_dati) > 1 else "",
                        "mov": parti_dati[2] if len(parti_dati) > 2 else "",
                        "audio": parti_dati[3] if len(parti_dati) > 3 else "",
                    })
                elif " - " in dati_dopo_tempo:
                    parti_dati = [p.strip() for p in dati_dopo_tempo.split(" - ", 3)]
                    blocchi.append({
                        "durata": dur,
                        "tipo": parti_dati[0],
                        "zoom": parti_dati[1] if len(parti_dati) > 1 else "",
                        "mov": parti_dati[2] if len(parti_dati) > 2 else "",
                        "audio": parti_dati[3] if len(parti_dati) > 3 else "",
                    })
            except Exception:
                pass
                    
    return blocchi


def _build_timeline_text(blocchi: list) -> str:
    tempo = 0.0
    righe = []
    for b in blocchi:
        fine = tempo + b["durata"]
        audio_val = f" | {b['audio']}" if b.get("audio") else ""
        righe.append(f"[{tempo:.1f}s - {fine:.1f}s] {b['tipo']} | {b['zoom']} | {b['mov']}{audio_val}")
        tempo = fine
    return "\n".join(righe)


def salva_timeline_sessione(testo_timeline: str, s: dict) -> None:
    s["lista_scene_salvate"] = testo_timeline
    sessione.salva_sessione({"lista_scene_salvate": testo_timeline})


def aggiungi_spezzone_testuale(sec, tipo, zoom, mov, audio, testo, s):
    durata = float(sec)
    audio_val = f" | {audio.strip()}" if audio.strip() else ""
    if testo.strip() == "":
        nuovo_testo = f"[0.0s - {durata:.1f}s] {tipo} | {zoom} | {mov}{audio_val}"
        salva_timeline_sessione(nuovo_testo, s)
        return nuovo_testo, "", ""

    blocchi = _parse_timeline(testo)
    blocchi.append({"durata": durata, "tipo": tipo, "zoom": zoom, "mov": mov, "audio": audio.strip()})
    risultato = _build_timeline_text(blocchi)
    salva_timeline_sessione(risultato, s)
    return risultato, "", ""


def rimuovi_ultimo_spezzone(testo, s):
    blocchi = _parse_timeline(testo)
    if not blocchi:
        salva_timeline_sessione("", s)
        return ""
    blocchi.pop()
    
    if not blocchi:
        salva_timeline_sessione("", s)
        return ""
    risultato = _build_timeline_text(blocchi)
    salva_timeline_sessione(risultato, s)
    return risultato


def svuota_timeline_completa(s):
    salva_timeline_sessione("", s)
    return "", "", ""


# Script esportato per js_helpers.py (evita AttributeError all'avvio)
js_setup_timeline_drag = """
() => {
    if (window._timeline_listener_attached) return;
    window._timeline_listener_attached = true;

    const PX_PER_SEC = 80;
    let isResizing = false;
    let startX = 0;
    let startWidth = 0;
    let currentCard = null;
    let handleActive = null;

    function setGradioInputValue(element, value) {
        if (!element) return;
        const proto = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
        if (descriptor && descriptor.set) {
            descriptor.set.call(element, value);
        } else {
            element.value = value;
        }
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
    }

    window.gestisciClickTimelineVisuale = function(azione, idx, btn) {
        if (azione === 'EDIT') {
            document.querySelectorAll('.timeline-visual-item').forEach(function(el) { el.classList.remove('editing'); });
            var card = btn ? btn.closest('.timeline-visual-item') : null;
            if (card) card.classList.add('editing');
        }
        var container = document.getElementById('hidden-timeline-trigger') || document.querySelector('#hidden-timeline-trigger');
        var trg = container ? (container.querySelector('textarea, input') || container) : null;
        if (trg) {
            setGradioInputValue(trg, azione + '_' + idx + '_' + Date.now());
        }
    };

    function ricalcolaTempiInTempoReale() {
        const cards = document.querySelectorAll('.timeline-visual-item');
        let accumulatedTime = 0.0;
        
        cards.forEach((card) => {
            const width = card.offsetWidth;
            const duration = Math.round((width / PX_PER_SEC) * 10) / 10;
            const end = accumulatedTime + duration;
            
            const pill = card.querySelector('.timeline-time-pill');
            if (pill) {
                pill.textContent = accumulatedTime.toFixed(1) + 's - ' + end.toFixed(1) + 's';
            }
            
            card.setAttribute('data-durata', duration.toFixed(1));
            accumulatedTime = end;
        });
    }

    function salvaTimelineInGradio() {
        const cards = document.querySelectorAll('.timeline-visual-item');
        let lines = [];
        let accumulatedTime = 0.0;
        
        cards.forEach(card => {
            const duration = parseFloat(card.getAttribute('data-durata'));
            const tipo = card.getAttribute('data-tipo');
            const zoom = card.getAttribute('data-zoom');
            const mov = card.getAttribute('data-mov') || '';
            const audio = card.getAttribute('data-audio') || '';
            
            const end = accumulatedTime + duration;
            const audio_val = audio ? ` | ${audio}` : '';
            lines.push(`[${accumulatedTime.toFixed(1)}s - ${end.toFixed(1)}s] ${tipo} | ${zoom} | ${mov}${audio_val}`);
            accumulatedTime = end;
        });
        
        const rawText = lines.join('\\n');
        const container = document.querySelector('#tabella-regia-view-textbox');
        const textarea = container ? (container.querySelector('textarea, input') || container) : null;
        if (textarea) {
            setGradioInputValue(textarea, rawText);
        }

        const dragContainer = document.querySelector('#durata-drag-trigger');
        const dragTrigger = dragContainer ? (dragContainer.querySelector('textarea, input') || dragContainer) : null;
        if (dragTrigger) {
            setGradioInputValue(dragTrigger, accumulatedTime.toFixed(1));
        }
    }

    document.addEventListener('mousedown', function(e) {
        if (e.target.classList.contains('timeline-resize-handle')) {
            e.preventDefault();
            isResizing = true;
            handleActive = e.target;
            handleActive.classList.add('active');
            currentCard = handleActive.closest('.timeline-visual-item');
            startX = e.clientX;
            startWidth = currentCard.offsetWidth;
        }
    });

    document.addEventListener('mousemove', function(e) {
        if (!isResizing || !currentCard) return;
        const dx = e.clientX - startX;
        let newWidth = startWidth + dx;
        
        if (newWidth < 40) newWidth = 40;
        
        currentCard.style.width = newWidth + 'px';
        ricalcolaTempiInTempoReale();
    });

    document.addEventListener('mouseup', function() {
        if (!isResizing) return;
        isResizing = false;
        if (handleActive) {
            handleActive.classList.remove('active');
        }
        currentCard = null;
        handleActive = null;
        
        salvaTimelineInGradio();
    });
}
"""


def compila_timeline_html(testo: str, audio_globale=None) -> str:
    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.ottieni_dizionario_lingua(lang)
    
    testo_pulito = _pulisci_testo_grezzo_timeline(testo)
    blocchi = _parse_timeline(testo_pulito)
    
    js_init_html = """
    <img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" style="display:none;" onload="
        window.gestisciClickTimelineVisuale = function(azione, idx, btn) {
            if (azione === 'EDIT') {
                document.querySelectorAll('.timeline-visual-item').forEach(function(el) { el.classList.remove('editing'); });
                var card = btn ? btn.closest('.timeline-visual-item') : null;
                if (card) card.classList.add('editing');
            }
            var container = document.getElementById('hidden-timeline-trigger') || document.querySelector('#hidden-timeline-trigger');
            var trg = container ? (container.querySelector('textarea, input') || container) : null;
            if (trg) {
                var val = azione + '_' + idx + '_' + Date.now();
                var proto = trg instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                var descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
                if (descriptor && descriptor.set) {
                    descriptor.set.call(trg, val);
                } else {
                    trg.value = val;
                }
                trg.dispatchEvent(new Event('input', { bubbles: true }));
                trg.dispatchEvent(new Event('change', { bubbles: true }));
            }
        };
    " />
    """

    # 1. SE SONO PRESENTI SPEZZONI VALIDI, MOSTRA SEMPRE LE SCHEDE IN TEMPO REALE
    if blocchi:
        tempo = 0.0
        cards_html = ""
        px_per_sec = 80
        
        icone_inquadratura = {
            "Close-up": "🔍", "Eye-Level Close-up": "👁️", "Extreme Close-up": "👁️", "Macro Shot": "🧬",
            "Medium Shot": "👤", "Full Body Shot": "🧍", "Wide Shot": "🗺️", "Establishing Shot": "🌇",
            "Low Angle Shot": "📐", "High Angle Shot": "🪜", "Worm's Eye View": "🔽", "Aerial Drone Shot": "🦅",
            "Dutch Angle Shot": "🌀", "Over-the-Shoulder Shot": "👥", "Point-of-View (POV) Shot": "👁️",
            "Cinematic 16:9 Widescreen": "📺", "Cinematic 9:16 Portrait": "📱"
        }
        
        icone_movimento = {
            "Static (No Zoom)": "⏹️", "Subtle Camera Drift / Operator Breathing": "💨", 
            "Slow Dolly Push-in": "⏩", "Slow Dolly Pull-out": "⏪", "Lateral Slider Move": "↔️",
            "Slow Zoom-in": "🔎", "Slow Zoom-out": "🔍", "Fast Zoom-in": "⚡", "Fast Zoom-out": "🌪️", 
            "Dynamic Dolly Zoom": "🚀", "Slow Pan Left": "◀️", "Slow Pan Right": "▶️", 
            "Slow Tilt Up": "🔼", "Slow Tilt Down": "🔽", "Tracking Follow Shot": "🏃", 
            "Snorricam / Bodycam Shot": "🎥", "Handheld Camera Shake": "🎛️"
        }
        
        for idx, b in enumerate(blocchi):
            fine = tempo + b["durata"]
            
            tipo_pulito = _pulisci_scelta_ui(b["tipo"])
            zoom_pulito = _pulisci_scelta_ui(b["zoom"])
            
            icon_t = icone_inquadratura.get(tipo_pulito, "📹")
            icon_m = icone_movimento.get(zoom_pulito, "🎬")
            desc = b["mov"].strip() if b["mov"] else "..."
            
            audio_val = b.get("audio", "").strip()
            audio_html = f'<div class="timeline-card-audio">🔊 {html.escape(audio_val)}</div>' if audio_val else ""
            
            width_px = max(40, int(b["durata"] * px_per_sec))
            
            safe_tipo = _safe_html_attr(b["tipo"])
            safe_zoom = _safe_html_attr(b["zoom"])
            safe_mov  = _safe_html_attr(desc)
            safe_audio = _safe_html_attr(audio_val)
            
            cards_html += f"""
            <div class="timeline-visual-item" data-idx="{idx}" data-durata="{b["durata"]:.1f}" data-tipo="{safe_tipo}" data-zoom="{safe_zoom}" data-mov="{safe_mov}" data-audio="{safe_audio}" style="width: {width_px}px;">
                <div class="timeline-visual-badge">
                    <span class="timeline-time-pill" id="time-pill-{idx}">{tempo:.1f}s - {fine:.1f}s</span>
                    <span class="timeline-index-pill">#{idx+1}</span>
                </div>
                <div class="timeline-visual-card">
                    <div class="timeline-card-actions">
                        <button class="timeline-card-btn-edit" data-idx="{idx}" title="✏️ Edit" onclick="event.preventDefault(); event.stopPropagation(); if(window.gestisciClickTimelineVisuale) window.gestisciClickTimelineVisuale('EDIT', {idx}, this);">✏️</button>
                        <button class="timeline-card-btn-delete" data-idx="{idx}" title="🗑️ Delete" onclick="event.preventDefault(); event.stopPropagation(); if(window.gestisciClickTimelineVisuale) window.gestisciClickTimelineVisuale('DELETE', {idx}, this);">🗑️</button>
                    </div>
                    <div class="timeline-card-header">
                        <span class="timeline-card-title">{icon_t} {tipo_pulito}</span>
                        <span class="timeline-card-meta">{icon_m} {zoom_pulito}</span>
                    </div>
                    <div class="timeline-card-desc">{desc}</div>
                    {audio_html}
                    <div class="timeline-resize-handle" data-idx="{idx}"></div>
                </div>
            </div>
            """
            tempo = fine
            
        max_secondi_righello = max(30, int(tempo) + 5)
        ruler_ticks_html = ""
        for sec in range(max_secondi_righello + 1):
            left_px = sec * px_per_sec
            ruler_ticks_html += f"""
            <div class="ruler-tick" style="left: {left_px}px;">
                <span class="ruler-tick-label">{sec}s</span>
            </div>
            """
            
        return f"""
        {js_init_html}
        <div class="timeline-scroll-container" style="position: relative; z-index: 5; pointer-events: auto;">
            <div class="timeline-visual-container">
                <div class="timeline-cards-track" id="timeline-track">
                    {cards_html}
                </div>
                <div class="timeline-ruler" style="width: {max_secondi_righello * px_per_sec}px;">
                    {ruler_ticks_html}
                </div>
            </div>
        </div>
        """

    # 2. SE NON CI SONO ANCORA SPEZZONI, MOSTRA IL RIQUADRO D'ATTESA O VUOTO
    is_loading = (
        "sceneggiatore ai" in testo_pulito.lower() or 
        "screenwriter" in testo_pulito.lower() or
        "ai all'opera" in testo_pulito.lower() or 
        "at work" in testo_pulito.lower() or 
        "scrittura" in testo_pulito.lower() or
        "writing" in testo_pulito.lower() or
        "caricamento" in testo_pulito.lower() or
        "elaborazione" in testo_pulito.lower() or
        "vlm" in testo_pulito.lower() or
        "regia" in testo_pulito.lower() or
        "🔄" in testo_pulito or
        "⏳" in testo_pulito or
        "llama-vision" in testo_pulito.lower() or
        "descrivo" in testo_pulito.lower() or
        "describing" in testo_pulito.lower() or
        testo_pulito.strip().startswith("...")
    )
    
    if is_loading:
        return f"""
        {js_init_html}
        <div style="text-align: center; padding: 28px; color: #3b82f6; font-style: italic; border: 1px dashed rgba(59, 130, 246, 0.3); border-radius: 8px; background: rgba(59, 130, 246, 0.05); margin-top: 10px; animation: pulseLavoro 1.8s infinite ease-in-out; position: relative; z-index: 5; pointer-events: auto;">
            ✍️ {testo_pulito}
        </div>
        """
        
    from services import comfyui_manager
    if comfyui_manager.generazione_attiva:
        messaggio_attesa = dl.get("script_writing_status", "Writing screenplay in progress...")
        return f"""
        {js_init_html}
        <div style="text-align: center; padding: 28px; color: #3b82f6; font-style: italic; border: 1px dashed rgba(59, 130, 246, 0.3); border-radius: 8px; background: rgba(59, 130, 246, 0.05); margin-top: 10px; animation: pulseLavoro 1.8s infinite ease-in-out; position: relative; z-index: 5; pointer-events: auto;">
            ✍️ {messaggio_attesa}
        </div>
        """
        
    msg_vuoto = dl.get("timeline_empty_msg", "Your timeline is empty. Configure and add the first clip below!")
    return f"""
    {js_init_html}
    <div style="text-align: center; padding: 28px; color: #64748b; font-style: italic; border: 1px dashed rgba(255,255,255,0.1); border-radius: 8px; background: rgba(0,0,0,0.15); margin-top: 10px; position: relative; z-index: 5; pointer-events: auto;">
        🎥 {msg_vuoto}
    </div>
    """