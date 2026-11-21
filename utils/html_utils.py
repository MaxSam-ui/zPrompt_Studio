# utils/html_utils.py

import os
import time
from core import config, sessione, lingua
from utils.media_base import norm_path_sicuro
from utils.gallery_commands import gallery_item_key


def ottieni_lightbox_modal_html():
    """Restituisce il markup HTML del modale Lightbox una sola volta a livello globale."""
    return """
    <div class="gallery-modal-overlay" id="gallery-lightbox-modal" style="display: none;">
        <button class="gallery-modal-close" id="gallery-lightbox-close">❌</button>
        <button class="gallery-modal-nav gallery-modal-prev" id="gallery-lightbox-prev">◀</button>
        <div class="gallery-modal-content">
            <img src="" class="gallery-modal-img" id="gallery-lightbox-img">
        </div>
        <button class="gallery-modal-nav gallery-modal-next" id="gallery-lightbox-next">▶</button>
    </div>
    """


def calcola_stato_spia_video(s_sessione, stato_gen, solo_testo):
    from core import sessione as core_sessione
    s_reale = core_sessione.carica_ultima_sessione()
    
    generation_mode = s_reale.get("generation_mode", "Classica (1 Immagine)")
    lang = s_reale.get("lingua_selezionata", "IT")
    
    from core import lingua
    dl = lingua.ottieni_dizionario_lingua(lang)
    
    lista_frames_storyboard = stato_gen.get("lista_frame_storyboard_attivi", []) if stato_gen else []
    is_extension = stato_gen.get("is_extension", False) if stato_gen else False
    clip_chain = stato_gen.get("clip_chain", []) if stato_gen else []
    has_chain = bool(clip_chain and len(clip_chain) >= 1)
    
    path_first = (stato_gen.get("percorso_immagine_selezionata") if stato_gen else None) or s_reale.get("percorso_immagine_selezionata")
    path_dest = (stato_gen.get("percorso_immagine_destinazione") if stato_gen else None) or s_reale.get("percorso_immagine_destinazione")
    
    has_first = bool(path_first and os.path.exists(path_first))
    has_dest = bool(path_dest and os.path.exists(path_dest) and norm_path_sicuro(path_dest) != norm_path_sicuro(path_first))

    is_manual_upload = False
    if stato_gen and "percorso_immagine_selezionata" in stato_gen:
        img_i2v_path = stato_gen.get("percorso_immagine_selezionata")
        ultimo_usato = stato_gen.get("sorgente_corrente_utilizzato")
        if img_i2v_path and ultimo_usato:
            is_manual_upload = (norm_path_sicuro(img_i2v_path) != norm_path_sicuro(ultimo_usato))
            
    is_storyboard_active = (
        not is_extension and
        ("storyboard" in str(generation_mode).lower()) and 
        bool(lista_frames_storyboard and len(lista_frames_storyboard) >= 2)
    )
    
    if is_storyboard_active and not solo_testo:
        colore = "#a855f7" 
        bg = "rgba(168, 85, 247, 0.12)"
        border = "rgba(168, 85, 247, 0.35)"
        testo = dl.get("spia_storyboard", "🎬 STORYBOARD")
        
    elif is_extension and is_manual_upload:
        colore = "#eab308" 
        bg = "rgba(234, 179, 8, 0.12)"
        border = "rgba(234, 179, 8, 0.35)"
        testo = dl.get("spia_ext_manual", "🔄 ESTENSIONE (Manuale)")
        
    elif is_extension:
        colore = "#f97316" 
        bg = "rgba(249, 115, 22, 0.12)"
        border = "rgba(249, 115, 22, 0.35)"
        testo = dl.get("spia_ext_auto", "🔄 ESTENSIONE (Auto)")
        
    elif solo_testo:
        colore = "#06b6d4" 
        bg = "rgba(6, 182, 212, 0.12)"
        border = "rgba(6, 182, 212, 0.35)"
        testo = dl.get("spia_new_t2v", "📝 NUOVO T2V")

    elif has_chain and len(clip_chain) > 1:
        colore = "#10b981" 
        bg = "rgba(16, 185, 129, 0.12)"
        border = "rgba(16, 185, 129, 0.35)"
        num_seg = len(clip_chain)
        template_fuso = dl.get("spia_fuso", "🔗 FUSO ({num} clip)")
        testo = template_fuso.format(num=num_seg) if "{num}" in template_fuso else template_fuso

    elif has_first and has_dest:
        colore = "#ec4899" 
        bg = "rgba(236, 72, 153, 0.12)"
        border = "rgba(236, 72, 153, 0.35)"
        testo = dl.get("spia_new_fl2v", "🎥 NUOVO FL2V")
        
    else:
        colore = "#10b981" 
        bg = "rgba(16, 185, 129, 0.12)"
        border = "rgba(16, 185, 129, 0.35)"
        testo = dl.get("spia_new_i2v", "🎥 NUOVO I2V")
        
    fps = s_reale.get("video_fps", "24")
    rapporto = s_reale.get("video_rapporto", "16:9")
    risoluzione = s_reale.get("video_risoluzione", "480p")
        
    html_badge = f"""
    <div style="display: inline-flex; align-items: center; white-space: nowrap; gap: 6px; background: {bg}; border: 1px solid {border}; border-radius: 20px; padding: 4px 10px; font-size: 11px; font-weight: 600; color: {colore}; letter-spacing: normal;">
        <span style="display: inline-block; width: 6px; height: 6px; background: {colore}; border-radius: 50%; box-shadow: 0 0 8px {colore}; flex-shrink: 0;"></span>
        <span>{testo} | ⚡ {fps}fps | 📐 {rapporto} | 📺 {risoluzione}</span>
    </div>
    """
    return html_badge


