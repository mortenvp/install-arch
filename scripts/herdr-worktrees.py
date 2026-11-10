#!/usr/bin/env python3
"""Install the reviewed personal Herdr layout without editing any shipped files."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1] / "patches/herdr-worktrees"
MODS = ("wt-worktree", "wt-menu", "wt-new-menu", "wt-tabs", "wt-spaces")
MANIFEST = ".install-arch-worktrees.json"
LAYOUT = "wt"


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(app, relative):
    path = app
    for part in ("", *Path(relative).parts):
        if part in ("..", "/"):
            raise ValueError(f"Unsafe managed path: {relative}")
        path = path / part
        if path.is_symlink():
            raise ValueError(f"Refusing symlink: {path}")
    return path


def read_optional(path):
    return path.read_bytes() if path.exists() else None


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".wt-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            os.fchmod(stream.fileno(), 0o644)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def templates():
    result = {"layouts/wt.json": (SOURCE / "layouts/wt.json").read_bytes()}
    license_text = (SOURCE / "LICENSE").read_bytes()
    for mod in MODS:
        for filename in ("main.js", "mod.json"):
            relative = f"mods/{mod}/{filename}"
            result[relative] = (SOURCE / relative).read_bytes()
        result[f"mods/{mod}/LICENSE"] = license_text
    return result


def read_manifest(app, allowed):
    data = read_optional(safe_path(app, MANIFEST))
    if data is None:
        return {}
    record = json.loads(data)
    if not isinstance(record, dict) or record.get("version") != 1 or not isinstance(record.get("files"), dict):
        raise ValueError(f"Invalid ownership record: {app / MANIFEST}")
    files = record["files"]
    if set(files) - set(allowed) or not all(isinstance(v, str) for v in files.values()):
        raise ValueError(f"Unexpected managed files in {app / MANIFEST}")
    return files


def selection(app):
    """Use IPC while Herdr runs; never race its shared-state writer."""
    result = subprocess.run(["herdr-app", "status"], capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        return True, json.loads(result.stdout)["layout"]
    if (app / "herdr-app.sock").exists():
        raise ValueError("Herdr's socket exists but status failed; resolve that before installing.")
    state = read_optional(safe_path(app, "shared.json"))
    shared = json.loads(state) if state is not None else {}
    if not isinstance(shared, dict):
        raise ValueError(f"Expected an object in {app / 'shared.json'}")
    return False, shared.get("layout", "main")


def select_layout(app, running, name):
    if running:
        subprocess.run(["herdr-app", "do", "layout.switch", json.dumps({"name": name})],
                       check=True, capture_output=True, text=True, timeout=10)
    else:
        path = safe_path(app, "shared.json")
        current = read_optional(path)
        shared = json.loads(current) if current is not None else {}
        shared["layout"] = name
        atomic_write(path, encoded(shared))


def check_mods(app, files):
    # A failed check must leave the installation and selected layout untouched.
    with tempfile.TemporaryDirectory(prefix="herdr-wt-check-") as temporary:
        stage = Path(temporary)
        for relative, data in files.items():
            path = stage / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for mod in MODS:
            result = subprocess.run(["herdr-app", "check", str(stage / "mods" / mod)],
                                    env=dict(os.environ, HERDR_APP_HOME=str(app)),
                                    capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise ValueError(f"Herdr check failed for {mod}:\n{result.stdout}{result.stderr}")


def backup(app, paths):
    existing = {relative: read_optional(safe_path(app, relative)) for relative in paths}
    existing = {relative: data for relative, data in existing.items() if data is not None}
    if not existing:
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    root = safe_path(app, f"backups/wt-worktrees/{stamp}")
    for relative, data in existing.items():
        atomic_write(root / relative, data)
    print(f"Backup: {root}")


def install(app, files, previous, running, active):
    for relative, desired in files.items():
        current = read_optional(safe_path(app, relative))
        if current is None:
            continue
        if relative in previous:
            if digest(current) != previous[relative]:
                raise ValueError(f"Refusing to overwrite an edited file: {app / relative}")
        elif current != desired:
            raise ValueError(f"Refusing to overwrite an unrelated file: {app / relative}")

    check_mods(app, files)
    changes = {relative: data for relative, data in files.items()
               if read_optional(app / relative) != data}
    record = encoded({"version": 1, "files": {k: digest(v) for k, v in files.items()}})
    if read_optional(app / MANIFEST) != record:
        changes[MANIFEST] = record
    backups = list(changes)
    if not running and active != LAYOUT:
        backups.append("shared.json")
    backup(app, backups)
    for relative, data in changes.items():
        atomic_write(safe_path(app, relative), data)
    if active != LAYOUT:
        select_layout(app, running, LAYOUT)
    print("Herdr WT layout selected: <main-checkout>.worktrees/<branch>.")
    print("Existing worktrees were not moved. Shipped Herdr files were not changed.")


def uninstall(app, previous, running, active):
    if not previous:
        print("Herdr WT layout is not installed; nothing to remove.")
        return
    for relative, expected in previous.items():
        current = read_optional(safe_path(app, relative))
        if current is not None and digest(current) != expected:
            raise ValueError(f"Refusing to remove an edited file: {app / relative}")
    paths = [*previous, MANIFEST]
    if not running and active == LAYOUT:
        paths.append("shared.json")
    backup(app, paths)
    if active == LAYOUT:
        select_layout(app, running, "main")
    for relative in previous:
        safe_path(app, relative).unlink(missing_ok=True)
    safe_path(app, MANIFEST).unlink()
    # Leave editor helpers, mod state and unrelated files alone.
    for mod in MODS:
        path = app / "mods" / mod
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    print("Removed Herdr WT files; existing worktrees and terminals were not changed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    app = Path(os.environ.get("HERDR_APP_HOME") or
               str(Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") /
                   "herdr-app")).expanduser().absolute()
    files = templates()
    previous = read_manifest(app, files)
    running, active = selection(app)
    if args.uninstall:
        uninstall(app, previous, running, active)
    else:
        install(app, files, previous, running, active)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(f"Herdr worktrees: {error}") from error
