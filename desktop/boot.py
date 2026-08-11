"""Entry point for the desktop shell's backend.

Why this exists rather than `python -m uvicorn asgi:app`:

The vendored runtime is Python's Windows "embeddable package", whose `._pth`
file REPLACES sys.path outright. The current directory is not on it, and
PYTHONPATH is ignored while a `._pth` is present - so `asgi:app` is simply not
importable, no matter what working directory the process is given. The failure
is a bare ModuleNotFoundError with nothing pointing at the cause.

Putting the app root on sys.path explicitly fixes that, and gives the packaged
and development launches ONE code path instead of two that can drift.

    python boot.py --port 5599 [--app-dir <dir>]     # the web app
    python boot.py --mcp [--app-dir <dir>]           # the MCP server (stdio)

--app-dir defaults to the directory beside this file, which is the shape
stage-app.ps1 produces:

    app/boot.py
    app/asgi.py            <- uvicorn entrypoint (loads the state-dir .env)
    app/app/main.py        <- the FastAPI factory and engine modules
    app/mcp_server/        <- MCP front door (Claude Desktop / agents)
    app/frontend/dist/     <- built React UI
"""
import argparse
import os
import sys


def _plain(path):
    r"""Drop Windows' verbatim \\?\ prefix from a drive path.

    os.chdir() cannot use one: SetCurrentDirectory rejects the verbatim form,
    so an install under C:\Program Files failed here with every path check
    passing. The shell strips it too - this is the second line of defence,
    because the cost of getting it wrong is a server that dies before it can
    say why.

    Genuine UNC paths (\\?\UNC\...) and paths over the legacy limit still need
    the prefix, so only ordinary drive paths are unwrapped.
    """
    p = str(path)
    if p.startswith("\\\\?\\"):
        rest = p[4:]
        if len(rest) > 2 and rest[1] == ":" and rest[0].isalpha() and len(rest) < 250:
            return rest
    return p


def main():
    ap = argparse.ArgumentParser(description="Start the Catalog Insights backend.")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--app-dir", default=None)
    ap.add_argument("--mcp", action="store_true",
                    help="run the MCP server instead of the web app "
                         "(stdio by default; set MCP_HTTP=1 for HTTP)")
    args = ap.parse_args()

    here = _plain(os.path.dirname(os.path.abspath(__file__)))
    app_root = _plain(os.path.abspath(args.app_dir or here))

    asgi_py = os.path.join(app_root, "asgi.py")
    if not os.path.isfile(asgi_py):
        # Explicit beats a ModuleNotFoundError three frames deep: this is the
        # message that tells whoever is reading the log that the INSTALL is
        # wrong, not the app.
        sys.exit("boot: asgi.py not found at {} - the install is incomplete".format(asgi_py))

    sys.path.insert(0, app_root)
    os.chdir(app_root)

    # Belt and braces with the shell's PYTHONDONTWRITEBYTECODE: an MCP launch
    # (Claude Desktop runs boot.py --mcp directly, without the shell's env)
    # must not compile bytecode into a read-only install tree either.
    sys.dont_write_bytecode = True

    # The state-dir .env, before anything imports app.config. asgi.py does the
    # same for the web app; the MCP path has no other loader, and doing it here
    # unconditionally (override=False, so real env always wins) keeps both
    # front doors on one rule.
    state = os.environ.get("INSIGHTS_STATE_DIR")
    if state:
        try:
            from dotenv import load_dotenv
            load_dotenv(os.path.join(state, ".env"), override=False)
        except ImportError:
            pass  # dotenv ships in requirements; a missing module surfaces later anyway

    if args.mcp:
        from mcp_server.server import main as mcp_main
        mcp_main()
        return

    if args.port is None:
        sys.exit("boot: --port is required for the web app")

    import uvicorn
    uvicorn.run("asgi:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
