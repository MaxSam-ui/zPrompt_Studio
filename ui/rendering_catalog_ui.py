# ui/rendering_catalog_ui.py

import gradio as gr
from typing import Dict, Any

from services import catalog_manager, local_vlm
from core import sessione, lingua
from utils.catalog_prompt import assemble_catalog_prompt, bounded_count, is_empty_choice


def _catalog_labels():
    lang = sessione.carica_ultima_sessione().get("lingua_selezionata", "IT")
    d = lingua.LINGUE.get(lang, lingua.LINGUE["IT"])
    return d["nessuno_catalogo"], d["default_preset_catalogo"], d["nuovo_elemento_catalogo"]


def _trova_valore_valido(val_salvato, scelte, default_label):
    if val_salvato is None:
        return default_label
    if is_empty_choice(val_salvato):
        return scelte[0]
    return val_salvato  # Dropdowns explicitly allow custom descriptions.


def crea_sezione_catalogo(
    d: Dict[str, str],
    s: Dict[str, Any],
    mode_iniziale: str,
    prompt_to_send_img: gr.Textbox,
    selettore_sequenza_scatti: gr.Slider = None,
    dropdown_model: gr.Dropdown = None
) -> Dict[str, Any]:
    """Crea la sezione Catalogo Cast & Scenografia gestita da menu a tendina e layout orizzontale compatto."""
    
    preset_seq_iniziale = s.get("suggerimento_sequenza_selezionato", "-")
    diz_personaggi = catalog_manager.carica_catalogo("Personaggio", genere=preset_seq_iniziale)
    diz_outfits = catalog_manager.carica_catalogo("Outfit/Location", genere=preset_seq_iniziale)
    diz_azioni = catalog_manager.carica_catalogo("Azione", genere=preset_seq_iniziale)

    label_nessuno = d.get("nessuno_catalogo", "- Nessuno -")
    label_default_preset = d.get("default_preset_catalogo", "- Default Preset -")
    label_nuovo_elemento = d.get("nuovo_elemento_catalogo", "- Nuovo Elemento -")

    scelte_personaggi = [label_nessuno] + list(diz_personaggi.keys())
    scelte_outfits = [label_default_preset] + list(diz_outfits.keys())
    scelte_azioni = [label_nessuno] + list(diz_azioni.keys())

    num_soggetti_seq = gr.State(value=s.get("soggetti_visibili_count", 1))
    num_azioni_seq = gr.State(value=s.get("azioni_visibili_count", 1))

    is_seq_init = ("sequenza" in str(mode_iniziale).lower() or "sequence" in str(mode_iniziale).lower())

    is_story_init = "storyboard" in str(mode_iniziale).lower()
    limite_azioni_catalogo = gr.State(value=bounded_count(s.get("storyboard_pannelli", 3), 4) if is_story_init else bounded_count(s.get("sequenza_num_scatti", 5)))

    # Voci del menu a tendina
    scelta_principale = d.get("vista_selettore_rapido", "🎬 Selettore & Assemblaggio Rapido")
    scelta_gestione = d.get("vista_gestione_catalogo", "✏️ Gestione & Modifica Catalogo")
    scelta_estrazione = d.get("vista_estrazione_ai", "🧠 Estrazione Asset con AI (da Prompt)")

    # ACCORDION PRINCIPALE
    with gr.Accordion(
        d.get("box_catalogo_sequenza_label", "🎭 Catalogo Cast & Scenografia"), 
        open=is_seq_init or is_story_init, 
        visible=is_seq_init or is_story_init
    ) as box_catalogo_sequenza:
        
        # MENU A TENDINA PER SELEZIONARE LA MODALITÀ (PARTE SEMPRE DALLA PRINCIPALE)
        dd_vista_catalogo = gr.Dropdown(
            choices=[scelta_principale, scelta_gestione, scelta_estrazione],
            value=scelta_principale,
            label=d.get("selettore_vista_label", "📂 Vista / Modalità Catalogo"),
            allow_custom_value=False,
            interactive=True
        )

        # =====================================================================
        # 1. MODALITÀ PRINCIPALE: SELETTORE RAPIDO & ASSEMBLAGGIO
        # =====================================================================
        with gr.Group(visible=True) as col_selettore_rapido:
            gr.Markdown(d["catalog_sequence_help"])
            gr.Markdown(d["catalog_cast_title"])
            default_s1 = label_nessuno
            s1_val = _trova_valore_valido(s.get("dd_soggetto_1"), scelte_personaggi, default_s1)
            s2_val = _trova_valore_valido(s.get("dd_soggetto_2"), scelte_personaggi, label_nessuno)
            s3_val = _trova_valore_valido(s.get("dd_soggetto_3"), scelte_personaggi, label_nessuno)
            s4_val = _trova_valore_valido(s.get("dd_soggetto_4"), scelte_personaggi, label_nessuno)
            s5_val = _trova_valore_valido(s.get("dd_soggetto_5"), scelte_personaggi, label_nessuno)

            with gr.Row(variant="compact"):
                dd_soggetto_1 = gr.Dropdown(choices=scelte_personaggi, value=s1_val, label=d.get("dd_soggetto_1_label", "Soggetto 1"), allow_custom_value=True, min_width=120, scale=1)
                dd_soggetto_2 = gr.Dropdown(choices=scelte_personaggi, value=s2_val, label=d.get("dd_soggetto_2_label", "Soggetto 2"), visible=(s.get("soggetti_visibili_count", 1) >= 2), allow_custom_value=True, min_width=120, scale=1)
                dd_soggetto_3 = gr.Dropdown(choices=scelte_personaggi, value=s3_val, label=d.get("dd_soggetto_3_label", "Soggetto 3"), visible=(s.get("soggetti_visibili_count", 1) >= 3), allow_custom_value=True, min_width=120, scale=1)

            with gr.Row(variant="compact"):
                dd_soggetto_4 = gr.Dropdown(choices=scelte_personaggi, value=s4_val, label=d.get("dd_soggetto_4_label", "Soggetto 4"), visible=(s.get("soggetti_visibili_count", 1) >= 4), allow_custom_value=True, min_width=120, scale=1)
                dd_soggetto_5 = gr.Dropdown(choices=scelte_personaggi, value=s5_val, label=d.get("dd_soggetto_5_label", "Soggetto 5"), visible=(s.get("soggetti_visibili_count", 1) == 5), allow_custom_value=True, min_width=120, scale=1)

            with gr.Row(variant="compact"):
                btn_add_soggetto = gr.Button(d.get("btn_add_soggetto", "➕ Aggiungi Soggetto"), size="sm", variant="secondary", scale=1)
                btn_rem_soggetto = gr.Button(d.get("btn_rem_soggetto", "➖ Rimuovi Soggetto"), size="sm", variant="secondary", scale=1)

            gr.Markdown(d["catalog_outfit_title"])
            out_val = _trova_valore_valido(s.get("dd_outfit_location"), scelte_outfits, label_default_preset)
            dd_outfit_location = gr.Dropdown(choices=scelte_outfits, value=out_val, label=d.get("dd_outfit_location_label", "Outfit & Location"), allow_custom_value=True)

            gr.Markdown(d["catalog_actions_title"])
            a1_val = _trova_valore_valido(s.get("dd_azione_1"), scelte_azioni, label_nessuno)
            a2_val = _trova_valore_valido(s.get("dd_azione_2"), scelte_azioni, label_nessuno)
            a3_val = _trova_valore_valido(s.get("dd_azione_3"), scelte_azioni, label_nessuno)
            a4_val = _trova_valore_valido(s.get("dd_azione_4"), scelte_azioni, label_nessuno)
            a5_val = _trova_valore_valido(s.get("dd_azione_5"), scelte_azioni, label_nessuno)

            with gr.Row(variant="compact"):
                dd_azione_1 = gr.Dropdown(choices=scelte_azioni, value=a1_val, label=d.get("scatto_1_azione_label", "Scatto 1: Azione"), visible=True, allow_custom_value=True, min_width=120, scale=1)
                dd_azione_2 = gr.Dropdown(choices=scelte_azioni, value=a2_val, label=d.get("scatto_2_azione_label", "Scatto 2: Azione"), visible=(s.get("azioni_visibili_count", 1) >= 2), allow_custom_value=True, min_width=120, scale=1)
                dd_azione_3 = gr.Dropdown(choices=scelte_azioni, value=a3_val, label=d.get("scatto_3_azione_label", "Scatto 3: Azione"), visible=(s.get("azioni_visibili_count", 1) >= 3), allow_custom_value=True, min_width=120, scale=1)

            with gr.Row(variant="compact"):
                dd_azione_4 = gr.Dropdown(choices=scelte_azioni, value=a4_val, label=d.get("scatto_4_azione_label", "Scatto 4: Azione"), visible=(s.get("azioni_visibili_count", 1) >= 4), allow_custom_value=True, min_width=120, scale=1)
                dd_azione_5 = gr.Dropdown(choices=scelte_azioni, value=a5_val, label=d.get("scatto_5_azione_label", "Scatto 5: Azione"), visible=(s.get("azioni_visibili_count", 1) == 5), allow_custom_value=True, min_width=120, scale=1)

            with gr.Row(variant="compact"):
                btn_add_azione = gr.Button(d["btn_add_azione"], size="sm", variant="secondary", elem_classes=["btn-azione-custom"], scale=1)
                btn_rem_azione = gr.Button(d["btn_rem_azione"], size="sm", variant="secondary", elem_classes=["btn-azione-custom"], scale=1)

            with gr.Row():
                btn_assembla_da_catalogo = gr.Button(d.get("btn_assembla_da_catalogo", "🪄 Assembla Idea dal Catalogo"), variant="primary", size="md", scale=1)

        # =====================================================================
        # 2. MODALITÀ: GESTIONE & MODIFICA CATALOGO
        # =====================================================================
        with gr.Group(visible=False) as col_gestione_catalogo:
            gr.Markdown(d.get("titolo_gestione_catalogo", "#### ➕ / ✏️ Salva, Modifica o Elimina Elementi dal Catalogo"))
            
            with gr.Row(variant="compact"):
                dd_tipo_salvataggio = gr.Dropdown(
                    choices=[d.get("tipo_personaggio", "Personaggio"), d.get("tipo_outfit", "Outfit/Location"), d.get("tipo_azione", "Azione")], 
                    value=d.get("tipo_personaggio", "Personaggio"), 
                    label=d.get("dd_tipo_salvataggio_label", "Tipo Elemento"), 
                    allow_custom_value=True, scale=1
                )
                dd_seleziona_esistente = gr.Dropdown(
                    choices=[label_nuovo_elemento] + list(diz_personaggi.keys()), 
                    value=label_nuovo_elemento, 
                    label=d.get("dd_seleziona_esistente_label", "Seleziona Elemento da Modificare"), 
                    allow_custom_value=True, scale=2
                )
            
            txt_nome_catalogo = gr.Textbox(
                label=d.get("txt_nome_catalogo_label", "Nome Breve / Etichetta"), 
                placeholder=d.get("placeholder_nome_catalogo", "Es. Detective Vintage, Terrazza Notturna...")
            )
            txt_desc_catalogo = gr.Textbox(
                label=d.get("txt_desc_catalogo_label", "Descrizione Prompt Completa (Inglese)"), 
                placeholder=d.get("placeholder_desc_catalogo", "Descrizione visiva dettagliata per l'IA..."), 
                lines=3
            )
            
            with gr.Row(variant="compact"):
                btn_salva_catalogo = gr.Button(d.get("btn_salva_catalogo", "💾 Salva / Aggiorna Catalogo"), variant="primary", scale=2)
                btn_elimina_catalogo = gr.Button(d.get("btn_elimina_catalogo", "🗑️ Elimina Elemento"), variant="stop", scale=1)
            
            lbl_stato_catalogo = gr.Markdown(value="", visible=True)

        # =====================================================================
        # 3. MODALITÀ: ESTRAZIONE ASSET CON AI (LAYOUT ORIZZONTALE A 3 ELEMENTI)
        # =====================================================================
        with gr.Group(visible=False) as col_estrazione_ai:
            gr.Markdown(d.get("titolo_estrazione_ai", "#### 🧠 Estrai Asset da Prompt Corrente"))
            with gr.Row():
                btn_estrai_vlm = gr.Button(d.get("btn_estrai_vlm_label", "🧠 Estrai e Separa Asset dal Prompt Corrente"), variant="secondary", scale=1)
            
            lbl_stato_estrazione = gr.Markdown(value="", visible=True)

            # RIGA 1: PERSONAGGIO (DESCRIZIONE | NOME PERSONAGGIO | ICONA SALVA)
            with gr.Row(variant="compact"):
                txt_ext_char = gr.Textbox(
                    label=d.get("txt_ext_char_label", "👤 Personaggio Estratto"), 
                    placeholder=d.get("placeholder_desc_char", "Descrizione del personaggio..."), 
                    lines=2,
                    scale=4
                )
                txt_ext_char_name = gr.Textbox(
                    label=d.get("nome_char_salvataggio_label", "👤 Nome Personaggio"), 
                    placeholder=d.get("placeholder_nome_char", "Es. Detective..."),
                    lines=2,
                    scale=2
                )
                btn_save_ext_char = gr.Button(
                    "💾", 
                    variant="primary", 
                    size="sm",
                    scale=0,
                    min_width=50
                )

            # RIGA 2: OUTFIT (DESCRIZIONE | NOME OUTFIT | ICONA SALVA)
            with gr.Row(variant="compact"):
                txt_ext_outfit = gr.Textbox(
                    label=d.get("txt_ext_outfit_label", "👗 Outfit & Ambiente Estratto"), 
                    placeholder=d.get("placeholder_desc_outfit", "Descrizione vestiti e location..."), 
                    lines=2,
                    scale=4
                )
                txt_ext_outfit_name = gr.Textbox(
                    label=d.get("nome_outfit_salvataggio_label", "👗 Nome Outfit"), 
                    placeholder=d.get("placeholder_nome_outfit", "Es. Abito Notturno..."),
                    lines=2,
                    scale=2
                )
                btn_save_ext_outfit = gr.Button(
                    "💾", 
                    variant="primary", 
                    size="sm",
                    scale=0,
                    min_width=50
                )

            # RIGA 3: AZIONE (DESCRIZIONE | NOME AZIONE | ICONA SALVA)
            with gr.Row(variant="compact"):
                txt_ext_act = gr.Textbox(
                    label=d.get("txt_ext_act_label", "🎬 Azione Estratta"), 
                    placeholder=d.get("placeholder_desc_act", "Descrizione posa/azione..."), 
                    lines=2,
                    scale=4
                )
                txt_ext_act_name = gr.Textbox(
                    label=d.get("nome_act_salvataggio_label", "🎬 Nome Azione"), 
                    placeholder=d.get("placeholder_nome_act", "Es. Sguardo Intenso..."),
                    lines=2,
                    scale=2
                )
                btn_save_ext_act = gr.Button(
                    "💾", 
                    variant="primary", 
                    size="sm",
                    scale=0,
                    min_width=50
                )

    # =========================================================================
    # LOGICA COMMUTAZIONE VISTA ISTANTANEA
    # =========================================================================
    def cambia_vista_dropdown(scelta):
        s_low = str(scelta).lower()
        v_estrazione = ("estraz" in s_low or "extract" in s_low)
        v_gestione = ("gestion" in s_low or "manag" in s_low or "modifica" in s_low or "edit" in s_low)
        v_principale = not v_estrazione and not v_gestione
        return gr.update(visible=v_principale), gr.update(visible=v_gestione), gr.update(visible=v_estrazione)

    dd_vista_catalogo.change(
        fn=cambia_vista_dropdown,
        inputs=[dd_vista_catalogo],
        outputs=[col_selettore_rapido, col_gestione_catalogo, col_estrazione_ai]
    )

    # =========================================================================
    # EVENTI E LOGICA CONTROLLI
    # =========================================================================
    def gestisci_aggiunta_soggetto(count):
        nuovo_count = min(count + 1, 5)
        sessione.salva_sessione({"soggetti_visibili_count": nuovo_count})
        return nuovo_count, gr.update(visible=(nuovo_count >= 2)), gr.update(visible=(nuovo_count >= 3)), gr.update(visible=(nuovo_count >= 4)), gr.update(visible=(nuovo_count == 5))

    def gestisci_rimozione_soggetto(count):
        label_nessuno, label_default_preset, label_nuovo_elemento = _catalog_labels()
        nuovo_count = max(count - 1, 1)
        updates = {"soggetti_visibili_count": nuovo_count}
        if nuovo_count < 5: updates["dd_soggetto_5"] = label_nessuno
        if nuovo_count < 4: updates["dd_soggetto_4"] = label_nessuno
        if nuovo_count < 3: updates["dd_soggetto_3"] = label_nessuno
        if nuovo_count < 2: updates["dd_soggetto_2"] = label_nessuno
        sessione.salva_sessione(updates)

        u2 = gr.update(visible=False, value=label_nessuno) if nuovo_count < 2 else gr.update(visible=True)
        u3 = gr.update(visible=False, value=label_nessuno) if nuovo_count < 3 else gr.update(visible=True)
        u4 = gr.update(visible=False, value=label_nessuno) if nuovo_count < 4 else gr.update(visible=True)
        u5 = gr.update(visible=False, value=label_nessuno) if nuovo_count < 5 else gr.update(visible=True)

        return nuovo_count, u2, u3, u4, u5

    btn_add_soggetto.click(fn=gestisci_aggiunta_soggetto, inputs=[num_soggetti_seq], outputs=[num_soggetti_seq, dd_soggetto_2, dd_soggetto_3, dd_soggetto_4, dd_soggetto_5])
    btn_rem_soggetto.click(fn=gestisci_rimozione_soggetto, inputs=[num_soggetti_seq], outputs=[num_soggetti_seq, dd_soggetto_2, dd_soggetto_3, dd_soggetto_4, dd_soggetto_5])

    def gestisci_aggiunta_azione(count_az, max_scatti):
        try:
            limite_max = int(max_scatti)
        except Exception:
            limite_max = 5
        nuovo_count = min(count_az + 1, max(1, min(5, limite_max)))
        sessione.salva_sessione({"azioni_visibili_count": nuovo_count})
        return (
            nuovo_count,
            gr.update(visible=(nuovo_count >= 2)),
            gr.update(visible=(nuovo_count >= 3)),
            gr.update(visible=(nuovo_count >= 4)),
            gr.update(visible=(nuovo_count == 5))
        )

    def gestisci_rimozione_azione(count_az):
        label_nessuno, label_default_preset, label_nuovo_elemento = _catalog_labels()
        nuovo_count = max(count_az - 1, 1)
        updates = {"azioni_visibili_count": nuovo_count}
        if nuovo_count < 5: updates["dd_azione_5"] = label_nessuno
        if nuovo_count < 4: updates["dd_azione_4"] = label_nessuno
        if nuovo_count < 3: updates["dd_azione_3"] = label_nessuno
        if nuovo_count < 2: updates["dd_azione_2"] = label_nessuno
        sessione.salva_sessione(updates)

        u2 = gr.update(visible=False, value=label_nessuno) if nuovo_count < 2 else gr.update(visible=True)
        u3 = gr.update(visible=False, value=label_nessuno) if nuovo_count < 3 else gr.update(visible=True)
        u4 = gr.update(visible=False, value=label_nessuno) if nuovo_count < 4 else gr.update(visible=True)
        u5 = gr.update(visible=False, value=label_nessuno) if nuovo_count < 5 else gr.update(visible=True)

        return nuovo_count, u2, u3, u4, u5

    inputs_add_azione = [num_azioni_seq, limite_azioni_catalogo]

    btn_add_azione.click(fn=gestisci_aggiunta_azione, inputs=inputs_add_azione, outputs=[num_azioni_seq, dd_azione_2, dd_azione_3, dd_azione_4, dd_azione_5])
    btn_rem_azione.click(fn=gestisci_rimozione_azione, inputs=[num_azioni_seq], outputs=[num_azioni_seq, dd_azione_2, dd_azione_3, dd_azione_4, dd_azione_5])

    def adatta_azioni_a_modalita(mode, frames, shots, current_count):
        limit = bounded_count(frames, 4) if "storyboard" in str(mode).lower() else bounded_count(shots)
        count = min(bounded_count(current_count), limit)
        sessione.salva_sessione({"azioni_visibili_count": count})
        updates = [gr.update(visible=count >= index) for index in range(2, 6)]
        return limit, count, *updates

    # Estrazione Asset da Prompt
    btn_estrai_vlm.click(
        fn=local_vlm.estrai_asset_da_prompt,
        inputs=[prompt_to_send_img],
        outputs=[txt_ext_char, txt_ext_outfit, txt_ext_act, lbl_stato_estrazione]
    )

    def _salva_rapido_estratto(tipo, nome, desc):
        label_nessuno, label_default_preset, label_nuovo_elemento = _catalog_labels()
        if not nome or not desc:
            return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), "⚠️ Please fill both name and description."
        
        preset_corrente = sessione.carica_ultima_sessione().get("suggerimento_sequenza_selezionato", "-")
        catalog_manager.salva_elemento_catalogo(tipo, nome, desc, genere=preset_corrente)
        diz_char = catalog_manager.carica_catalogo("Personaggio", genere=preset_corrente)
        diz_out = catalog_manager.carica_catalogo("Outfit/Location", genere=preset_corrente)
        diz_act = catalog_manager.carica_catalogo("Azione", genere=preset_corrente)
        
        scelte_char = [label_nessuno] + list(diz_char.keys())
        scelte_out = [label_default_preset] + list(diz_out.keys())
        scelte_act = [label_nessuno] + list(diz_act.keys())
        
        return (
            gr.update(choices=scelte_char), gr.update(choices=scelte_char), gr.update(choices=scelte_char),
            gr.update(choices=scelte_char), gr.update(choices=scelte_char), gr.update(choices=scelte_out),
            gr.update(choices=scelte_act), gr.update(choices=scelte_act), gr.update(choices=scelte_act),
            gr.update(choices=scelte_act), gr.update(choices=scelte_act), "✅ Item saved to catalog!"
        )

    btn_save_ext_char.click(fn=lambda n, d_text: _salva_rapido_estratto("Personaggio", n, d_text), inputs=[txt_ext_char_name, txt_ext_char], outputs=[dd_soggetto_1, dd_soggetto_2, dd_soggetto_3, dd_soggetto_4, dd_soggetto_5, dd_outfit_location, dd_azione_1, dd_azione_2, dd_azione_3, dd_azione_4, dd_azione_5, lbl_stato_estrazione])
    btn_save_ext_outfit.click(fn=lambda n, d_text: _salva_rapido_estratto("Outfit/Location", n, d_text), inputs=[txt_ext_outfit_name, txt_ext_outfit], outputs=[dd_soggetto_1, dd_soggetto_2, dd_soggetto_3, dd_soggetto_4, dd_soggetto_5, dd_outfit_location, dd_azione_1, dd_azione_2, dd_azione_3, dd_azione_4, dd_azione_5, lbl_stato_estrazione])
    btn_save_ext_act.click(fn=lambda n, d_text: _salva_rapido_estratto("Azione", n, d_text), inputs=[txt_ext_act_name, txt_ext_act], outputs=[dd_soggetto_1, dd_soggetto_2, dd_soggetto_3, dd_soggetto_4, dd_soggetto_5, dd_outfit_location, dd_azione_1, dd_azione_2, dd_azione_3, dd_azione_4, dd_azione_5, lbl_stato_estrazione])

    def _aggiorna_lista_elementi_esistenti(tipo):
        label_nessuno, label_default_preset, label_nuovo_elemento = _catalog_labels()
        preset_corrente = sessione.carica_ultima_sessione().get("suggerimento_sequenza_selezionato", "-")
        dati = catalog_manager.carica_catalogo(tipo or "Personaggio", genere=preset_corrente)
        scelte = [label_nuovo_elemento] + list(dati.keys())
        return gr.update(choices=scelte, value=label_nuovo_elemento), "", ""

    dd_tipo_salvataggio.change(
        fn=_aggiorna_lista_elementi_esistenti,
        inputs=[dd_tipo_salvataggio], outputs=[dd_seleziona_esistente, txt_nome_catalogo, txt_desc_catalogo]
    )

    def _carica_elemento_da_modificare(tipo, nome):
        label_nessuno, label_default_preset, label_nuovo_elemento = _catalog_labels()
        if not nome or nome == label_nuovo_elemento:
            return "", ""
        preset_corrente = sessione.carica_ultima_sessione().get("suggerimento_sequenza_selezionato", "-")
        dati = catalog_manager.carica_catalogo(tipo or "Personaggio", genere=preset_corrente)
        return nome, dati.get(nome, "")

    dd_seleziona_esistente.change(
        fn=_carica_elemento_da_modificare,
        inputs=[dd_tipo_salvataggio, dd_seleziona_esistente], outputs=[txt_nome_catalogo, txt_desc_catalogo]
    )

    def _salva_o_aggiorna_elemento(tipo, nome, desc):
        label_nessuno, label_default_preset, label_nuovo_elemento = _catalog_labels()
        if not nome or not desc:
            return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), "⚠️ Please fill both name and description."
        
        tipo_safe = tipo or "Personaggio"
        preset_corrente = sessione.carica_ultima_sessione().get("suggerimento_sequenza_selezionato", "-")
        dati = catalog_manager.salva_elemento_catalogo(tipo_safe, nome, desc, genere=preset_corrente)
        
        scelte_char = [label_nessuno] + list(catalog_manager.carica_catalogo("Personaggio", genere=preset_corrente).keys())
        scelte_out = [label_default_preset] + list(catalog_manager.carica_catalogo("Outfit/Location", genere=preset_corrente).keys())
        scelte_act = [label_nessuno] + list(catalog_manager.carica_catalogo("Azione", genere=preset_corrente).keys())
        scelte_esistenti = [label_nuovo_elemento] + list(dati.keys())
        
        return (
            gr.update(choices=scelte_char), gr.update(choices=scelte_char), gr.update(choices=scelte_char),
            gr.update(choices=scelte_char), gr.update(choices=scelte_char), gr.update(choices=scelte_out),
            gr.update(choices=scelte_act), gr.update(choices=scelte_act), gr.update(choices=scelte_act),
            gr.update(choices=scelte_act), gr.update(choices=scelte_act),
            gr.update(choices=scelte_esistenti, value=nome), "✅ Item saved to catalog!"
        )

    btn_salva_catalogo.click(fn=_salva_o_aggiorna_elemento, inputs=[dd_tipo_salvataggio, txt_nome_catalogo, txt_desc_catalogo], outputs=[dd_soggetto_1, dd_soggetto_2, dd_soggetto_3, dd_soggetto_4, dd_soggetto_5, dd_outfit_location, dd_azione_1, dd_azione_2, dd_azione_3, dd_azione_4, dd_azione_5, dd_seleziona_esistente, lbl_stato_catalogo])

    def _elimina_elemento_catalogo(tipo, nome_sel, *selected):
        label_nessuno, label_default_preset, label_nuovo_elemento = _catalog_labels()
        if not nome_sel or nome_sel == label_nuovo_elemento:
            return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), "⚠️ Select an item to delete.", "", ""
        
        tipo_safe = tipo or "Personaggio"
        preset_corrente = sessione.carica_ultima_sessione().get("suggerimento_sequenza_selezionato", "-")
        dati = catalog_manager.elimina_elemento_catalogo(tipo_safe, nome_sel, genere=preset_corrente)
        
        scelte_char = [label_nessuno] + list(catalog_manager.carica_catalogo("Personaggio", genere=preset_corrente).keys())
        scelte_out = [label_default_preset] + list(catalog_manager.carica_catalogo("Outfit/Location", genere=preset_corrente).keys())
        scelte_act = [label_nessuno] + list(catalog_manager.carica_catalogo("Azione", genere=preset_corrente).keys())
        scelte_esistenti = [label_nuovo_elemento] + list(dati.keys())
        
        lower_type = tipo_safe.lower()
        deleted_indexes = range(5) if ("personaggio" in lower_type or "character" in lower_type) else [5] if ("outfit" in lower_type or "location" in lower_type) else range(6,11)
        def after_delete(choices, index):
            if index in deleted_indexes and index < len(selected) and selected[index] == nome_sel:
                return gr.update(choices=choices, value=choices[0])
            return gr.update(choices=choices)

        return (
            after_delete(scelte_char, 0), after_delete(scelte_char, 1), after_delete(scelte_char, 2),
            after_delete(scelte_char, 3), after_delete(scelte_char, 4), after_delete(scelte_out, 5),
            after_delete(scelte_act, 6), after_delete(scelte_act, 7), after_delete(scelte_act, 8),
            after_delete(scelte_act, 9), after_delete(scelte_act, 10),
            gr.update(choices=scelte_esistenti, value=label_nuovo_elemento), "🗑️ Item deleted from catalog!", "", ""
        )

    btn_elimina_catalogo.click(fn=_elimina_elemento_catalogo, inputs=[dd_tipo_salvataggio, dd_seleziona_esistente, dd_soggetto_1, dd_soggetto_2, dd_soggetto_3, dd_soggetto_4, dd_soggetto_5, dd_outfit_location, dd_azione_1, dd_azione_2, dd_azione_3, dd_azione_4, dd_azione_5], outputs=[dd_soggetto_1, dd_soggetto_2, dd_soggetto_3, dd_soggetto_4, dd_soggetto_5, dd_outfit_location, dd_azione_1, dd_azione_2, dd_azione_3, dd_azione_4, dd_azione_5, dd_seleziona_esistente, lbl_stato_catalogo, txt_nome_catalogo, txt_desc_catalogo])

    # 3. ASSEMBLAGGIO DIRETTO CON PRESERVAZIONE NOME: DESCRIZIONE
    def _assembla_prompt_da_catalogo(s1, s2, s3, s4, s5, outfit_loc, az1, az2, az3, az4, az5, num_soggetti_count, num_azioni_count):
        preset_corrente = sessione.carica_ultima_sessione().get("suggerimento_sequenza_selezionato", "-")
        diz_char = catalog_manager.carica_catalogo("Personaggio", genere=preset_corrente)
        diz_out = catalog_manager.carica_catalogo("Outfit/Location", genere=preset_corrente)
        diz_act = catalog_manager.carica_catalogo("Azione", genere=preset_corrente)
        
        result = assemble_catalog_prompt([s1,s2,s3,s4,s5], outfit_loc, [az1,az2,az3,az4,az5],
                                         num_soggetti_count, num_azioni_count, diz_char, diz_out, diz_act)
        return result if result else gr.update()

    btn_assembla_da_catalogo.click(
        fn=_assembla_prompt_da_catalogo,
        inputs=[dd_soggetto_1, dd_soggetto_2, dd_soggetto_3, dd_soggetto_4, dd_soggetto_5, dd_outfit_location, dd_azione_1, dd_azione_2, dd_azione_3, dd_azione_4, dd_azione_5, num_soggetti_seq, num_azioni_seq],
        outputs=[prompt_to_send_img]
    )

    return {
        "box_catalogo_sequenza": box_catalogo_sequenza,
        "num_azioni_seq": num_azioni_seq, "limite_azioni_catalogo": limite_azioni_catalogo,
        "adatta_azioni_a_modalita": adatta_azioni_a_modalita,
        "dd_vista_catalogo": dd_vista_catalogo,
        "dd_soggetto_1": dd_soggetto_1, "dd_soggetto_2": dd_soggetto_2, "dd_soggetto_3": dd_soggetto_3, "dd_soggetto_4": dd_soggetto_4, "dd_soggetto_5": dd_soggetto_5,
        "btn_add_soggetto": btn_add_soggetto, "btn_rem_soggetto": btn_rem_soggetto,
        "dd_outfit_location": dd_outfit_location,
        "dd_azione_1": dd_azione_1, "dd_azione_2": dd_azione_2, "dd_azione_3": dd_azione_3, "dd_azione_4": dd_azione_4, "dd_azione_5": dd_azione_5,
        "btn_assembla_da_catalogo": btn_assembla_da_catalogo,
        "btn_estrai_vlm": btn_estrai_vlm,
        "btn_save_ext_char": btn_save_ext_char, "btn_save_ext_outfit": btn_save_ext_outfit, "btn_save_ext_act": btn_save_ext_act,
        "refresh_catalog_editor": _aggiorna_lista_elementi_esistenti,
        "txt_nome_catalogo": txt_nome_catalogo, "txt_desc_catalogo": txt_desc_catalogo,
        "dd_tipo_salvataggio": dd_tipo_salvataggio, "dd_seleziona_esistente": dd_seleziona_esistente,
        "btn_salva_catalogo": btn_salva_catalogo, "btn_elimina_catalogo": btn_elimina_catalogo
    }
