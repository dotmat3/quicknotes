# Rilasciare QuickNotes

Come pubblicare una versione. La guida da dare ai colleghi è [installazione.md](installazione.md).

## Come funziona

Ogni versione è una release su GitHub con un solo file, **`QuickNotes.zip`**: una cartella portatile che contiene l'app, l'interfaccia già compilata, le librerie e il Python "embeddable" ufficiale di python.org. Si estrae e si usa: niente installer, niente amministratore, niente Python da installare. Il server MCP per Claude è dentro, come `python -m quicknotes mcp`.

Non ci sono aggiornamenti automatici. Chi vuole la versione nuova la scarica e sostituisce la cartella, ad app chiusa. Il nome non cambia tra una versione e l'altra, quindi questo link porta sempre all'ultima:
`https://github.com/dotmat3/quicknotes/releases/latest/download/QuickNotes.zip`

In Impostazioni › Informazioni l'app mostra la versione e un pulsante che apre la pagina delle release.

Per i colleghi c'è anche una pagina di presentazione con il pulsante di download e le istruzioni, pubblicata come artefatto di Claude: <https://claude.ai/artifact/AkHt8yRBtSwkSyJJBpJ2Ym>. È privata finché non la condividi dal menu Condividi. Fino alla 0.3.1 scaricava `QuickNotes.exe`: con la prima versione Python va aggiornata perché scarichi `QuickNotes.zip` e spieghi lo sblocco.

## A ogni versione

1. **Alza il numero di versione** in `quicknotes/__init__.py` (`__version__`) e in `frontend/package.json`: `0.4.0` → `0.4.1` per correzioni, `0.5.0` per novità.
2. **Controlla che tutto sia verde:**

   ```bash
   .venv/Scripts/python -m unittest discover -s tests
   cd frontend && npx vitest run && cd ..
   node scripts/prova-python.mjs
   ```

   e le prove `scripts/prova-*.mjs` toccate dalle modifiche (vedi il README).
3. **Costruisci il rilascio:**

   ```bash
   node scripts/rilascio.mjs --note "Cosa cambia, in una o due frasi"
   ```

   Lo script compila l'interfaccia, scarica una volta sola il Python embeddable della stessa versione di `.venv` (resta in `dist/cache`), installa le librerie e mette in `rilasci/v<versione>/` `QuickNotes.zip` e `note-release.md`, la descrizione della release con le istruzioni per chi scarica.
4. **Prova lo zip come un collega:** estrailo in una cartella nuova e apri `Verifica.cmd`, poi `QuickNotes.cmd`. `QN_PYTHON=<cartella>/QuickNotes/python/pythonw.exe node scripts/prova-python.mjs` fa la prova dal vivo sulla cartella estratta.
5. **Pubblica su GitHub:** apri `https://github.com/dotmat3/quicknotes/releases/new`.
   - Tag: `v<versione>`, per esempio `v0.4.0`. Titolo: `QuickNotes <versione>`.
   - Come descrizione incolla `note-release.md`.
   - Allega `QuickNotes.zip`.
   - Lascia spuntato "Set as the latest release", poi premi "Publish release".
6. **Controlla:** scarica `QuickNotes.zip` dal link `releases/latest/download/…`, estrailo e avvialo.
7. **Aggiorna la pagina di presentazione** con il nuovo numero di versione: chiedi a Claude di aggiornare l'artefatto all'indirizzo qui sopra.

### Se una versione ha un problema

Pubblica subito una versione con un numero più alto, che corregge o ripristina. Una release difettosa si può anche togliere da GitHub: il link `latest` torna alla precedente.

## Cosa sapere sui PC aziendali

- **Firma:** `python.exe` e `pythonw.exe` sono quelli ufficiali, firmati dalla Python Software Foundation. Le regole aziendali che bloccano gli eseguibili non firmati di solito li lasciano passare; `QuickNotes.cmd` e `Verifica.cmd` sono semplici file di comandi che li avviano.
- **Zip non sbloccato:** i file estratti portano il marchio "scaricato da internet" e .NET Framework rifiuterebbe le DLL di pythonnet. Per questo la cartella include `python.exe.config` e `pythonw.exe.config` con `loadFromRemoteSources`, e funziona anche senza sbloccare; sbloccare resta la cosa giusta da fare.
- **WebView2 e .NET Framework 4.7.2:** presenti su Windows 10 e 11 aggiornati. Se mancano, `Verifica.cmd` lo dice.
- **Regole sulle DLL (AppLocker, WDAC) o antivirus:** se bloccano le DLL non firmate di pythonnet, la verifica lo segnala sotto la riga di pythonnet. Serve un'eccezione dall'IT per la cartella dell'app.
- **Dati:** le note restano in `%USERPROFILE%\QuickNotes` e la configurazione in `%USERPROFILE%\.quicknotes`, ovunque sia la cartella dell'app. Sostituirla o cancellarla non le tocca. WebView2 tiene la sua cache in `%USERPROFILE%\.quicknotes\webview`.
- **Avvio con Windows** salva il percorso di `pythonw.exe` nella cartella dell'app. Se si sostituisce la cartella nello stesso posto continua a funzionare; se la si sposta va riattivato.

## Dettagli tecnici

- `scripts/costruisci.py` usa il Python di `.venv`: la versione dell'embeddable e le ruote delle librerie sono quindi quelle giuste per Windows x64.
- Il file `python3XX._pth` dell'embeddable elenca `lib` e `app`: Python cerca i moduli solo lì, ignora `PYTHONPATH` e la cartella corrente.
- `proxy_tools`, richiesto da pywebview, esiste solo come sorgente: per questo pip installa senza `--only-binary`.
