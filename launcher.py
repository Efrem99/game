"""Console launcher for XBot RPG."""

from launchers.bootstrap import run_app


def main():
    return run_app(
        startup_tag="--- Starting XBot RPG ---",
        pause_on_error=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())

