# utils/js_helpers.py

import json
from core import lingua
from utils import timeline

def genera_script_traduci_tab_header():
    """Genera lo script JS dinamico per tradurre i titoli dei tab principali."""
    mappa_titoli_tabs = {}
    for lang_code, d_dict in lingua.LINGUE.items():
        mappa_titoli_tabs[lang_code] = [
            d_dict.get("tab_analisi", "Analisi Immagine"),
            d_dict.get("tab_render", "Rendering"),
            d_dict.get("tab_video", "Generazione Video"),
            d_dict.get("tab_batch", "Elaborazione Batch"),
            d_dict.get("tab_log", "Registri & Impostazioni")
        ]

    return f"""
    (lang) => {{
        const tabLabels = {json.dumps(mappa_titoli_tabs, ensure_ascii=False)};
        const labels = tabLabels[lang] || tabLabels['IT'] || [];
        const container = document.getElementById('main-tabs-container');
        if (container) {{
            const buttons = Array.from(container.querySelectorAll(':scope > .tab-wrapper button, .tab-nav button, .gr-tab-nav button, gr-tab-nav button, button[role="tab"]'));
            buttons.forEach((btn) => {{
                const current = btn.textContent.trim();
                const idx = Object.values(tabLabels).reduce((found, names) =>
                    found >= 0 ? found : names.indexOf(current), -1);
                if (labels[idx]) {{
                    // Keep the existing text node owned by Svelte.
                    const walker = document.createTreeWalker(btn, NodeFilter.SHOW_TEXT);
                    let text;
                    while ((text = walker.nextNode())) {{
                        if (text.nodeValue.trim()) {{
                            text.nodeValue = labels[idx];
                            break;
                        }}
                    }}
                    btn.setAttribute('aria-label', labels[idx]);
                }}
            }});
        }}
    }}
    """

JS_AGGIORNA_TABS_LAVORO = """
() => {
    const tabs = document.querySelector('.tabs');
    if (tabs) {
        const primaryButtons = Array.from(document.querySelectorAll('button.primary'));
        const isBusy = primaryButtons.some(btn => btn.disabled);
        if (isBusy) {
            tabs.classList.add('lavoro-attivo-tabs');
        } else {
            tabs.classList.remove('lavoro-attivo-tabs');
        }
    }
}
"""

