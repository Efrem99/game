"""Alternative silent launcher used by start_game.bat."""

from launchers.bootstrap import run_app, show_messagebox_error


def main():
    return run_app(
        startup_tag="--- Starting XBot RPG (run_game.pyw) ---",
        error_handler=show_messagebox_error,
    )


if __name__ == "__main__":
    main()

