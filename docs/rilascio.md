# Rilasciare QuickNotes

Come pubblicare una versione. La guida da dare ai colleghi è [installazione.md](installazione.md).

## Come funziona

Ogni versione è una release su GitHub con due eseguibili:

| File | Cos'è |
|---|---|
| `QuickNotes.exe` | L'app, con l'interfaccia già dentro. Si scarica e si avvia: niente installer, niente amministratore |
| `quicknotes-mcp.exe` | Il server MCP per Claude, facoltativo. Va nella stessa cartella di `QuickNotes.exe` |

Non ci sono aggiornamenti automatici. Chi vuole la versione nuova la scarica e sostituisce i file, ad app chiusa. I nomi non cambiano tra una versione e l'altra, quindi questo link porta sempre all'ultima:
`https://github.com/<tuo-utente>/quicknotes/releases/latest/download/QuickNotes.exe`

In Impostazioni › Informazioni l'app mostra la versione e un pulsante che apre la pagina delle release.

Per i colleghi c'è anche una pagina di presentazione con il pulsante di download e le istruzioni, pubblicata come artefatto di Claude: <https://claude.ai/artifact/AkHt8yRBtSwkSyJJBpJ2Ym>. È privata finché non la condividi dal menu Condividi. I suoi link puntano a `releases/latest`, quindi scaricano sempre l'ultima versione.

## Una volta sola

Serve un repository GitHub con **release pubbliche**: chi scarica non deve avere un account. Il codice può restare privato, basta un repository pubblico che contiene solo le release. Annota il nome completo, `<tuo-utente>/quicknotes`.

## A ogni versione

1. **Alza il numero di versione** in `Cargo.toml`, alla riga `version = "…"` della sezione `[workspace.package]`, e in `frontend/package.json`: `0.3.0` → `0.3.1` per correzioni, `0.4.0` per novità.
2. **Controlla che tutto sia verde:** i comandi di "Come riprendere il lavoro" in [piano-incrementale.md](piano-incrementale.md).
3. **Costruisci il rilascio:**

   ```bash
   node scripts/rilascio.mjs --repo <tuo-utente>/quicknotes --note "Cosa cambia, in una o due frasi"
   ```

   La prima volta `--repo` si ricorda in `scripts/rilascio.json`; dopo basta `--note`. Lo script compila server MCP e app e mette in `rilasci/v<versione>/` i due `.exe` e `note-release.md`, la descrizione della release con le istruzioni per chi scarica.
4. **Pubblica su GitHub:** apri `https://github.com/<tuo-utente>/quicknotes/releases/new`.
   - Tag: `v<versione>`, per esempio `v0.3.1`. Titolo: `QuickNotes <versione>`.
   - Come descrizione incolla `note-release.md`.
   - Allega `QuickNotes.exe` e `quicknotes-mcp.exe`.
   - Lascia spuntato "Set as the latest release", poi premi "Publish release".
5. **Controlla:** scarica `QuickNotes.exe` dal link `releases/latest/download/…` e avvialo.
6. **Aggiorna la pagina di presentazione:** i download funzionano già, ma il numero di versione scritto nella pagina va cambiato. Chiedi a Claude di aggiornare l'artefatto all'indirizzo qui sopra con la nuova versione.

### Se una versione ha un problema

Pubblica subito una versione con un numero più alto, che corregge o ripristina. Una release difettosa si può anche togliere da GitHub: il link `latest` torna alla precedente.

## Cosa sapere sui PC aziendali

- **Avviso di Windows (SmartScreen):** l'eseguibile non ha un certificato di firma del codice, quindi al primo avvio Windows mostra "Windows ha protetto il PC". Si va avanti con "Ulteriori informazioni" › "Esegui comunque". Alcune aziende bloccano del tutto i programmi non firmati, o quelli avviati da Download: in quel caso serve parlarne con l'IT. La soluzione stabile è un certificato di firma del codice: dell'azienda, oppure un servizio come Azure Trusted Signing.
- **WebView2:** l'app usa il motore di Edge, già presente su Windows 10 e 11 aggiornati. Senza installer nessuno lo installa al posto tuo: se mancasse, l'app non si apre e va installato il "WebView2 Runtime" di Microsoft.
- **Dati:** le note restano in `%USERPROFILE%\QuickNotes` e la configurazione in `%USERPROFILE%\.quicknotes`, ovunque sia l'eseguibile. Sostituirlo o cancellarlo non le tocca. WebView2 tiene la sua cache in `%LOCALAPPDATA%\it.quicknotes.app`.
- **Avvio con Windows** salva il percorso dell'eseguibile. Se si sostituisce `QuickNotes.exe` nella stessa cartella continua a funzionare; se lo si sposta va riattivato.

## Dettagli tecnici

- `tauri build --no-bundle` con `bundle.active: false`: niente installer, solo `target/release/quicknotes.exe`, che lo script copia come `QuickNotes.exe`. Icona, nome e copyright entrano comunque nell'eseguibile.
- L'indirizzo delle release entra nell'app al momento della compilazione, con la variabile `QUICKNOTES_RELEASES` impostata dallo script. Le copie compilate a mano non ce l'hanno e non mostrano il pulsante.
- L'identificatore `it.quicknotes.app` non va cambiato: WebView2 lo usa per la cartella dei suoi dati.
- Chi aveva installato la 0.3.0 con l'installer può disinstallarla da Impostazioni di Windows › App e usare l'eseguibile: le note non si toccano. Finché resta installata, il controllo degli aggiornamenti non trova più `latest.json` e lo segnala solo in Impostazioni › Informazioni.
