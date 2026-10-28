# Prova di installazione pulita — zPrompt Studio

Questa cartella contiene i sorgenti per la prova GitHub. Non contiene ambiente Python,
modelli, LoRA, sessioni, immagini generate, prompt salvati o dati della vecchia installazione.
Sono inclusi i preset generici; i preset personali/sperimentali numerati 90–99 sono esclusi.
Il preset text_only è stato reso neutro nella sola copia.

1. Copia/estrai tutta questa cartella in una posizione nuova e scrivibile.
2. Installa Python 3.11 a 64 bit con Python Launcher. Per la generazione GPU servono
   una GPU compatibile, driver e ComfyUI configurato separatamente.
3. Esegui `install.bat`: crea il proprio venv, copia config/settings.example.json in settings.json se assente e installa le dipendenze via Internet.
   Le dipendenze dirette presenti nell'ambiente di sviluppo sono fissate a quelle versioni;
   le dipendenze transitive sono fissate in scripts/constraints-win-py311.txt per Windows/Python 3.11.
4. PRIMA di avviare, modifica `settings.json`: imposta `COMFYUI_DIR` sulla cartella
   che contiene `ComfyUI` e `python_embeded` del portable. Il percorso C:/... è solo
   un esempio. Controlla `COMFYUI_URL` e i percorsi LoRA. `VLM_CACHE_DIR` è locale
   (`models_cache`), come output e sessione.
5. Esegui `zPrompt_Studio.bat`. Usa Registri e Impostazioni per verificare i workflow.
6. Installa in ComfyUI i nodi personalizzati e i modelli richiesti dai workflow che
   intendi usare. I JSON sono inclusi in `workflows`, i pesi NON sono inclusi.
   I modelli LLM/VLM possono essere scaricati al primo utilizzo; quelli di generazione
   e i LoRA devono essere disponibili nella tua installazione ComfyUI.
7. Prova prima una generazione singola, poi Edit, storyboard e video secondo i modelli installati.

Chiudi la vecchia app prima della prova: se configuri lo stesso ComfyUI, entrambe
le copie usano lo stesso servizio e gli stessi modelli. Per una prova completamente
isolata prepara anche un nuovo ComfyUI portable. Questa cartella non lo installa.

Le guide illustrate offline sono disponibili in `help/help.html` (italiano) e
`help/help.en.html` (inglese), oppure tramite il pulsante Help dell’app.
I percorsi indicati in questa guida sono relativi alla cartella principale del progetto.
