"""Fast local ComfyUI path check; does not launch or download anything."""
import json
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from core.comfyui_setup import resolve_portable, server_available
try:
    file = root / "data/settings.json"
    if not file.exists(): file = root / "settings.json"
    if not file.exists(): file = root / "config/settings.example.json"
    settings = json.loads(file.read_text(encoding="utf-8-sig"))
    if server_available(settings.get("COMFYUI_URL", "http://127.0.0.1:8188")):
        print("[OK] ComfyUI server is available.")
        sys.exit(0)
    try:
        resolve_portable(settings.get("COMFYUI_DIR", ""), root)
        print("[OK] ComfyUI portable Python and main.py found.")
    except ValueError:
        print("[CONFIG] ComfyUI portable installation is missing or incomplete.")
        print("Studio will show a ComfyUI setup panel. You can also use Logs & Settings > Folders.")
        print("Paste the folder containing python_embeded and ComfyUI, then click Check and save folder.")
        print("Restart Studio after saving. Image/video generation needs a working ComfyUI server.")

except (OSError, ValueError, TypeError, AttributeError) as exc:
    print("[CONFIG] Cannot check ComfyUI settings: " + str(exc))
