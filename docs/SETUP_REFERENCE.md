# Configuration and diagnostics

[Back to the overview](README.md)

## Folder details: ComfyUI and LoRAs

### Set the ComfyUI folder

In **Logs & Settings → Local ComfyUI**, paste the Windows Portable folder containing `python_embeded` and `ComfyUI` (not the `models` folder). Click **Check and save folder**, then restart Studio. Selecting the `ComfyUI` subfolder also works: Studio detects its parent automatically. Invalid paths do not replace the saved setting. This feature does not install ComfyUI.

### LoRA folders

Each family uses one folder under `ComfyUI/models/loras`: `Z-Image`, `Flux-2`, `Krea-2`, `Qwen2.1`, `LTX-2.5`, `MiniMax`. Paths in `data/settings.json` derive from `{COMFYUI_DIR}`: configure the main ComfyUI folder once. Existing `Z-Image1` and `Z-Image2` folders remain readable for compatibility; put new Z-Image LoRAs in `Z-Image`. Model files are never moved automatically.

## Preview status

- Dependency resolution was checked for Windows / Python 3.11; transitive versions are recorded in `scripts/constraints-win-py311.txt`.
- Workflow wiring and UI callbacks have been tested; a fresh installation and every model/workflow combination still need end-to-end testing.
- Offline manuals in Italian and English are bundled: use **?** and select the language, or open `help/help.html` / `help/help.en.html`.
- This is a beta. Supported workflow profiles are checked automatically; generation quality and hardware compatibility still require real-world testing.

When reporting a problem, include the workflow/model, reproduction steps and relevant logs. Remove personal prompts, paths and credentials first.

The installer also checks Python, dependencies, GPU/CUDA, folders and ComfyUI. Repeat with `scripts/check_installation.bat` or **Logs & Settings → Diagnostics → Check installation**. Start ComfyUI to check workflow nodes and models. `CONFIG` means setup or further checks are needed for the desired features; checks do not download models or certify a complete generation.

System instructions can be customized without editing Python: see the [template and local override guide](../suggestions/system/README.md).

### Project folders

Start and update with the two `.bat` files in the main folder. The start launcher runs installation automatically when the environment or its main dependencies are missing. You can also install with `scripts/install.bat`; run diagnostics with `scripts/check_installation.bat`. The small root `requirements.txt` preserves compatibility with older updaters.

- `config/`: model catalog, workflow parameters and example settings.
- `scripts/`: updater and dependency constraints.
- `docs/`: installation notes, third-party notices and file manifest.
- `workflows/`: API workflows and editable profiles.
- `suggestions/`: editable prompt instructions and examples.
- `help/`: illustrated user guide.

Personal settings and sessions are stored in `data/` and excluded from Git. Existing files are transferred automatically on startup. Installation and diagnostic tools are in `scripts/`.
