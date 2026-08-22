"""Version stamps and branding — the two things that drift silently.

Ported from the Glossary Generator's test_docs.py, which exists because three
build manifests once sat at 0.1.0 while the app shipped 1.36.3: nothing reads
them at runtime, so nothing contradicts them.

Insights had the same drift and no test. 1.18.1 bumped desktop/package.json,
Cargo.toml and tauri.conf.json but left VERSION and frontend/package.json at
1.18.0 — and app/main.py serves the VERSION file, so the app would have
reported 1.18.0 from an installer named 1.18.1. Caught 2026-08-22.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def version():
    return read("VERSION").strip()


def test_version_is_well_formed():
    assert re.fullmatch(r"\d+\.\d+\.\d+", version()), version()


def test_every_manifest_agrees_with_VERSION():
    """VERSION is the source of truth — app/main.py serves it, so a manifest
    that disagrees names an installer whose contents say something else."""
    want = version()
    for rel in (("frontend", "package.json"), ("desktop", "package.json")):
        path = os.path.join(ROOT, *rel)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            got = json.load(f).get("version")
        assert got == want, f"{'/'.join(rel)} is {got}, VERSION is {want}"

    conf = os.path.join(ROOT, "desktop", "src-tauri", "tauri.conf.json")
    if os.path.isfile(conf):
        with open(conf, encoding="utf-8") as f:
            got = json.load(f).get("version")
        assert got == want, f"tauri.conf.json is {got}, VERSION is {want}"

    cargo = os.path.join(ROOT, "desktop", "src-tauri", "Cargo.toml")
    if os.path.isfile(cargo):
        m = re.search(r'^version\s*=\s*"([^"]+)"', read("desktop", "src-tauri",
                                                        "Cargo.toml"), re.M)
        assert m and m.group(1) == want, \
            f"Cargo.toml is {m and m.group(1)}, VERSION is {want}"


def test_the_newest_changelog_entry_is_this_version():
    m = re.search(r"^##\s*\[?v?([0-9][^\]\s]*)\]?", read("CHANGELOG.md"), re.M)
    assert m and m.group(1) == version(), \
        f"newest CHANGELOG entry is {m and m.group(1)}, VERSION is {version()}"


def _strip_comments(text):
    """Comments describe the code; they are not what ships to a screen."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)     # css / js block
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)      # html
    text = re.sub(r"^\s*//.*$", " ", text, flags=re.M)       # js line
    return text


def test_no_swirl_asset_ships():
    """1.18.1 retired the swirl for the Pentaho capital-P mark on black.

    The test is for a surviving ASSET or REFERENCE, not for the word: the
    splash page comment explains that the swirl is retired, and a test that
    fails on its own changelog is a test nobody keeps.
    """
    import glob
    named = [os.path.relpath(p, ROOT) for p in
             glob.glob(os.path.join(ROOT, "**", "*swirl*"), recursive=True)
             if ".venv" not in p and "node_modules" not in p and "target" not in p]
    assert not named, f"a swirl asset still ships: {named}"

    refs = []
    for pattern in ("frontend/src/**/*.jsx", "frontend/src/**/*.css",
                    "desktop/dist/*.html"):
        for path in glob.glob(os.path.join(ROOT, pattern), recursive=True):
            body = _strip_comments(read(os.path.relpath(path, ROOT)))
            if re.search(r"swirl", body, re.I):
                refs.append(os.path.relpath(path, ROOT))
    assert not refs, f"live swirl reference (outside comments) in: {refs}"


def test_pentaho_keeps_its_capital_P_where_a_user_can_see_it():
    """Identifiers may be lowercase — a theme id of 'pentaho' is fine. What
    must carry the capital P is anything rendered."""
    import glob
    bad = []
    for pattern in ("frontend/src/**/*.jsx", "desktop/dist/*.html"):
        for path in glob.glob(os.path.join(ROOT, pattern), recursive=True):
            rel = os.path.relpath(path, ROOT)
            body = _strip_comments(read(rel))
            visible = re.findall(r">([^<>{}]+)<", body)          # rendered text
            visible += re.findall(r"label:\s*['\"]([^'\"]+)", body)  # option labels
            visible += re.findall(r"(?:title|alt|placeholder)=['\"]([^'\"]+)", body)
            for text in visible:
                if re.search(r"pentaho", text):            # lowercase only
                    bad.append(f"{rel}: {text.strip()[:40]!r}")
    assert not bad, f"lowercase 'pentaho' where a user can see it: {bad[:5]}"
