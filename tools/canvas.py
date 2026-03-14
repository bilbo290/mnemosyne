import json
import os
from pathlib import Path

from app import mcp
from core.db import CHROMA_PATH

CANVAS_CONFIG_PATH = str(Path(CHROMA_PATH).parent / "canvas.json")


def _load_config() -> dict:
    if os.path.exists(CANVAS_CONFIG_PATH):
        with open(CANVAS_CONFIG_PATH) as f:
            return json.load(f)
    return {}


def _save_config(config: dict):
    Path(CANVAS_CONFIG_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(CANVAS_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


@mcp.tool()
def canvas(
    action: str,
    project_id: str,
    file_path: str = "",
    text: str = "",
    label: str = "",
    mode: str = "append",
    save_to_memory: bool = True,
    order: int | None = None,
    tags: list[str] | None = None,
    tail_lines: int | None = None,
) -> dict:
    """Write scenes to a file instead of chat (saves context).

    Actions:
      setup — set canvas file path (needs: file_path)
      write — write to canvas (needs: text; optional: label, mode, save_to_memory, order, tags)
      read — read canvas content (optional: tail_lines to limit)
      clear — clear the canvas

    Args:
        action: setup, write, read, or clear
        project_id: Project ID
        file_path: Canvas file path (for setup)
        text: Content to write (for write)
        label: Section label for memory (for write)
        mode: append or overwrite (for write)
        save_to_memory: Also save to project memory (for write, default true)
        order: Section order (for write)
        tags: Tags (for write)
        tail_lines: Only return last N lines (for read)
    """
    if action == "setup":
        config = _load_config()
        config[project_id] = file_path
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        if not os.path.exists(file_path):
            Path(file_path).touch()
        _save_config(config)
        return {"path": file_path, "status": "configured"}

    # All other actions need a configured canvas
    config = _load_config()
    path = config.get(project_id)
    if not path:
        return {"error": "No canvas configured. Use action=setup first."}

    if action == "write":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        wc = len(text.split())
        if mode == "overwrite":
            with open(path, "w") as f:
                f.write(text)
        else:
            with open(path, "a") as f:
                if os.path.exists(path) and os.path.getsize(path) > 0:
                    f.write("\n\n---\n\n")
                f.write(text)
        result = {"status": "written", "words": wc}
        if save_to_memory and label:
            from tools.content import save_content
            save_content(text=text, project_id=project_id, label=label, order=order, tags=tags)
            result["memory"] = "saved"
        return result

    if action == "read":
        if not os.path.exists(path):
            return {"content": "", "words": 0}
        with open(path) as f:
            c = f.read()
        if tail_lines and c:
            c = "\n".join(c.split("\n")[-tail_lines:])
        return {"content": c, "words": len(c.split()) if c else 0}

    if action == "clear":
        if os.path.exists(path):
            with open(path, "w") as f:
                f.write("")
        return {"status": "cleared"}

    return {"error": f"Unknown action '{action}'. Use: setup, write, read, clear"}
