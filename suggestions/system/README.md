# System prompt customization / Personalizzazione dei prompt di sistema

## Italiano

I file `.txt` contengono le istruzioni inviate al modello. Per personalizzarli, copia il file desiderato in `suggestions/system/custom/`, mantenendo lo stesso nome, e modifica la copia in UTF-8. La copia locale ha precedenza, non viene pubblicata su GitHub e non blocca `update.bat`. Elimina la copia per ripristinare il template distribuito. Non modificare gli originali se vuoi ricevere aggiornamenti automatici senza conflitti.

I template vengono riletti a ogni nuova richiesta. Un prompt di sistema già visualizzato/modificato nella UI è invece lo stato corrente dell'utente: riseleziona il preset o la modalità per rigenerarlo; non viene sovrascritto mentre lo stai usando. Una generazione già iniziata mantiene le istruzioni con cui è partita.

La catena è: template del compito + contenuti dell'utente e riferimenti + preset scelto + regole condivise quando previste dal flusso. `Scene_Consistency.txt` governa priorità e continuità per analisi, storyboard, sequenze e regia; `Output_Language.txt` governa la lingua per generazione/affinamento visivo. Le regole del compilatore MiniMax sono nel suo template dedicato. Non ogni file viene aggiunto a ogni richiesta.

Puoi cambiare tono, dettaglio, scelte stilistiche e regole. Conserva i segnaposto necessari ai dati del compito: `{idea}`, ad esempio, viene sostituito con l'idea. I nomi sono esatti e sensibili alle maiuscole. I segnaposto sconosciuti producono un errore; le parentesi presenti nei testi dell'utente restano letterali. Rimuovere un segnaposto elimina quel dato dal messaggio, quindi evita di togliere idea, timeline, richieste di modifica o riferimenti. Gli esempi non devono introdurre personaggi, azioni o stile non richiesti.

Vincoli tecnici da conservare: numerazione Photo/panel, intervalli della timeline, campi separati da `|`, etichette di inquadratura/movimento, `[GLOBAL_AUDIO]`, etichette CHARACTER/OUTFIT_LOCATION/ACTION e le sei sezioni MiniMax. I parser e i controlli di durata restano nel codice. Modificare le istruzioni non disattiva tali controlli e non garantisce che un LLM segua sempre il template.

I file vuoti normalmente generano un errore esplicito, così l'app non sostituisce le personalizzazioni con altre istruzioni nascoste. Solo `Scene_Consistency.txt`, `Output_Language.txt` e `Negative Prompt.txt` possono essere vuoti per disattivare il relativo contributo. Il prompt negativo viene inviato al workflow LTX, non al LLM. I limiti di token, i dati di input e il protocollo chat del modello restano gestiti dal codice.

`text_only.txt` è mantenuto per compatibilità con vecchi preset: il flusso attuale usa `Text_Only_Template.txt`. I preset di genere, cast e stile nelle altre sottocartelle restano separati dai template di sistema. Questa cartella custom riguarda solo i template system, non i cataloghi JSON o gli altri preset.

## English

Copy a system `.txt` file into `suggestions/system/custom/`, keep its filename, and edit the UTF-8 copy. Local overrides take precedence, are ignored by Git and survive updates. Delete an override to restore the shipped template. Editing shipped originals can block the updater.

Templates are read for each new request. Existing system text in the UI remains the user's current state; reselect the preset/mode to rebuild it. Running requests keep their original instructions. Task templates, user/reference data, selected presets and applicable shared rules form the prompt; not every template applies to every task.

Customize tone and guidance while retaining required input placeholders and output formats. Placeholder names are case-sensitive. Unknown placeholders fail clearly; braces in user-provided text are not recursively expanded. Removing a placeholder removes that input from the request. Preserve Photo/panel numbering, timeline intervals, pipe-separated fields, allowed shot/camera labels, `[GLOBAL_AUDIO]`, catalog extraction labels and the six MiniMax sections. Parsers, duration validation, token limits and chat protocol stay in code.

Empty task templates fail explicitly. Empty overrides are supported only for `Scene_Consistency.txt`, `Output_Language.txt` and `Negative Prompt.txt`. The negative prompt is a workflow input, not an LLM instruction. `text_only.txt` is a compatibility preset; current text-only generation uses `Text_Only_Template.txt`. Other style presets and JSON catalogs are separate; this override mechanism covers system templates only.

