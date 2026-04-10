import customtkinter as ctk
import threading
from core.crypto import CryptoManager
from core.database import DatabaseManager


class LoginView(ctk.CTkFrame):
    """Full-screen login / first-run setup frame."""

    ACCENT = "#4A9EFF"

    def __init__(self, parent, db: DatabaseManager, crypto: CryptoManager,
                 on_success):
        super().__init__(parent, fg_color="transparent")
        self._db = db
        self._crypto = crypto
        self._on_success = on_success
        self._first_run = db.is_first_run()
        self._build()

    def _build(self):
        # ── centered card ──────────────────────────────────────────────────
        card = ctk.CTkFrame(self, corner_radius=20,
                            fg_color=("#1e293b", "#0f172a"),
                            border_color=self.ACCENT, border_width=1)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.configure(width=420)

        pad = {"padx": 40, "pady": 8}

        # Logo + title
        ctk.CTkLabel(card, text="🔐", font=("Segoe UI", 56)).pack(pady=(40, 4))
        ctk.CTkLabel(card, text="DiloPass",
                     font=("Segoe UI", 32, "bold"),
                     text_color=self.ACCENT).pack()
        ctk.CTkLabel(card,
                     text="Votre coffre-fort numérique sécurisé",
                     font=("Segoe UI", 13),
                     text_color="#94a3b8").pack(pady=(2, 20))

        if self._first_run:
            self._build_setup(card, pad)
        else:
            self._build_login(card, pad)

    def _build_login(self, card, pad):
        ctk.CTkLabel(card, text="Mot de passe maître",
                     font=("Segoe UI", 13, "bold"),
                     text_color="#cbd5e1").pack(anchor="w", **pad)

        self._pw_entry = ctk.CTkEntry(
            card, placeholder_text="Entrez votre mot de passe…",
            show="●", height=44, font=("Segoe UI", 14),
            corner_radius=10, border_color=self.ACCENT)
        self._pw_entry.pack(fill="x", **pad)
        self._pw_entry.bind("<Return>", lambda e: self._do_login())

        self._err_label = ctk.CTkLabel(card, text="", text_color="#ef4444",
                                       font=("Segoe UI", 12))
        self._err_label.pack(**pad)

        self._btn = ctk.CTkButton(
            card, text="  Déverrouiller", height=48,
            font=("Segoe UI", 15, "bold"),
            fg_color=self.ACCENT, hover_color="#2563eb",
            corner_radius=12, command=self._do_login)
        self._btn.pack(fill="x", padx=40, pady=(4, 40))

    def _build_setup(self, card, pad):
        ctk.CTkLabel(card, text="Créer votre mot de passe maître",
                     font=("Segoe UI", 14, "bold"),
                     text_color="#cbd5e1").pack(**pad)
        ctk.CTkLabel(card,
                     text="Il chiffrera toutes vos données — ne l'oubliez pas !",
                     font=("Segoe UI", 11), text_color="#94a3b8").pack(**pad)

        self._pw_entry = ctk.CTkEntry(
            card, placeholder_text="Nouveau mot de passe…",
            show="●", height=44, font=("Segoe UI", 14),
            corner_radius=10, border_color=self.ACCENT)
        self._pw_entry.pack(fill="x", **pad)
        self._pw_entry.bind("<KeyRelease>", self._update_strength)

        # Strength bar
        self._strength_label = ctk.CTkLabel(card, text="",
                                             font=("Segoe UI", 11))
        self._strength_label.pack(**pad)
        self._strength_bar = ctk.CTkProgressBar(card, height=6,
                                                 corner_radius=3)
        self._strength_bar.set(0)
        self._strength_bar.pack(fill="x", padx=40, pady=2)

        self._pw2_entry = ctk.CTkEntry(
            card, placeholder_text="Confirmer le mot de passe…",
            show="●", height=44, font=("Segoe UI", 14),
            corner_radius=10, border_color=self.ACCENT)
        self._pw2_entry.pack(fill="x", **pad)

        self._err_label = ctk.CTkLabel(card, text="", text_color="#ef4444",
                                       font=("Segoe UI", 12))
        self._err_label.pack(**pad)

        self._btn = ctk.CTkButton(
            card, text="  Créer le coffre-fort", height=48,
            font=("Segoe UI", 15, "bold"),
            fg_color=self.ACCENT, hover_color="#2563eb",
            corner_radius=12, command=self._do_setup)
        self._btn.pack(fill="x", padx=40, pady=(4, 40))

    def _update_strength(self, _event=None):
        pw = self._pw_entry.get()
        score, label, color = CryptoManager.strength(pw)
        self._strength_label.configure(text=f"Force : {label}", text_color=color)
        self._strength_bar.configure(progress_color=color)
        self._strength_bar.set(score / 100)

    def _do_login(self):
        pw = self._pw_entry.get().strip()
        if not pw:
            self._err_label.configure(text="Veuillez entrer votre mot de passe.")
            return
        self._btn.configure(state="disabled", text="Déverrouillage…")
        self._err_label.configure(text="")
        threading.Thread(target=self._verify_async, args=(pw,),
                         daemon=True).start()

    def _verify_async(self, pw: str):
        hsh  = self._db.get_master_hash()
        salt = self._db.get_salt()
        ok   = CryptoManager.verify_master(pw, hsh)
        self.after(0, lambda: self._login_result(ok, pw, salt))

    def _login_result(self, ok: bool, pw: str, salt: bytes):
        if ok:
            self._crypto.unlock(pw, salt)
            self._on_success()
        else:
            self._btn.configure(state="normal", text="  Déverrouiller")
            self._err_label.configure(text="Mot de passe incorrect ✗")
            self._pw_entry.delete(0, "end")

    def _do_setup(self):
        pw  = self._pw_entry.get()
        pw2 = self._pw2_entry.get()
        if len(pw) < 8:
            self._err_label.configure(
                text="Le mot de passe doit contenir au moins 8 caractères.")
            return
        if pw != pw2:
            self._err_label.configure(text="Les mots de passe ne correspondent pas.")
            return
        self._btn.configure(state="disabled", text="Création…")
        threading.Thread(target=self._setup_async, args=(pw,),
                         daemon=True).start()

    def _setup_async(self, pw: str):
        salt = CryptoManager.new_salt()
        hsh  = CryptoManager.hash_master(pw)
        self._db.setup_master(hsh, salt)
        self._crypto.unlock(pw, salt)
        self.after(0, self._on_success)
