"""Single authoritative location for all data files: ./databases/.

No fallback to home directories, TR4QT paths, or CWD. If a required file
is not in ./databases/, the caller should fault with a clear message and
point the user at `--update-data`.
"""

import os


def databases_dir() -> str:
    """Return the databases directory path (./databases/ relative to CWD)."""
    return os.path.join(os.getcwd(), "databases")


def data_path(filename: str) -> str:
    """Return the expected absolute path for a data file."""
    return os.path.join(databases_dir(), filename)


def find_data_file(filename: str, cli_path: str | None = None) -> str | None:
    """Return cli_path if it exists, else ./databases/<filename> if it exists."""
    if cli_path and os.path.isfile(cli_path):
        return cli_path
    p = data_path(filename)
    return p if os.path.isfile(p) else None
