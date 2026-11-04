"""Private runtime files, with migration from the original root layout."""
import json
import os
from pathlib import Path


def prepare_runtime_files(root):
    root = Path(root).resolve()
    data = root / "data"
    data.mkdir(exist_ok=True)
    target = data / "settings.json"
    legacy = root / "settings.json"
    # Never overwrite either copy if both exist: the current layout wins.
    source = target if target.exists() else legacy
    settings = None
    if source.exists():
        settings = json.loads(source.read_text(encoding="utf-8-sig"))
        if not isinstance(settings, dict):
            raise ValueError("Settings must contain a JSON object")
        session = Path(settings.get("SESSION_FILE", "session.json"))
        session = session if session.is_absolute() else root / session
        if session.resolve() == (root / "session.json").resolve():
            destination = data / "session.json"
            if session.exists() and destination.exists():
                raise ValueError("Both old and new session files exist. Keep the desired session in data/session.json and remove the duplicate before restarting.")
            if session.exists():
                session.rename(destination)
            settings["SESSION_FILE"] = "data/session.json"
        # Write first, then remove the old settings: an interruption cannot lose them.
        tmp = data / "settings.migration.tmp"
        tmp.write_text(json.dumps(settings, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, target)
        if source == legacy:
            legacy.unlink()
    elif (root / "session.json").exists() and not (data / "session.json").exists():
        (root / "session.json").rename(data / "session.json")
    return target
