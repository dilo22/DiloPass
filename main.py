"""
DiloPass — Coffre-fort numérique sécurisé
Chiffrement AES-256 via Fernet · PBKDF2-HMAC-SHA256 · bcrypt

Usage:
    pip install -r requirements.txt
    python main.py
"""
import customtkinter as ctk
from ui.app import DiloPassApp


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = DiloPassApp()
    app.mainloop()


if __name__ == "__main__":
    main()
