# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec pour DiloPass
# Généré pour Python 3.13 / Windows
#
# Pour builder :
#   pip install pyinstaller
#   pyinstaller dilopass.spec

import os
import customtkinter

# Dossier des assets CustomTkinter (thèmes, images)
ctk_path = os.path.dirname(customtkinter.__file__)

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        (ctk_path, "customtkinter/"),   # thèmes et assets CTk obligatoires
    ],
    hiddenimports=[
        "customtkinter",
        "PIL._tkinter_finder",          # Pillow + tkinter
        "PIL.Image",
        "PIL.ImageTk",
        "bcrypt",
        "cryptography",
        "cryptography.fernet",
        "cryptography.hazmat.primitives.kdf.pbkdf2",
        "cryptography.hazmat.primitives.hashes",
        "cryptography.hazmat.backends",
        "pyperclip",
        "pyperclip.handlers",
        "sqlite3",
        "tkinter",
        "tkinter.filedialog",
        "tkinter.messagebox",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "pandas", "scipy", "PyQt5", "wx"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="DiloPass",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,              # UPX peut fausser les antivirus, mieux de le désactiver
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # Pas de fenêtre console
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",              # Remplacer par "assets/icon.ico" si tu as une icône
)
