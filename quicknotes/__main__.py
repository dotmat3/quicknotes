"""python -m quicknotes [comando]

    (nessuno)                  apre l'app; --nascosta la lascia nell'area di notifica, --debug apre gli strumenti
    mcp                        server MCP su stdio, per Claude
    verifica [--senza-finestra]  controlla che l'app possa girare su questo PC
    reindex                    ricostruisce l'indice dai file
    where                      mostra le cartelle in uso
"""

import sys


def main() -> None:
    args = sys.argv[1:]
    command = args[0] if args and not args[0].startswith("-") else ""
    if command == "mcp":
        from .mcp import main as mcp_main
        mcp_main()
    elif command == "verifica":
        from .check import run
        sys.exit(run(with_window="--senza-finestra" not in args))
    elif command == "reindex":
        from .config import Config
        from .store import NoteStore
        store = NoteStore(Config.load().notes_path())
        print(f"Note indicizzate: {store.reindex()}")
    elif command == "where":
        from .config import Config, config_dir
        print(f"Note:           {Config.load().notes_path()}\nConfigurazione: {config_dir()}\nPython:         {sys.executable}")
    elif command:
        print(__doc__)
        sys.exit(2)
    else:
        from .app import main as app_main
        app_main(debug="--debug" in args, hidden="--nascosta" in args)


if __name__ == "__main__":
    main()
