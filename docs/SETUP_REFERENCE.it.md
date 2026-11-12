# Configurazione e diagnostica

[Torna alla pagina iniziale](README.it.md)

## Dettagli delle cartelle: ComfyUI e LoRA

### Impostare la cartella ComfyUI

In **Registri e impostazioni → ComfyUI locale**, incolla il percorso della cartella Windows Portable che contiene `python_embeded` e `ComfyUI` (non la cartella `models`). Premi **Verifica e salva cartella**, poi riavvia Studio. Se selezioni la sottocartella `ComfyUI`, Studio riconosce automaticamente la cartella principale. Un percorso non valido non sostituisce quello salvato. Questa funzione non installa ComfyUI.

### Cartelle LoRA

Ogni famiglia usa una cartella sotto `ComfyUI/models/loras`: `Z-Image`, `Flux-2`, `Krea-2`, `Qwen2.1`, `LTX-2.5`, `MiniMax`. I percorsi in `data/settings.json` derivano da `{COMFYUI_DIR}`: basta impostare la cartella ComfyUI principale. Le vecchie cartelle `Z-Image1` e `Z-Image2`, se presenti, restano leggibili per compatibilità; i nuovi LoRA Z-Image vanno in `Z-Image`. Nessun modello viene spostato automaticamente.

## Stato della preview

- Risoluzione delle dipendenze verificata per Windows/Python 3.11; versioni transitive fissate in `scripts/constraints-win-py311.txt`.
- Collegamenti dei workflow e callback dell’interfaccia verificati. Restano da collaudare l’installazione da zero e tutte le combinazioni di modelli e workflow.
- Le guide offline italiana e inglese sono incluse: usa **?** e scegli la lingua oppure apri `help/help.html` / `help/help.en.html`.
- Presentazione destinata alla revisione privata: non costituisce una pubblicazione o una concessione di licenza.

Per segnalare un problema indica modello/workflow, passaggi per riprodurlo e log pertinenti, rimuovendo dati personali e credenziali.

Il programma di installazione esegue anche un controllo di Python, dipendenze, GPU/CUDA, cartelle e ComfyUI. Ripetilo con `scripts/check_installation.bat` oppure da **Registri e Impostazioni → Diagnostica → Verifica installazione**. Avvia ComfyUI per verificare nodi e modelli dei workflow. `CONFIG` indica requisiti da configurare o verificare per le funzioni desiderate; il controllo non scarica modelli e non certifica una generazione completa.

I suggerimenti di sistema sono personalizzabili senza modificare Python: consulta la [guida ai template e alle personalizzazioni locali](../suggestions/system/README.md).

### Cartelle del progetto

Avvia e aggiorna con i due `.bat` nella cartella principale. Il file di avvio richiama automaticamente l’installazione quando mancano l’ambiente o le dipendenze principali. Puoi anche installare con `scripts/install.bat`; esegui la diagnostica con `scripts/check_installation.bat`. Il piccolo `requirements.txt` nella radice mantiene compatibili gli aggiornamenti dalle vecchie versioni.

- `config/`: catalogo modelli, parametri workflow e impostazioni di esempio.
- `scripts/`: programma di aggiornamento e vincoli delle dipendenze.
- `docs/`: istruzioni di installazione, attribuzioni e manifesto dei file.
- `workflows/`: workflow API e profili modificabili.
- `suggestions/`: istruzioni per i prompt ed esempi personalizzabili.
- `help/`: guida illustrata.

Impostazioni e sessioni personali sono in `data/`, esclusa da Git. I vecchi file vengono trasferiti automaticamente all’avvio. Installazione e diagnostica sono in `scripts/`.
