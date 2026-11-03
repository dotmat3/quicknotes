# Usare QuickNotes

QuickNotes è un'app per Windows per prendere note di riunione, tenere traccia di azioni e decisioni e ritrovare tutto con la ricerca. Le note sono file Markdown sul tuo computer: nessun account, nessun cloud.

## Cosa serve

- Windows 10 o 11.
- Niente installazione e niente permessi di amministratore: è un solo file da avviare.

## Primo avvio

1. Scarica **`QuickNotes.exe`** dall'ultima release: **<https://github.com/dotmat3/quicknotes/releases/latest>**.
2. Mettilo in una cartella che non svuoti, per esempio `Documenti\QuickNotes`, invece di lasciarlo in Download.
3. Fai doppio clic. Windows potrebbe mostrare **"Windows ha protetto il PC"**, perché l'app non ha ancora un certificato di firma del codice: premi **"Ulteriori informazioni"**, poi **"Esegui comunque"**. Succede solo la prima volta.
   Se il PC aziendale blocca l'avvio e non compare "Esegui comunque", scrivi a chi ti ha mandato l'app: va chiesto all'IT.

Per ritrovarla facilmente: clic destro su `QuickNotes.exe` › Mostra altre opzioni › **Aggiungi a Start** (o **Aggiungi alla barra delle applicazioni**).

## Primi passi

- **Le note** sono nella cartella `QuickNotes` della tua cartella utente (`C:\Users\<tu>\QuickNotes`), divise per anno e mese. In Impostazioni › Note e registrazione c'è "Apri la cartella". Ogni giorno ha la sua nota del giorno.
- **Chiudere la finestra non chiude l'app:** QuickNotes resta nell'area di notifica, vicino all'orologio. Per uscire davvero: clic destro sull'icona › Esci.
- **Tasti utili ovunque in Windows:** Ctrl Alt N per una nota rapida, Ctrl Alt D per la nota del giorno.
- **Dentro l'app:** il pulsante **?** in basso a destra (o F1) apre la guida con tutti i comandi; Ctrl K cerca ovunque.
- **Avvio con Windows:** in Impostazioni › Informazioni puoi farla partire con Windows, nascosta nell'area di notifica, così i tasti rapidi sono sempre pronti. Se poi sposti `QuickNotes.exe`, riattivalo.

## Versioni nuove

QuickNotes non si aggiorna da sola. In Impostazioni › Informazioni vedi la tua versione, e **"Apri le release"** porta alla pagina con le versioni pubblicate. Per passare a una nuova:

1. Chiudi QuickNotes: clic destro sull'icona vicino all'orologio › Esci.
2. Scarica il nuovo `QuickNotes.exe` e mettilo al posto del vecchio, nella stessa cartella.
3. Riaprilo.

Le note non vengono mai toccate.

## Con Claude (facoltativo)

QuickNotes può far leggere e cercare le tue note a Claude Desktop o Claude Code. Scarica anche **`quicknotes-mcp.exe`** dalla stessa release e mettilo nella cartella di `QuickNotes.exe`. In Impostazioni › Claude trovi il blocco di configurazione già pronto da copiare.

## Togliere QuickNotes

Esci dall'app, disattiva prima "Avvia con Windows" se l'avevi acceso, e cancella `QuickNotes.exe`. Le note in `C:\Users\<tu>\QuickNotes` restano dove sono: per eliminarle va cancellata a mano quella cartella, e la configurazione è in `C:\Users\<tu>\.quicknotes`.