## File e segnaposto / Files and placeholders

| File | Segnaposto / Placeholders |
|---|---|
| [Default_Director_Style.txt](Default_Director_Style.txt) | — |
| [Edit_Prompt.txt](Edit_Prompt.txt) | — |
| [Extract_Catalog.txt](Extract_Catalog.txt) | — |
| [Frame_Analysis.txt](Frame_Analysis.txt) | — |
| [Image_Refine_System.txt](Image_Refine_System.txt) | — |
| [Master_Director_Template.txt](Master_Director_Template.txt) | `{audio_section}`, `{cronologia}`, `{frame_context}`, `{regole_estetiche_regista}` |
| [Master_Storyboard_Template.txt](Master_Storyboard_Template.txt) | `{num_pannelli_int}`, `{regole_estetiche_storyboard}`, `{shape_desc}` |
| [Master_Vision_Template.txt](Master_Vision_Template.txt) | `{regole_estetiche_vision}` |
| [MiniMax_Compiler.txt](MiniMax_Compiler.txt) | `{canonical}`, `{reference_context}` |
| [MiniMax_Legacy_Format.txt](MiniMax_Legacy_Format.txt) | `{refs}`, `{sound}`, `{subject}`, `{text}` |
| [MiniMax_No_References.txt](MiniMax_No_References.txt) | — |
| [MiniMax_References.txt](MiniMax_References.txt) | `{references}` |
| [MiniMax_Repair.txt](MiniMax_Repair.txt) | `{original_instruction}`, `{structured}` |
| [Negative Prompt.txt](Negative%20Prompt.txt) | — |
| [Output_Language.txt](Output_Language.txt) | — |
| [Photo_Sequence.txt](Photo_Sequence.txt) | `{num_scatti}`, `{regole_estetiche_sequenza}` |
| [Refine Prompt.txt](Refine%20Prompt.txt) | `{descrizione_corrente}`, `{istruzioni_affinamento}`, `{sistema_prompt}` |
| [Scene_Consistency.txt](Scene_Consistency.txt) | — |
| [Screenwriter.txt](Screenwriter.txt) | `{durata}`, `{frame_context}`, `{idea_utente}`, `{intervalli_formattati}`, `{lista_inquadrature}`, `{lista_zoom}`, `{primo_intervallo}`, `{video_num_clips}` |
| [Sequence_Participants.txt](Sequence_Participants.txt) | — |
| [Sequence_Refine.txt](Sequence_Refine.txt) | `{changes}`, `{original}` |
| [Sequence_Wardrobe.txt](Sequence_Wardrobe.txt) | `{primary}` |
| [Storyboard_System.txt](Storyboard_System.txt) | — |
| [Subject_From_Frame.txt](Subject_From_Frame.txt) | `{desc_start}`, `{dest_context}` |
| [Subject_From_Text.txt](Subject_From_Text.txt) | `{idea}` |
| [Subject_Refine_Frame.txt](Subject_Refine_Frame.txt) | `{desc_start}`, `{dest_context}`, `{testo_utente}` |
| [text_only.txt](text_only.txt) | `{regole_estetiche_vision}` |
| [Text_Only_Template.txt](Text_Only_Template.txt) | `{regole_estetiche_vision}` |
| [Timeline_Dialogue.txt](Timeline_Dialogue.txt) | `{soggetto}`, `{testo_timeline}` |
| [Timeline_First_Context.txt](Timeline_First_Context.txt) | `{prompt_img}` |
| [Timeline_First_Last_Context.txt](Timeline_First_Last_Context.txt) | `{desc_last_frame}`, `{prompt_img}` |
| [Video_Director_Style.txt](Video_Director_Style.txt) | `{stile_regole_testo}` |
| [Video_First_Context.txt](Video_First_Context.txt) | `{prompt_img}` |
| [Video_First_Last_Context.txt](Video_First_Last_Context.txt) | `{desc_last_frame}`, `{prompt_img}` |
| [Video_Subject_Context.txt](Video_Subject_Context.txt) | `{soggetto}` |
| [Video_Timeline_Repair.txt](Video_Timeline_Repair.txt) | `{audio_section}`, `{cronologia}`, `{draft}`, `{frame_block}`, `{soggetto}` |
