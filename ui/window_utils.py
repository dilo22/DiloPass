import os
import sys


def get_icon_path() -> str | None:
    # Support dev mode and PyInstaller onefile/onedir.
    base_dir = getattr(sys, "_MEIPASS", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    icon_path = os.path.join(base_dir, "assets", "icon.ico")
    return icon_path if os.path.exists(icon_path) else None


def apply_window_icon(window) -> None:
    icon_path = get_icon_path()
    if not icon_path:
        return
    try:
        window.iconbitmap(icon_path)
    except Exception:
        pass
