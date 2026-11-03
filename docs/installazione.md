# Installare QuickNotes

QuickNotes è un'app per Windows per prendere note di riunione, tenere traccia di azioni e decisioni e ritrovare tutto con la ricerca. Le note sono file Markdown sul tuo computer: nessun account, nessun cloud.

## Cosa serve

- Windows 10 o 11.
- Non servono permessi di amministratore: QuickNotes si installa solo per il tuo utente.

## Installazione

1. Scarica l'ultima versione da **[link alla pagina delle release]**: il file si chiama `QuickNotes_<versione>_x64-setup.exe`.
2. Aprilo. Windows potrebbe mostrare **"Windows ha protetto il PC"**, perché l'app non ha ancora un certificato di firma del codice: premi **"Ulteriori informazioni"**, poi **"Esegui comunque"**.
   Se il PC aziendale blocca l'installazione e non compare "Esegui comunque", scrivi a chi ti ha mandato l'app: va chiesto all'IT.
3. Segui l'installazione e, alla fine, lascia spuntato "Avvia QuickNotes".

QuickNotes si trova poi nel menu Start.

## Primi passi

- **Le note** sono nella cartella `QuickNotes` della tua cartella utente (`C:\Users\<tu>\QuickNotes`), divise per anno e mese. In Impostazioni › Note e registrazione c'è "Apri la cartella". Ogni giorno ha la sua nota del giorno.
- **Chiudere la finestra non chiude l'app:** QuickNotes resta nell'area di notifica, vicino all'orologio. Per uscire davvero: clic destro sull'icona › Esci.
- **Tasti utili ovunque in Windows:** Ctrl Alt N per una nota rapida, Ctrl Alt D per la nota del giorno.
- **Dentro l'app:** il pulsante **?** in basso a destra (o F1) apre la guida con tutti i comandi; Ctrl K cerca ovunque.
- **Avvio con Windows:** in Impostazioni › Informazioni puoi farla partire con Windows, nascosta nell'area di notifica, così i tasti rapidi sono sempre pronti.

## Aggiornamenti

Qualche secondo dopo l'avvio QuickNotes controlla se c'è una versione nuova. Se c'è, nella barra in alto compare **"Aggiornamento x.y.z"**:

1. Premilo: si apre Impostazioni › Informazioni con le novità.
2. Premi **"Aggiorna e riavvia"**. QuickNotes salva le note, si aggiorna e si riapre da sola in pochi secondi.

Niente si aggiorna senza il tuo clic, e le note non vengono mai toccate. Se la rete aziendale non lascia controllare gli aggiornamenti, l'app funziona lo stesso: basta scaricare e lanciare il nuovo installer, che aggiorna senza perdere nulla.

## Con Claude (facoltativo)

QuickNotes può far leggere e cercare le tue note a Claude Desktop o Claude Code. In Impostazioni › Claude trovi il blocco di configurazione già pronto da copiare.

## Disinstallare

Impostazioni di Windows › App › App installate › QuickNotes › Disinstalla. Le note in `C:\Users\<tu>\QuickNotes` restano dove sono: per eliminarle va cancellata a mano quella cartella.