def genera_script_inizializzazione():
    """Genera lo script JS di inizializzazione completa della UI e dei listener della galleria/lightbox."""
    return """
    () => {
        // Gradio can remount a range without initializing --range_progress.
        // Restore only its paint state; never change values or dispatch events.
        if (!window._studioSliderObserver) {
            let sliderPaintPending = false;
            const paintSliders = () => {
                sliderPaintPending = false;
                document.querySelectorAll('.gradio-container input[type="range"]').forEach(slider => {
                    const min = Number(slider.min || 0);
                    const max = Number(slider.max || 100);
                    const value = Number(slider.value);
                    if (!Number.isFinite(value) || max <= min) return;
                    const progress = `${Math.max(0, Math.min(100, (value - min) * 100 / (max - min)))}%`;
                    if (slider.style.getPropertyValue('--range_progress') !== progress) {
                        slider.style.setProperty('--range_progress', progress);
                    }
                });
            };
            const scheduleSliderPaint = () => {
                if (sliderPaintPending) return;
                sliderPaintPending = true;
                requestAnimationFrame(paintSliders);
            };
            window._studioSliderObserver = new MutationObserver(scheduleSliderPaint);
            window._studioSliderObserver.observe(document.querySelector('.gradio-container') || document.body,
                {childList: true, subtree: true, attributes: true,
                 attributeFilter: ['min', 'max', 'value', 'style']});
            document.addEventListener('input', scheduleSliderPaint, true);
            document.addEventListener('change', scheduleSliderPaint, true);
            paintSliders();
        }
        const labelRestoreButtons = () => document.querySelectorAll('button.studio-restore-icon').forEach(button => {
            const label = button.textContent.trim();
            if (button.title !== label) button.title = label;
        });
        labelRestoreButtons();
        if (!window._restoreLabelObserver) {
            window._restoreLabelObserver = new MutationObserver(labelRestoreButtons);
            window._restoreLabelObserver.observe(document.body, {childList: true, subtree: true, characterData: true});
        }
        const setupTimeline = __SETUP_TIMELINE_PLACEHOLDER__;
        setupTimeline();

        if (!window._gallery_listener_attached) {
            window._gallery_listener_attached = true;
            
            document.addEventListener('click', function(e) {
                const btnRemoveVideoFrame = e.target.closest('.video-strip-btn-remove');
                const btnFrameF = e.target.closest('.gallery-item-btn-frame-f');
                const btnFrameL = e.target.closest('.gallery-item-btn-frame-l');
                const btnDeleteImg = e.target.closest('.gallery-item-btn-delete');
                const btnExpandImg = e.target.closest('.gallery-item-btn-expand');
                const thumbnailImg = e.target.closest('.gallery-thumbnail');
                const modalClose = e.target.closest('#gallery-lightbox-close');
                const modalOverlay = e.target.closest('#gallery-lightbox-modal');
                const btnPrev = e.target.closest('#gallery-lightbox-prev');
                const btnNext = e.target.closest('#gallery-lightbox-next');
                
                // 1. RIMOZIONE SICURA DALLA STRISCIA VIDEO (1° CLICK GARANTITO)
                if (btnRemoveVideoFrame) {
                    e.preventDefault();
                    e.stopPropagation();
                    const card = btnRemoveVideoFrame.closest('.video-strip-card');
                    if (card) {
                        card.style.display = 'none';
                    }
                    const idx = btnRemoveVideoFrame.getAttribute('data-idx');
                    const trigger = document.querySelector('#hidden-video-gallery-trigger textarea, #hidden-video-gallery-trigger input');
                    if (trigger) {
                        trigger.value = 'REMOVE_' + idx + '_' + Date.now();
                        trigger.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                    return;
                }

                if (btnFrameF) {
                    e.preventDefault();
                    e.stopPropagation();
                    const idx = btnFrameF.getAttribute('data-idx');
                    const trigger = document.querySelector('#hidden-gallery-trigger textarea, #hidden-gallery-trigger input');
                    if (trigger) {
                        trigger.value = 'SET_FIRST_' + idx + '_' + Date.now();
                        trigger.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                } else if (btnFrameL) {
                    e.preventDefault();
                    e.stopPropagation();
                    const idx = btnFrameL.getAttribute('data-idx');
                    const wrapper = btnFrameL.closest('.gallery-item-wrapper');
                    const container = btnFrameL.closest('.custom-gallery-grid');
                    const wasActiveL = btnFrameL.classList.contains('active-l');
                    
                    if (container) {
                        container.querySelectorAll('.gallery-item-btn-frame-l').forEach(b => b.classList.remove('active-l'));
                    }
                    
                    if (wasActiveL) {
                        btnFrameL.classList.remove('active-l');
                    } else {
                        btnFrameL.classList.add('active-l');
                        if (wrapper) {
                            const siblingF = wrapper.querySelector('.gallery-item-btn-frame-f');
                            if (siblingF && siblingF.classList.contains('active-f')) {
                                siblingF.classList.remove('active-f');
                                wrapper.classList.remove('selected-thumbnail');
                            }
                        }
                    }
                    
                    const trigger = document.querySelector('#hidden-gallery-trigger textarea, #hidden-gallery-trigger input');
                    if (trigger) {
                        trigger.value = 'SET_LAST_' + idx + '_' + Date.now();
                        trigger.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                } else if (btnDeleteImg) {
                    e.preventDefault();
                    e.stopPropagation();
                    const idx = btnDeleteImg.getAttribute('data-idx');
                    const itemKey = btnDeleteImg.getAttribute('data-key');
                    
                    const isBatch = btnDeleteImg.closest('#gallery-batch-html') !== null;
                    const triggerId = isBatch ? '#hidden-gallery-trigger-batch' : '#hidden-gallery-trigger';
                    
                    const trigger = document.querySelector(triggerId + ' textarea, ' + triggerId + ' input');
                    if (trigger) {
                        window._galleryDeleteSequence = (window._galleryDeleteSequence || 0) + 1;
                        const target = itemKey ? 'KEY_' + itemKey : idx;
                        trigger.value = 'DELETE_' + target + '_' + Date.now() + '_' + window._galleryDeleteSequence;
                        trigger.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                } else if (btnExpandImg) {
                    e.preventDefault();
                    e.stopPropagation();
                    const imgSrc = btnExpandImg.getAttribute('data-src');
                    const modal = document.getElementById('gallery-lightbox-modal');
                    const modalImg = document.getElementById('gallery-lightbox-img');
                    if (modal && modalImg) {
                        modalImg.setAttribute('src', imgSrc);
                        modal.classList.add('active');
                        window._lightbox_opener = btnExpandImg;
                        document.getElementById('gallery-lightbox-close')?.focus({ preventScroll: true });
                        
                        const parentGrid = btnExpandImg.closest('.custom-gallery-grid');
                        if (parentGrid) {
                            const expands = Array.from(parentGrid.querySelectorAll('.gallery-item-btn-expand'));
                            window._lightbox_src_list = expands.map(b => b.getAttribute('data-src'));
                            window._lightbox_current_idx = expands.indexOf(btnExpandImg);
                        }
                    }
                } else if (btnPrev) {
                    e.preventDefault();
                    e.stopPropagation();
                    if (window._lightbox_src_list && window._lightbox_src_list.length > 0) {
                        window._lightbox_current_idx = (window._lightbox_current_idx - 1 + window._lightbox_src_list.length) % window._lightbox_src_list.length;
                        const modalImg = document.getElementById('gallery-lightbox-img');
                        if (modalImg) modalImg.setAttribute('src', window._lightbox_src_list[window._lightbox_current_idx]);
                    }
                } else if (btnNext) {
                    e.preventDefault();
                    e.stopPropagation();
                    if (window._lightbox_src_list && window._lightbox_src_list.length > 0) {
                        window._lightbox_current_idx = (window._lightbox_current_idx + 1) % window._lightbox_src_list.length;
                        const modalImg = document.getElementById('gallery-lightbox-img');
                        if (modalImg) modalImg.setAttribute('src', window._lightbox_src_list[window._lightbox_current_idx]);
                    }
                } else if (thumbnailImg) {
                    e.preventDefault();
                    e.stopPropagation();
                    const idx = thumbnailImg.getAttribute('data-idx');
                    const isBatch = thumbnailImg.closest('#gallery-batch-html') !== null;
                    const triggerId = isBatch ? '#hidden-gallery-trigger-batch' : '#hidden-gallery-trigger';
                    
                    const trigger = document.querySelector(triggerId + ' textarea, ' + triggerId + ' input');
                    if (trigger) {
                        trigger.value = 'SELECT_' + idx + '_' + Date.now();
                        trigger.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                } else if (modalClose || (modalOverlay && !e.target.closest('.gallery-modal-content') && !e.target.closest('.gallery-modal-nav'))) {
                    const modal = document.getElementById('gallery-lightbox-modal');
                    if (modal) {
                        modal.classList.remove('active');
                        window._lightbox_opener?.focus({ preventScroll: true });
                    }
                }
            });
        }

        if (!window._lightbox_keyboard_attached) {
            window._lightbox_keyboard_attached = true;
            document.addEventListener('keydown', function(event) {
                const modal = document.getElementById('gallery-lightbox-modal');
                if (modal && modal.classList.contains('active')) {
                    if (event.key === 'ArrowLeft') {
                        document.getElementById('gallery-lightbox-prev').click();
                    } else if (event.key === 'ArrowRight') {
                        document.getElementById('gallery-lightbox-next').click();
                    } else if (event.key === 'Escape') {
                        document.getElementById('gallery-lightbox-close').click();
                    }
                }
            });
        }
    }
    """.replace("__SETUP_TIMELINE_PLACEHOLDER__", timeline.js_setup_timeline_drag)
