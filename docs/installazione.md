# Usare QuickNotes

QuickNotes è un'app per Windows per prendere note di riunione, tenere traccia di azioni e decisioni e ritrovare tutto con la ricerca. Le note sono file Markdown sul tuo computer: nessun account, nessun cloud.

## Cosa serve

- Windows 10 o 11 a 64 bit.
- Niente installazione e niente permessi di amministratore: è una cartella da estrarre. Dentro c'è anche Python, non serve averlo.

## Primo avvio

1. Scarica **`QuickNotes.zip`** dall'ultima release: **<https://github.com/dotmat3/quicknotes/releases/latest>**.
2. Prima di estrarlo: tasto destro sullo zip › **Proprietà** › spunta **Sblocca** › OK. Serve perché lo zip arriva da internet.
3. Estrai la cartella in un posto che non svuoti, per esempio `Documenti\QuickNotes`, invece di lasciarla in Download.
4. Apri **`QuickNotes.cmd`**.

Se non succede nulla, apri **`Verifica.cmd`** nella stessa cartella: controlla il PC e scrive cosa manca in `verifica-quicknotes.txt`. Se non sai cosa farne, manda quel file a chi ti ha dato l'app.

Per ritrovarla facilmente: tasto destro su `QuickNotes.cmd` › Mostra altre opzioni › **Crea collegamento**, e sposta il collegamento sul Desktop o nel menu Start.

## Primi passi

- **Le note** sono nella cartella `QuickNotes` della tua cartella utente (`C:\Users\<tu>\QuickNotes`), divise per anno e mese. In Impostazioni › Note e registrazione c'è "Apri la cartella". Ogni giorno ha la sua nota del giorno.
- **Chiudere la finestra non chiude l'app:** QuickNotes resta nell'area di notifica, vicino all'orologio. Per uscire davvero: clic destro sull'icona › Esci.
- **Tasti utili ovunque in Windows:** Ctrl Alt N per una nota rapida, Ctrl Alt D per la nota del giorno.
- **Dentro l'app:** il pulsante **?** in basso a destra (o F1) apre la guida con tutti i comandi; Ctrl K cerca ovunque.
- **Avvio con Windows:** in Impostazioni › Informazioni puoi farla partire con Windows, nascosta nell'area di notifica, così i tasti rapidi sono sempre pronti. Se poi sposti la cartella, riattivalo.

## Versioni nuove

QuickNotes non si aggiorna da sola. In Impostazioni › Informazioni vedi la tua versione, e **"Apri le release"** porta alla pagina con le versioni pubblicate. Per passare a una nuova:

1. Chiudi QuickNotes: clic destro sull'icona vicino all'orologio › Esci.
2. Scarica il nuovo `QuickNotes.zip`, sbloccalo ed estrailo al posto della vecchia cartella.
3. Riaprilo. Se avevi attivato l'avvio con Windows, riattivalo.

Le note non vengono mai toccate.

## Con Claude (facoltativo)

QuickNotes può far leggere e cercare le tue note a Claude Desktop o Claude Code. In Impostazioni › Claude trovi la configurazione già pronta da copiare, con il percorso della tua cartella. Se sposti la cartella, copiala di nuovo.
