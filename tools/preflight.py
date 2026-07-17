"""Tiny preflight helpers for run.sh / run.bat — standard library only.

Keeps the launch scripts simple and identical across platforms instead of
embedding fiddly inline Python. Subcommands:

  python tools/preflight.py port 5002    -> prints 'free' or 'busy'
  python tools/preflight.py http <url>   -> prints 'ok' or 'no'   (HTTP reachable?)
  python tools/preflight.py json <url> <key>  -> prints the top-level JSON value
"""
import json
import socket
import sys
import urllib.request


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "port":
        # connect_ex == 0 means something is already listening (busy).
        free = socket.socket().connect_ex(("127.0.0.1", int(sys.argv[2]))) != 0
        print("free" if free else "busy")
    elif cmd == "http":
        try:
            urllib.request.urlopen(sys.argv[2], timeout=3)
            print("ok")
        except Exception:  # noqa: BLE001 — any failure means "not reachable"
            print("no")
    elif cmd == "json":
        try:
            data = json.loads(urllib.request.urlopen(sys.argv[2], timeout=4).read())
            print(data.get(sys.argv[3], ""))
        except Exception:  # noqa: BLE001
            print("")
    else:
        print("")


if __name__ == "__main__":
    main()
