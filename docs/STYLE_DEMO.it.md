# Una sola idea, tre trattamenti visivi

[English](STYLE_DEMO.md)

[![Confronto tra i tre risultati reali](assets/style-demo/comparison.jpg)](assets/style-demo/styles.mp4)

**[Guarda il confronto di 27 secondi](assets/style-demo/styles.mp4)** · [Prompt esatti e tempi misurati](assets/style-demo/prompts.json)

È un montaggio di risultati reali ottenuti tramite le funzioni di creazione prompt e rendering di Studio, non una registrazione dello schermo. Le attese sono omesse. Non sono state usate immagini di riferimento né LoRA opzionali. I prompt della demo non sono stati riscritti manualmente.

## Provalo anche tu

1. In **Analisi**, attiva **Solo testo** e scrivi `A dog on a street.` nel campo della descrizione.
2. Scegli **01_Natural_Photography** e crea il prompt. Osserva le indicazioni su luce, colori e composizione.
3. In **Rendering**, usa Krea-2 Turbo, modalità classica, una copia, 1024 × 576 e seed fisso **12112026**. Mantieni entrambe le fasi del workflow, senza LoRA opzionali. Genera.
4. Ripeti con **09_Ridley_Scott_Industrial_SciFi** e **11_Wes_Anderson_Graphic_Cinema**, senza cambiare descrizione e impostazioni di rendering.

Il modello dei prompt è Qwen3-VL 4B abliterated, con limite di 320 token. Il JSON allegato riporta i tempi reali, incluso il caricamento dove applicabile. Hardware, cache e versioni influiscono su tempi e risultati. Il seed immagine fisso non rende deterministica la generazione dei prompt dell’LLM.

## Cosa osservare

Confronta luce, palette, materiali e composizione. Lo stile fornisce indicazioni visive, non garantisce un risultato preciso. Con un’idea così breve l’LLM completa i dettagli mancanti: cane e strada possono cambiare. È una prova pratica dell’intero percorso, non un confronto a identità bloccata.

Scegliendo lo stile in Analisi viene selezionato anche quello corrispondente nel Video. Puoi cambiarlo nel Video; idea, timeline e prompt già creati restano invariati. Questo confronto mostra immagini statiche, non movimento video generato dall’AI.

### Risultato osservato

Natural Photography ha prodotto una scena fotografica; Industrial SciFi ha accentuato luci scure e superfici deteriorate. Graphic Cinema ha prodotto una resa illustrata invece di un look cinematografico dal vivo. È un’ambiguità nell’interpretazione delle indicazioni visive da parte del modello, non una prova di riproduzione fedele dello stile di un regista. Tutti i prompt hanno aggiunto dettagli non specificati. Per maggiore controllo, descrivi cane e ambiente e richiedi una fotografia dal vivo quando desiderata.
