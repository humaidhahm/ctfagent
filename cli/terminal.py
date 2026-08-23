import atexit
import sys


BACKGROUND = "#101725"


def setup_terminal():
    if not sys.stdout.isatty():
        return

    # Enter alternate screen buffer
    sys.stdout.write("\033[?1049h")

    # Set terminal background
    sys.stdout.write(f"\033]11;{BACKGROUND}\007")

    sys.stdout.flush()

    # Always restore terminal when the program exits
    atexit.register(restore_terminal)


def restore_terminal():
    if not sys.stdout.isatty():
        return

    # Reset terminal background
    sys.stdout.write("\033]111\007")

    # Leave alternate screen buffer
    sys.stdout.write("\033[?1049l")

    sys.stdout.flush()
