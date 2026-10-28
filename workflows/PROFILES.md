# Workflow profiles / Profili workflow

## Italiano

I profili coprono **tutti i workflow distribuiti**: Z-Image Turbo, Flux.2 Klein, Krea-2 Turbo, Krea-2 Edit, Qwen Image 2.1 Edit, LTX 2.5 e MiniMax Dual-Clock. Non è un importatore universale: cambiare la semantica dei nodi, il tipo di sampler o il protocollo del modello può richiedere un nuovo adattatore.

Il workflow API `minimax_h3_api.json` è accompagnato da `minimax_h3_api.profile.json`. Il profilo assegna a ogni ruolo (prompt, durata, seed, conditioning, sampler, uscita video, sorgente/destinazione LoRA e caricamento immagine) il relativo ID e tipo di nodo. Se rinumeri i nodi, aggiorni il profilo e i collegamenti nel workflow, senza modificare Python. I nomi degli ingressi sono quelli previsti dall'adattatore; non basta dichiarare un tipo diverso per renderlo compatibile.

Per personalizzare il profilo predefinito senza conflitti con gli aggiornamenti, copialo in `workflows/custom/minimax_h3_api.profile.json`. La copia ha precedenza ed è ignorata da Git. Per ripristinare il predefinito, rimuovi la copia. Per un altro workflow API, crea il file `.profile.json` con lo stesso nome accanto al JSON, oppure nella sottocartella `custom` della sua cartella. Il percorso del workflow continua a essere quello configurato dall'app. Un profilo mancante o errato interrompe la preparazione con un messaggio; non vengono indovinati i collegamenti.

### Profili immagine e LTX

| Workflow | Adapter | Operazioni |
|---|---|---|
| Z-Image Turbo | `zimage` | Testo, affinamento immagine, LoRA, seconda fase hires |
| Flux.2 Klein | `flux2` | Testo, affinamento immagine, LoRA |
| Krea-2 Turbo | `krea2` | Testo, affinamento immagine, LoRA, due fasi |
| Krea-2 Edit | `krea2_edit` | Edit, LoRA incorporata nel workflow |
| Qwen Image 2.1 Edit | `qwen21_edit` | Edit e LoRA personalizzate |
| LTX 2.5 | `ltx25` | Testo, primo frame, primo/ultimo, guida intermedia, LoRA |

