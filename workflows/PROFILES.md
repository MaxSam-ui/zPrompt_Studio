# Workflow profiles / Profili workflow

## Italiano

Questa prima versione riguarda **MiniMax Dual-Clock**. Gli altri adattatori restano invariati. Non è un importatore universale: cambiare la semantica dei nodi, il tipo di sampler o il protocollo del modello può richiedere un nuovo adattatore.

Il workflow API `minimax_h3_api.json` è accompagnato da `minimax_h3_api.profile.json`. Il profilo assegna a ogni ruolo (prompt, durata, seed, conditioning, sampler, uscita video, sorgente/destinazione LoRA e caricamento immagine) il relativo ID e tipo di nodo. Se rinumeri i nodi, aggiorni il profilo e i collegamenti nel workflow, senza modificare Python. I nomi degli ingressi sono quelli previsti dall'adattatore; non basta dichiarare un tipo diverso per renderlo compatibile.

Per personalizzare il profilo predefinito senza conflitti con gli aggiornamenti, copialo in `workflows/custom/minimax_h3_api.profile.json`. La copia ha precedenza ed è ignorata da Git. Per ripristinare il predefinito, rimuovi la copia. Per un altro workflow API, crea il file `.profile.json` con lo stesso nome accanto al JSON, oppure nella sottocartella `custom` della sua cartella. Il percorso del workflow continua a essere quello configurato dall'app. Un profilo mancante o errato interrompe la preparazione con un messaggio; non vengono indovinati i collegamenti.

### Modalità delle immagini

- `native_keyframes`: conserva il comportamento precedente del workflow distribuito, convertendo il conditioning in `MiniMaxH3ImageToVideo` e collegando primo/ultimo frame. L'eventuale immagine intermedia diventa una guida temporale.
- `references`: mantiene `MiniMaxH3ReferenceToVideo`. Le immagini sono riferimenti numerati: prima quella iniziale, poi quella finale se diversa, poi quella intermedia. Il prompt può attribuire loro un ruolo temporale, ma il nodo non impone un primo/ultimo frame nativo.

Il nome del checkpoint non seleziona più automaticamente la modalità. La compatibilità effettiva del checkpoint con la modalità scelta deve essere verificata con una generazione: il profilo non la certifica. Il predefinito conserva la configurazione esistente, non rappresenta un nuovo confronto di qualità tra Ref2VA e First/Last.

I campi `capabilities` dichiarano testo, First/Last, riferimenti, immagine intermedia e LoRA personalizzate. Una richiesta incompatibile viene rifiutata. In questa fase i controlli della UI non vengono nascosti in base al profilo: la validazione avviene prima dell'invio a ComfyUI. Le etichette F/L e le istruzioni della regia restano quelle esistenti; scegliere `references` non trasforma automaticamente il prompt in una richiesta di sola identità.

`lora_source_output` indica l'indice di uscita modello della sorgente LoRA (normalmente 0). Il collegamento `model` del nodo destinazione viene ricostruito a partire da questa sorgente. Gli ID dei nodi aggiunti sono allocati senza sovrascrivere nodi dell'utente.

Prima della generazione vengono controllati struttura, tipi dichiarati, ingressi richiesti, collegamenti non risolti e raggiungibilità di prompt/seed/durata/sampler dall'uscita video. **Registri & Impostazioni → Verifica installazione** controlla anche il profilo distribuito e, con ComfyUI acceso, la disponibilità dei nodi per i keyframe. Questi controlli non misurano fedeltà visiva o qualità del risultato.

## English

This initial profile adapter supports **MiniMax Dual-Clock** only. Pair an API workflow with a same-name `.profile.json` file. Each role maps to an actual node ID and class. Renumbering compatible nodes requires editing the workflow and profile, not Python. Input names and semantics must match the adapter; arbitrary new samplers/node behavior still require implementation.

Place a private override in the workflow folder's `custom/` directory with the same profile filename. It takes precedence and is ignored by Git in the shipped workflows folder. Remove it to restore the default. Profiles are read for every graph preparation. Missing/invalid profiles fail explicitly.

`native_keyframes` preserves the previous shipped behavior using native first/last conditioning and optional midpoint guidance. `references` retains reference conditioning, ordered first, distinct last, then middle. Prompt-based temporal anchors are possible but are not native frame constraints. Checkpoint names no longer choose the mode. The profile declares intended capabilities; actual checkpoint compatibility and visual quality require real sampling tests.

Capabilities reject unsupported requests before submission. This first version does not dynamically hide UI controls or rewrite the director's F/L semantics into identity-only references. `lora_source_output` selects the source model output, and custom LoRA are inserted before the target's `model` input. Generated IDs never overwrite existing nodes.

Validation covers graph structure, declared node classes, required inputs, missing links and output reachability. The existing installation check also reports profile validity and availability of native guide nodes when ComfyUI is online. An import wizard and automatic UI adaptation are later stages.
