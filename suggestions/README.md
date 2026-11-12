# Shared styles / Stili condivisi

## Italiano

Analisi/creazione dei prompt immagine (anche batch) e regia video offrono gli stessi otto stili di base: Natural Photography, Atmospheric Cinema, Noir, Science Fiction, Fantasy, Illustration Animation, Nature Documentary e Retro Film. Quando selezioni uno stile nel tab Analisi, viene selezionato anche il suggerimento di regia con lo stesso nome nel tab Video. Puoi poi cambiarlo liberamente nel Video. I suggerimenti senza corrispondenza lasciano invariata la scelta video; selezionare «-» la azzera. Il caricamento della sessione e il cambio lingua non sincronizzano le scelte. Idea, timeline e prompt già creati restano invariati.

Ogni coppia di file in `vision/` e `direction/` contiene la stessa base visiva, seguita da istruzioni specifiche per immagini o video. Per la demo del faro usa **02_Atmospheric_Cinema** in entrambe le fasi. Lo stile non deve cambiare identità, abiti, ambiente, azioni o tempi. La coerenza delle risposte dell’LLM resta da controllare.

I preset di `screenplay/` sono spunti di trama; quelli di `storyboard/` e `sequence/` definiscono strutture e modalità, non alternative allo stile. Personaggi e ambienti restano contenuti separati. Questi cataloghi e i prompt tecnici di `system/` non vengono sostituiti dal catalogo visivo.

I vecchi stili sono conservati nei file originali come archivio compatibile. `style_catalog.json` li nasconde dal menu solo se il contenuto è ancora quello distribuito e non sono selezionati nella sessione salvata. Un vecchio preset modificato resta visibile. Per recuperare un preset nascosto, copiane il `.txt` nella stessa cartella con un nome nuovo e riavvia l’app. Nessun testo utente viene cancellato o migrato verso uno stile diverso.

Per creare uno stile personale, copia la coppia di file con lo stesso nuovo nome nelle due cartelle. Modifica la base visiva in entrambe e conserva le istruzioni appropriate alla fase. I file vengono letti al momento dell’uso; riseleziona lo stile per aggiornare un prompt di sistema già visualizzato. Non serve modificare codice Python.

Sono disponibili anche cinque coppie ispirate a registi: **09_Ridley_Scott_Industrial_SciFi**, **10_Denis_Villeneuve_Monumental_SciFi**, **11_Wes_Anderson_Graphic_Cinema**, **12_Guillermo_del_Toro_Gothic_Fantasy** e **13_Alfred_Hitchcock_Visual_Suspense**. Fantascienza generale si trova sotto **04_Science_Fiction**. I riferimenti ai registi vengono descritti con caratteristiche visive concrete; non aggiungono automaticamente eventi, oggetti o movimenti di camera.

## English

Image prompt analysis/creation (including batch) and video direction share eight base styles: Natural Photography, Atmospheric Cinema, Noir, Science Fiction, Fantasy, Illustration Animation, Nature Documentary and Retro Film. Selecting a style in the Analysis tab also selects the matching direction preset in the Video tab. You can then override it in Video. Unmatched presets leave the video choice unchanged; selecting "-" clears it. Session loading and language changes do not synchronize selections. Existing ideas, timelines and prompts remain unchanged.

Each pair in `vision/` and `direction/` has an identical visual foundation and a separate application for still images or video. Use **02_Atmospheric_Cinema** in both stages for the lighthouse demo. Style must preserve identity, wardrobe, setting, actions and timing. Review the LLM’s actual output for consistency.

`screenplay/` contains story ideas; `storyboard/` and `sequence/` describe structures and modes. Characters and environments are separate scene content. These catalogs and the technical `system/` prompts are not replaced by visual styles.

Legacy styles remain in their original files. `style_catalog.json` hides only unchanged stock legacy presets that are not selected in the saved session. Edited legacy presets remain visible. To restore a hidden preset, copy its text file under a new name in the same folder and restart the app. No user text is deleted or migrated to a different style.

To customize, copy a matching pair under a new name in both folders. Edit the shared visual foundation in both files and keep the stage-specific instructions. Files are read when used; reselect a style to refresh an already displayed system prompt. No Python changes are required.

Five additional matched pairs offer director-inspired treatments: **09_Ridley_Scott_Industrial_SciFi**, **10_Denis_Villeneuve_Monumental_SciFi**, **11_Wes_Anderson_Graphic_Cinema**, **12_Guillermo_del_Toro_Gothic_Fantasy** and **13_Alfred_Hitchcock_Visual_Suspense**. General science fiction is **04_Science_Fiction**. These presets express concrete visual properties rather than relying on a director name, and do not automatically add events, objects or camera movement.