def compila_galleria_html(immagini_list, percorso_selezionato=None, percorso_destinazione=None):
    from core import sessione as core_sessione
    s_reale = core_sessione.carica_ultima_sessione()
    lang = s_reale.get("lingua_selezionata", "IT")
    
    from core import lingua
    dl = lingua.ottieni_dizionario_lingua(lang)

    if immagini_list:
        viste = set()
        immagini_uniche = []
        for img in immagini_list:
            if img:
                norm_p_check = norm_path_sicuro(img)
                if norm_p_check not in viste:
                    viste.add(norm_p_check)
                    immagini_uniche.append(img)
        immagini_list = immagini_uniche

    ha_immagini_accessibili = False
    if immagini_list:
        for img in immagini_list:
            if img and os.path.exists(os.path.abspath(img)):
                ha_immagini_accessibili = True
                break

    if not immagini_list or not ha_immagini_accessibili:
        msg_no_images = dl.get("no_images", "🖼️ No images generated yet.")
        return f"""
        <div class="studio-gallery-empty">
            {msg_no_images}
        </div>
        """
        
    lbl_delete = dl.get("tooltip_delete", "Delete 🗑️")
    lbl_expand = dl.get("tooltip_expand", "Expand 🔍")

    target_sel_f = percorso_selezionato if percorso_selezionato is not None else s_reale.get("percorso_immagine_selezionata")
    target_sel_l = percorso_destinazione if percorso_destinazione is not None else s_reale.get("percorso_immagine_destinazione")

    if target_sel_f and target_sel_l and norm_path_sicuro(target_sel_f) == norm_path_sicuro(target_sel_l):
        target_sel_l = None

    items_html = ""
    for idx, img_path in enumerate(immagini_list):
        if not img_path:
            continue
            
        abs_path = os.path.abspath(img_path)
        if not os.path.exists(abs_path):
            continue
        
        try:
            mtime = int(os.path.getmtime(abs_path))
        except Exception:
            mtime = int(time.time())

        try:
            rel_path = os.path.relpath(abs_path, config.STUDIO_ROOT_DIR)
            rel_path_normalizzato = rel_path.replace("\\", "/")
            url_servito = f"/gradio_api/file={rel_path_normalizzato}?v={mtime}"
        except Exception:
            abs_path_normalizzato = abs_path.replace("\\", "/")
            url_servito = f"/gradio_api/file={abs_path_normalizzato}?v={mtime}"
        
        is_f = bool(target_sel_f and norm_path_sicuro(abs_path) == norm_path_sicuro(target_sel_f))
        is_l = bool(target_sel_l and norm_path_sicuro(abs_path) == norm_path_sicuro(target_sel_l))
                
        classe_selected = " selected-thumbnail" if is_f else ""
        class_btn_f = "gallery-item-btn-frame-f active-f" if is_f else "gallery-item-btn-frame-f"
        class_btn_l = "gallery-item-btn-frame-l active-l" if is_l else "gallery-item-btn-frame-l"
        
        is_generata_internamente = False
        try:
            output_dir_abs = os.path.abspath(config.STUDIO_OUTPUT_DIR)
            is_generata_internamente = abs_path.startswith(output_dir_abs)
        except Exception:
            pass
            
        btn_delete_html = f'<button class="gallery-item-btn-delete" data-idx="{idx}" data-key="{gallery_item_key(abs_path)}" title="{lbl_delete}">🗑️</button>' if is_generata_internamente else ""
        
        items_html += f"""
        <div class="gallery-item-wrapper{classe_selected}" data-idx="{idx}">
            <img src="{url_servito}" class="gallery-thumbnail" data-idx="{idx}">
            {btn_delete_html}
            <div class="gallery-item-btn-group-fl">
                <button class="{class_btn_f}" data-idx="{idx}" title="Frame 1 (Iniziale)">F</button>
                <button class="{class_btn_l}" data-idx="{idx}" title="Frame Ultimo (Finale)">L</button>
            </div>
            <button class="gallery-item-btn-expand" data-idx="{idx}" data-src="{url_servito}" title="{lbl_expand}">🔍</button>
        </div>
        """
        
    html_completo = f"""
    <div class="custom-gallery-grid">
        {items_html}
    </div>
    """
    return html_completo