Questi profili distinguono `id` (ID reale del nodo nel JSON esportato) e `slot` (ruolo numerico interno dell'adattatore). **Per rinumerare il workflow cambia `id`, lascia invariato `slot`.** Per esempio il prompt può passare da `id: "5"` a `id: "205"`, conservando `slot: "5"`. Non rimuovere i ruoli obbligatori: la preparazione deve poter trovare tutte le fasi, compresa la seconda generazione dove prevista. `class_type` deve corrispondere al nodo reale e `required_inputs` documenta gli ingressi necessari. Un nuovo tipo di nodo deve anche essere compatibile con il significato e i nomi degli ingressi dell'adattatore: il profilo non lo converte automaticamente.

I nodi extra non dichiarati nel profilo vengono conservati; i nodi temporanei aggiunti dall'app non possono sovrascriverli. I collegamenti vengono tradotti e gli ID originali ripristinati prima dell'invio a ComfyUI. Il workflow su disco non viene riscritto. Per disabilitare un'operazione imposta la relativa capacità a `false`; le richieste incompatibili vengono rifiutate prima dell'invio. Krea Edit mantiene il controllo della propria LoRA incorporata e non acquisisce tre slot LoRA generici con questa modifica.

La verifica installazione controlla ora tutti i profili, anche a ComfyUI spento per la parte strutturale. Batch, storyboard e sequenze usano gli stessi preparatori dei workflow immagine, quindi beneficiano degli stessi profili. La UI resta invariata: non è ancora un editor/importatore guidato dei profili.

### Modalità delle immagini (MiniMax)

- `native_keyframes`: conserva il comportamento precedente del workflow distribuito, convertendo il conditioning in `MiniMaxH3ImageToVideo` e collegando primo/ultimo frame. L'eventuale immagine intermedia diventa una guida temporale.
- `references`: mantiene `MiniMaxH3ReferenceToVideo`. Le immagini sono riferimenti numerati: prima quella iniziale, poi quella finale se diversa, poi quella intermedia. Il prompt può attribuire loro un ruolo temporale, ma il nodo non impone un primo/ultimo frame nativo.

Il nome del checkpoint non seleziona più automaticamente la modalità. La compatibilità effettiva del checkpoint con la modalità scelta deve essere verificata con una generazione: il profilo non la certifica. Il predefinito conserva la configurazione esistente, non rappresenta un nuovo confronto di qualità tra Ref2VA e First/Last.

I campi `capabilities` dichiarano testo, First/Last, riferimenti, immagine intermedia e LoRA personalizzate. Una richiesta incompatibile viene rifiutata. In questa fase i controlli della UI non vengono nascosti in base al profilo: la validazione avviene prima dell'invio a ComfyUI. Le etichette F/L e le istruzioni della regia restano quelle esistenti; scegliere `references` non trasforma automaticamente il prompt in una richiesta di sola identità.

`lora_source_output` indica l'indice di uscita modello della sorgente LoRA (normalmente 0). Il collegamento `model` del nodo destinazione viene ricostruito a partire da questa sorgente. Gli ID dei nodi aggiunti sono allocati senza sovrascrivere nodi dell'utente.

Prima della generazione vengono controllati struttura, tipi dichiarati, ingressi richiesti, collegamenti non risolti e raggiungibilità di prompt/seed/durata/sampler dall'uscita video. **Registri & Impostazioni → Verifica installazione** controlla anche il profilo distribuito e, con ComfyUI acceso, la disponibilità dei nodi per i keyframe. Questi controlli non misurano fedeltà visiva o qualità del risultato.

## English

Profiles cover **all shipped workflows**: Z-Image Turbo, Flux.2 Klein, Krea-2 Turbo, Krea-2 Edit, Qwen Image 2.1 Edit, LTX 2.5 and MiniMax Dual-Clock. Pair an API workflow with a same-name `.profile.json` file. Each role maps to an actual node ID and class. Renumbering compatible nodes requires editing the workflow and profile, not Python. Input names and semantics must match the adapter; arbitrary new samplers/node behavior still require implementation.

Place a private override in the workflow folder's `custom/` directory with the same profile filename. It takes precedence and is ignored by Git in the shipped workflows folder. Remove it to restore the default. Profiles are read for every graph preparation. Missing/invalid profiles fail explicitly.

`native_keyframes` preserves the previous shipped behavior using native first/last conditioning and optional midpoint guidance. `references` retains reference conditioning, ordered first, distinct last, then middle. Prompt-based temporal anchors are possible but are not native frame constraints. Checkpoint names no longer choose the mode. The profile declares intended capabilities; actual checkpoint compatibility and visual quality require real sampling tests.

Capabilities reject unsupported requests before submission. This first version does not dynamically hide UI controls or rewrite the director's F/L semantics into identity-only references. `lora_source_output` selects the source model output, and custom LoRA are inserted before the target's `model` input. Generated IDs never overwrite existing nodes.

Validation covers graph structure, declared node classes, required inputs, missing links and output reachability. The existing installation check also reports profile validity and availability of native guide nodes when ComfyUI is online. An import wizard and automatic UI adaptation are later stages.

### Image and LTX adapter slots

For the six image/LTX profiles, `id` is the exported node ID and `slot` is a stable internal adapter role. Change `id` when renumbering; preserve `slot`. Keep required roles, matching node types and input semantics. The profile is a binding contract, not a universal node converter. Extra nodes are preserved and generated nodes receive collision-free IDs; disk workflows are never rewritten. Capabilities reject unsupported operations. Krea Edit retains its built-in LoRA strength control, without gaining generic custom LoRA slots.

Installation diagnostics now check every profile. Image batch/storyboard/sequence operations reuse the same graph builders. The UI remains unchanged; guided profile import/editing is not part of this stage. CPU regression tests compare 23 preparation cases with the previous release and repeat them with renumbered graphs. They verify wiring, not generated image/video quality.
