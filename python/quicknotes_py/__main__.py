"""python -m quicknotes_py [verifica [--senza-finestra]] [--debug] [--nascosta]"""

import sys


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "verifica":
        from .check import run
        sys.exit(run(with_window="--senza-finestra" not in args))
    from .app import main as app_main
    app_main(debug="--debug" in args, hidden="--nascosta" in args)


if __name__ == "__main__":
    main()