def compila_striscia_video_html(frames_list, is_storyboard=False):
    """
    Genera la striscia dedicata e semplificata per il Tab Video sotto al Frame 1:
    - Se vuota, non occupa spazio (restituisce stringa vuota).
    - Se presente, mostra le miniature con tasto ✕ per rimuoverle dalla sequenza video.
    """
    if not frames_list:
        return ""

    cards_html = ""
    for idx, img_path in enumerate(frames_list):
        if not img_path:
            continue
        abs_path = os.path.abspath(img_path)
        if not os.path.exists(abs_path):
            continue

        try:
            mtime = int(os.path.getmtime(abs_path))
        except Exception:
            mtime = int(time.time())

        try:
            rel_path = os.path.relpath(abs_path, config.STUDIO_ROOT_DIR)
            rel_norm = rel_path.replace("\\", "/")
            url_servito = f"/gradio_api/file={rel_norm}?v={mtime}"
        except Exception:
            abs_norm = abs_path.replace("\\", "/")
            url_servito = f"/gradio_api/file={abs_norm}?v={mtime}"

        badge_testo = f"🎬 Panel {idx+2}" if is_storyboard else "🏁 Last Frame"

        cards_html += f"""
        <div class="video-strip-card" data-idx="{idx}">
            <img src="{url_servito}" class="video-strip-thumbnail">
            <button class="video-strip-btn-remove" data-idx="{idx}" title="Rimuovi dalla sequenza video">✕</button>
            <div class="video-strip-badge">{badge_testo}</div>
        </div>
        """

    return f"""
    <div class="video-strip-container">
        {cards_html}
    </div>
    """
