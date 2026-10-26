# Custom suggestions / Suggerimenti personalizzati

## Italiano

I suggerimenti forniti sono **esempi dell’autore**, pensati per mostrare possibilità e aiutarti a iniziare. Puoi adattarli o aggiungerne di tuoi. Non sono necessari per ogni generazione e non garantiscono da soli qualità o continuità dei personaggi.

| Cartella | Funzione |
| --- | --- |
| `suggestions/vision` | Orienta la descrizione visiva e lo stile del prompt. |
| `suggestions/direction` | Indicazioni di regia, camera, movimento e atmosfera per il video. |
| `suggestions/screenplay` | Idee di scena già scritte: selezionarle carica il testo nel campo soggetto, non applica soltanto uno stile. Rileggi il campo dopo la selezione. |
| `suggestions/storyboard` | Tecniche e organizzazione delle inquadrature dei pannelli. |
| `suggestions/sequence` | Stile delle sequenze e cartelle dei cataloghi di personaggi, ambienti/abiti e azioni. |
| `suggestions/system` | Template tecnici usati dall’app: non sono semplici preset di stile. |

### Crea un tuo preset

1. Duplica un `.txt` della categoria appropriata e assegnagli un nome nuovo, per esempio `Mio_ritratto_naturale.txt`.
2. Salvalo in UTF-8 con estensione `.txt` minuscola nella cartella di quella categoria. Il nome senza estensione diventa la voce nel selettore.
3. Scrivi indicazioni brevi e coerenti. Per i prompt visivi l’inglese è una scelta pratica; nomi e trigger devono rimanere esatti.
4. Riavvia Studio per aggiornare gli elenchi, poi scegli il nuovo preset e controlla il testo risultante.
5. Provalo prima su una scena semplice e confrontalo con la stessa richiesta senza preset, lasciando invariati modello, seed e parametri quando possibile.

Per una sequenza puoi duplicare un preset `.txt` e la cartella del catalogo associata, mantenendo lo stesso nome di base. Conserva la struttura JSON dei file `characters.json`, `outfits.json` e `actions.json`. Gli abiti e l’ambiente possono essere descritti insieme nel catalogo `outfits`.

Esempio per `vision`:

```text
Use natural photographic lighting and restrained colors.
Preserve the supplied subject, clothing, setting and camera angle.
Describe relevant visible textures without inventing props or scenery.
```

### Scegli il suggerimento adatto

- Un preset di dialogo campo/controcampo è utile per una conversazione; non per una singola fotografia di prodotto.
- Un preset di genere può proporre un ambiente preciso. Se vuoi mantenere il tuo ambiente, elimina le indicazioni incompatibili dalla tua copia.
- Evita di chiedere contemporaneamente mezzogiorno e luce notturna, o camera fissa e movimenti multipli nella stessa inquadratura.
- I nomi di registi o stili sono scorciatoie descrittive, non garanzie di un risultato identico. Indicazioni concrete sono più verificabili.

Nei template `system` conserva nomi dei file, segnaposto fra parentesi graffe e formati richiesti. Modificarli può alterare parsing, compilazione e comportamento del modello: fai una copia e verifica il flusso interessato.

**Aggiornamenti:** modificare un file già tracciato può fermare `update.bat`. Conserva copie e backup dei tuoi preset. Le cinque cartelle creative possono essere spostate fuori dal repository tramite le relative chiavi `SUGGESTION_*_DIR` in `settings.json`; copia prima gli esempi che vuoi conservare. La cartella `system` non usa lo stesso meccanismo configurabile.

## English

The supplied suggestions are **examples prepared by the author**, intended to demonstrate possibilities and help you get started. Adapt them or add your own. They are optional and do not independently guarantee quality or character continuity.

| Folder | Purpose |
| --- | --- |
| `suggestions/vision` | Visual description and image-prompt style. |
| `suggestions/direction` | Video direction, camera movement and atmosphere. |
| `suggestions/screenplay` | Written scene ideas: selection loads text into the subject field, rather than merely adding a style. Review the field after selecting one. |
| `suggestions/storyboard` | Panel framing and storytelling techniques. |
| `suggestions/sequence` | Sequence style and associated character, setting/outfit and action catalogs. |
| `suggestions/system` | Technical templates used by the app, not ordinary style presets. |

### Create a preset

1. Duplicate a `.txt` file in the appropriate category and give it a new name, such as `My_natural_portrait.txt`.
2. Save it as UTF-8 with a lowercase `.txt` extension in that category folder. The filename without its extension becomes the selector entry.
3. Use short, consistent instructions. English is practical for visual prompts; preserve exact names and trigger words.
4. Restart Studio to refresh the lists, select the preset and review the resulting text.
5. Compare a simple scene with and without the preset, keeping model, seed and settings constant where possible.

For sequences, you can duplicate both the `.txt` preset and its matching catalog folder under the same base name. Preserve the JSON structure of `characters.json`, `outfits.json` and `actions.json`. The outfits catalog may combine clothing and environment descriptions.

The vision example above asks for natural photographic lighting while preserving supplied scene facts. Use shot/reverse-shot guidance for conversations, not every task. Remove genre-specific settings if they conflict with your idea. Avoid simultaneous contradictory lighting or camera instructions. Style/director names are descriptive shorthand, not guarantees.

In `system` templates, preserve filenames, brace placeholders and output contracts. Changes can affect parsing and compilation: keep backups and test the relevant flow.

**Updates:** edits to tracked presets can stop `update.bat`. Back up personal presets. The five creative preset directories can be placed outside the repository using their `SUGGESTION_*_DIR` settings; copy any bundled examples you want first. The system directory does not use that configurable mechanism.
