# Rilasciare QuickNotes

Come pubblicare una versione e come arrivano gli aggiornamenti ai colleghi. La guida da dare a loro è [installazione.md](installazione.md).

## Come funzionano gli aggiornamenti

1. Ogni versione è un installer per Windows, firmato con una chiave privata che hai solo tu.
2. La pubblichi come release su GitHub, insieme a un piccolo file, `latest.json`, che dice qual è l'ultima versione.
3. Qualche secondo dopo l'avvio, ogni copia installata legge `latest.json`. Se c'è una versione più nuova, nella barra del titolo compare il pulsante "Aggiornamento x.y.z".
4. Il collega lo preme, e in Impostazioni › Informazioni preme "Aggiorna e riavvia". L'app salva le note, scarica l'installer, **controlla la firma**, si chiude, si aggiorna e si riapre.

Niente si installa senza il clic del collega. Un installer che non porta la tua firma viene rifiutato, anche se qualcuno riuscisse a metterlo nella release.

## Una volta sola

### 1. Il repository GitHub per i rilasci

Le copie installate scaricano gli aggiornamenti senza account, quindi **le release devono essere pubbliche**. Il codice può restare privato: basta un repository pubblico che contiene solo le release.

1. Su GitHub crea un repository pubblico, per esempio `quicknotes`. Può restare vuoto, oppure avere un README che rimanda alla guida d'installazione.
2. Annota il nome completo, `<tuo-utente>/quicknotes`: serve allo script di rilascio.

Le copie installate cercano gli aggiornamenti a questo indirizzo, scritto dentro l'app:
`https://github.com/<tuo-utente>/quicknotes/releases/latest/download/latest.json`

**Non va più cambiato**: le copie già installate continuerebbero a cercare quello vecchio. Se un giorno servisse spostarlo, la versione che lo cambia va pubblicata anche al vecchio indirizzo.

### 2. La chiave di firma: fai subito una copia

Le chiavi sono in `C:\Users\<tu>\.tauri\`:

| File | Cos'è |
|---|---|
| `quicknotes.key` | Chiave privata. Firma ogni versione. **Non va mai condivisa né messa in un repository** |
| `quicknotes.key.password` | La sua password |
| `quicknotes.key.pub` | Chiave pubblica, già scritta in `tauri.conf.json`. Si può mostrare a chiunque |

Copia `quicknotes.key` e la password in un posto sicuro fuori da questo PC, per esempio un gestore di password. **Se la chiave si perde, le copie installate non accettano più aggiornamenti**: bisognerebbe rifare la chiave e far reinstallare a mano la nuova versione a tutti.

## A ogni versione

1. **Alza il numero di versione** in `Cargo.toml`, alla riga `version = "…"` della sezione `[workspace.package]`, e in `frontend/package.json`. Il numero deve crescere: `0.3.0` → `0.3.1` per correzioni, `0.4.0` per novità.
2. **Controlla che tutto sia verde:** i comandi di "Come riprendere il lavoro" in [piano-incrementale.md](piano-incrementale.md).
3. **Costruisci il rilascio:**

   ```bash
   node scripts/rilascio.mjs --repo <tuo-utente>/quicknotes --note "Cosa cambia, in una o due frasi"
   ```

   La prima volta `--repo` si ricorda in `scripts/rilascio.json`; dopo basta `--note`. Il testo di `--note` è quello che i colleghi leggono in Impostazioni › Informazioni prima di aggiornare. Lo script compila server MCP e app, crea l'installer, lo firma e scrive tutto in `rilasci/v<versione>/`.
4. **Pubblica su GitHub:** apri `https://github.com/<tuo-utente>/quicknotes/releases/new`.
   - Tag: `v<versione>`, per esempio `v0.3.0`.
   - Titolo: `QuickNotes <versione>`.
   - Allega **due file** da `rilasci/v<versione>/`: `QuickNotes_<versione>_x64-setup.exe` e `latest.json`. Il file `.sig` non serve: la firma è già dentro `latest.json`.
   - Lascia spuntato "Set as the latest release", poi premi "Publish release".
5. **Controlla:** su un PC con la versione precedente installata, riavvia QuickNotes. Entro una decina di secondi compare il pulsante di aggiornamento.

Prima di pubblicare, la prova completa di installazione e aggiornamento si fa sul tuo PC, senza GitHub, con installer di prova serviti da un server locale. Vedi l'intestazione di `scripts/prova-aggiornamento.mjs`. Installa in una cartella temporanea, usa note di prova e alla fine disinstalla.

### Se una versione ha un problema

Non si torna indietro: si pubblica subito una versione con un numero più alto, che corregge o ripristina. Una release con un difetto si può anche togliere da GitHub. Le copie che non si sono ancora aggiornate vedranno di nuovo come "ultima" la release precedente; quelle già aggiornate restano dove sono finché non esce una versione più nuova.

## Cosa sapere sui PC aziendali

- **Installazione senza amministratore:** l'installer mette l'app in `%LOCALAPPDATA%\QuickNotes`, solo per l'utente. Funziona anche senza diritti di amministratore, salvo politiche aziendali che bloccano i programmi installati nel profilo.
- **Avviso di Windows (SmartScreen):** l'installer non ha un certificato di firma del codice, quindi al primo avvio Windows mostra "Windows ha protetto il PC". Si va avanti con "Ulteriori informazioni" › "Esegui comunque". Alcune aziende bloccano del tutto i programmi non firmati: in quel caso serve parlarne con l'IT. La soluzione stabile è un certificato di firma del codice: dell'azienda, oppure un servizio come Azure Trusted Signing. La firma degli aggiornamenti descritta sopra è un'altra cosa e c'è già.
- **Rete:** gli aggiornamenti passano da `github.com` e `objects.githubusercontent.com`. Se la rete aziendale li blocca, l'app lo dice in Impostazioni › Informazioni e continua a funzionare; l'installer nuovo si può sempre scaricare e lanciare a mano, e aggiorna senza perdere nulla.
- **WebView2:** l'app usa il motore di Edge, già presente su Windows 10 e 11 aggiornati. Se mancasse, l'installer prova a scaricarlo.
- **Dati:** le note restano in `%USERPROFILE%\QuickNotes` e la configurazione in `%USERPROFILE%\.quicknotes`. Aggiornare o disinstallare non le tocca.

## Dettagli tecnici

- Installer NSIS per utente (`bundle.windows.nsis.installMode: currentUser`), in italiano. Il server MCP entra nell'installer come `externalBin` solo nel rilascio, così la compilazione di tutti i giorni non ne ha bisogno.
- Aggiornamenti con `tauri-plugin-updater`. Chiave pubblica in `tauri.conf.json`; l'indirizzo di `latest.json` lo aggiunge lo script, quindi le copie compilate a mano non cercano aggiornamenti e lo dicono.
- Al riavvio dopo un aggiornamento l'installer riapre l'app con gli stessi argomenti: un'app avviata con Windows (`--nascosta`) o su un'altra cartella (`--cartella-note=`) resta tale.
- L'identificatore `it.quicknotes.app` non va cambiato: Windows lo usa per riconoscere l'app installata e i suoi dati. Il nome mostrato invece può cambiare.
