import ctypes
import os
import threading

import customtkinter as ctk

from core.crypto import CryptoManager
from core.database import ATTACHMENTS_DIR, FILE_VAULT_DIR, DatabaseManager

ACCENT = "#4A9EFF"

QUESTIONS = [
    "Quel était le nom de votre premier animal de compagnie ?",
    "Dans quelle ville êtes-vous né(e) ?",
    "Quel est le prénom de votre meilleur(e) ami(e) d'enfance ?",
    "Quel est le nom de jeune fille de votre mère ?",
    "Quel était le nom de votre école primaire ?",
    "Quelle est la marque de votre première voiture ?",
    "Quel est le prénom de votre premier professeur ?",
    "Quel est votre plat préféré d'enfance ?",
    "Dans quelle rue avez-vous grandi ?",
    "Quel était votre surnom d'enfance ?",
]


def _caps_on() -> bool:
    try:
        return bool(ctypes.WinDLL("User32.dll").GetKeyState(0x14) & 0x0001)
    except Exception:
        return False


class LoginView(ctk.CTkFrame):
    def __init__(self, parent, db: DatabaseManager, crypto: CryptoManager,
                 on_success):
        super().__init__(parent, fg_color="transparent")
        self._db = db
        self._crypto = crypto
        self._on_success = on_success
        self._first_run = db.is_first_run()
        self._failed = 0
        self._caps_job = None
        self._build()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build(self):
        card = ctk.CTkFrame(self, corner_radius=24,
                            fg_color=("#1e293b", "#0f172a"),
                            border_color=ACCENT, border_width=1)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.configure(width=500)

        # Logo cliquable (devient interactif après 3 échecs)
        self._logo = ctk.CTkLabel(card, text="🔐", font=("Segoe UI", 68))
        self._logo.pack(pady=(44, 4))

        ctk.CTkLabel(card, text="DiloPass",
                     font=("Segoe UI", 38, "bold"),
                     text_color=ACCENT).pack()
        ctk.CTkLabel(card, text="Votre coffre-fort numérique sécurisé",
                     font=("Segoe UI", 13), text_color="#94a3b8").pack(pady=(2, 24))

        if self._first_run:
            self._build_setup(card)
        else:
            self._build_login(card)

    # ── Écran de connexion ────────────────────────────────────────────────────

    def _build_login(self, card):
        px = 48

        ctk.CTkLabel(card, text="Mot de passe maître",
                     font=("Segoe UI", 13, "bold"),
                     text_color="#cbd5e1").pack(anchor="w", padx=px, pady=(0, 4))

        # Champ + bouton afficher
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=px)

        self._pw_entry = ctk.CTkEntry(
            row, placeholder_text="Entrez votre mot de passe…",
            show="●", height=54, font=("Segoe UI", 15),
            corner_radius=10, border_color=ACCENT)
        self._pw_entry.pack(side="left", fill="x", expand=True)
        self._pw_entry.bind("<Return>", lambda _: self._do_login())
        self._pw_entry.focus()

        self._show_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            row, text="", variable=self._show_var,
            width=32, checkbox_width=24, checkbox_height=24,
            command=self._toggle_show,
        ).pack(side="left", padx=(10, 0))

        # Caps Lock
        self._caps_lbl = ctk.CTkLabel(card, text="",
                                       font=("Segoe UI", 11),
                                       text_color="#f97316")
        self._caps_lbl.pack(pady=(4, 0))
        self._start_caps_poll()

        # Erreur
        self._err_label = ctk.CTkLabel(card, text="",
                                        text_color="#ef4444",
                                        font=("Segoe UI", 12))
        self._err_label.pack(pady=(2, 0))

        # Bouton déverrouiller
        self._btn = ctk.CTkButton(
            card, text="🔓  Déverrouiller", height=54,
            font=("Segoe UI", 15, "bold"),
            fg_color=ACCENT, hover_color="#2563eb",
            corner_radius=12, command=self._do_login)
        self._btn.pack(fill="x", padx=px, pady=(10, 0))

        # Hint récupération (invisible par défaut)
        self._hint = ctk.CTkLabel(card, text="",
                                   font=("Segoe UI", 11),
                                   text_color="#64748b")
        self._hint.pack(pady=(10, 36))

    # ── Écran de premier lancement ────────────────────────────────────────────

    def _build_setup(self, card):
        px = 44
        body = ctk.CTkScrollableFrame(card, fg_color="transparent",
                                       height=500, width=460)
        body.pack(fill="both", expand=True, padx=4, pady=(0, 8))

        ctk.CTkLabel(body, text="Créez votre mot de passe maître",
                     font=("Segoe UI", 15, "bold"),
                     text_color="#cbd5e1").pack(padx=px, pady=(0, 2))
        ctk.CTkLabel(body,
                     text="Il chiffrera toutes vos données — ne l'oubliez jamais !",
                     font=("Segoe UI", 11), text_color="#94a3b8").pack(padx=px, pady=(0, 14))

        # Mot de passe
        ctk.CTkLabel(body, text="Mot de passe maître *",
                     font=("Segoe UI", 12), text_color="#94a3b8").pack(
                         anchor="w", padx=px, pady=(0, 4))
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", padx=px)
        self._pw_entry = ctk.CTkEntry(
            row, placeholder_text="Nouveau mot de passe…",
            show="●", height=52, font=("Segoe UI", 14),
            corner_radius=10, border_color=ACCENT)
        self._pw_entry.pack(side="left", fill="x", expand=True)
        self._pw_entry.bind("<KeyRelease>", self._update_strength)
        self._show_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row, text="", variable=self._show_var,
                        width=32, checkbox_width=24, checkbox_height=24,
                        command=self._toggle_show).pack(side="left", padx=(10, 0))

        # Caps Lock
        self._caps_lbl = ctk.CTkLabel(body, text="",
                                       font=("Segoe UI", 11),
                                       text_color="#f97316")
        self._caps_lbl.pack(pady=(4, 0))
        self._start_caps_poll()

        # Force
        self._str_lbl = ctk.CTkLabel(body, text="", font=("Segoe UI", 11))
        self._str_lbl.pack(pady=(2, 0))
        self._str_bar = ctk.CTkProgressBar(body, height=6, corner_radius=3)
        self._str_bar.set(0)
        self._str_bar.pack(fill="x", padx=px, pady=(2, 6))

        ctk.CTkLabel(body, text="Confirmer le mot de passe *",
                     font=("Segoe UI", 12), text_color="#94a3b8").pack(
                         anchor="w", padx=px, pady=(4, 4))
        self._pw2_entry = ctk.CTkEntry(
            body, placeholder_text="Confirmer…",
            show="●", height=52, font=("Segoe UI", 14),
            corner_radius=10, border_color=ACCENT)
        self._pw2_entry.pack(fill="x", padx=px)

        # Séparateur
        ctk.CTkFrame(body, height=1, fg_color="#334155").pack(
            fill="x", padx=px, pady=18)

        ctk.CTkLabel(body, text="🛡  Questions de secours",
                     font=("Segoe UI", 13, "bold"),
                     text_color="#cbd5e1").pack(padx=px)
        ctk.CTkLabel(body,
                     text="Si vous oubliez votre mot de passe, ces réponses permettront\n"
                          "de récupérer l'accès à votre coffre.",
                     font=("Segoe UI", 10), text_color="#64748b",
                     justify="center").pack(padx=px, pady=(2, 14))

        # Question 1
        ctk.CTkLabel(body, text="Question 1",
                     font=("Segoe UI", 12), text_color="#94a3b8").pack(
                         anchor="w", padx=px, pady=(0, 4))
        self._q1 = ctk.CTkOptionMenu(body, values=QUESTIONS, height=40,
                                      corner_radius=8, font=("Segoe UI", 11),
                                      dynamic_resizing=False)
        self._q1.set(QUESTIONS[0])
        self._q1.pack(fill="x", padx=px)
        ctk.CTkLabel(body, text="Réponse *",
                     font=("Segoe UI", 12), text_color="#94a3b8").pack(
                         anchor="w", padx=px, pady=(8, 4))
        self._a1 = ctk.CTkEntry(body, placeholder_text="Votre réponse…",
                                  height=44, font=("Segoe UI", 13), corner_radius=8)
        self._a1.pack(fill="x", padx=px)

        # Question 2
        ctk.CTkLabel(body, text="Question 2",
                     font=("Segoe UI", 12), text_color="#94a3b8").pack(
                         anchor="w", padx=px, pady=(12, 4))
        self._q2 = ctk.CTkOptionMenu(body, values=QUESTIONS, height=40,
                                      corner_radius=8, font=("Segoe UI", 11),
                                      dynamic_resizing=False)
        self._q2.set(QUESTIONS[1])
        self._q2.pack(fill="x", padx=px)
        ctk.CTkLabel(body, text="Réponse *",
                     font=("Segoe UI", 12), text_color="#94a3b8").pack(
                         anchor="w", padx=px, pady=(8, 4))
        self._a2 = ctk.CTkEntry(body, placeholder_text="Votre réponse…",
                                  height=44, font=("Segoe UI", 13), corner_radius=8)
        self._a2.pack(fill="x", padx=px)

        # Erreur + bouton
        self._err_label = ctk.CTkLabel(body, text="",
                                        text_color="#ef4444", font=("Segoe UI", 12))
        self._err_label.pack(pady=(10, 0))

        self._btn = ctk.CTkButton(
            body, text="🔐  Créer le coffre-fort", height=54,
            font=("Segoe UI", 15, "bold"),
            fg_color=ACCENT, hover_color="#2563eb",
            corner_radius=12, command=self._do_setup)
        self._btn.pack(fill="x", padx=px, pady=(10, 24))

    # ── Caps Lock ─────────────────────────────────────────────────────────────

    def _start_caps_poll(self):
        self._poll_caps()

    def _poll_caps(self):
        try:
            if _caps_on():
                self._caps_lbl.configure(text="⚠  Majuscules (Caps Lock) activées")
            else:
                self._caps_lbl.configure(text="")
        except Exception:
            pass
        self._caps_job = self.after(500, self._poll_caps)

    def destroy(self):
        if self._caps_job:
            try:
                self.after_cancel(self._caps_job)
            except Exception:
                pass
        super().destroy()

    # ── Afficher / masquer mot de passe ───────────────────────────────────────

    def _toggle_show(self):
        self._pw_entry.configure(show="" if self._show_var.get() else "●")

    # ── Force du mot de passe (setup) ─────────────────────────────────────────

    def _update_strength(self, _=None):
        score, label, color = CryptoManager.strength(self._pw_entry.get())
        self._str_lbl.configure(text=f"Force : {label}", text_color=color)
        self._str_bar.configure(progress_color=color)
        self._str_bar.set(score / 100)

    # ── Connexion ─────────────────────────────────────────────────────────────

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
            return

        self._failed += 1
        self._btn.configure(state="normal", text="🔓  Déverrouiller")
        self._pw_entry.delete(0, "end")

        if self._failed < 3:
            msg = "Mot de passe incorrect ✗"
            if self._failed == 2:
                msg += "  (1 tentative restante)"
            self._err_label.configure(text=msg)
        else:
            self._err_label.configure(
                text=f"Mot de passe incorrect ✗  ({self._failed} tentatives)")
            self._show_recovery_hint()

    def _show_recovery_hint(self):
        if self._db.get_recovery() is None:
            # Aucune question configurée — message explicatif
            self._hint.configure(
                text="Récupération non configurée.\n"
                     "Déverrouillez puis allez dans Paramètres > Questions de secours.",
                text_color="#64748b",
                cursor="arrow",
            )
            return
        # Le logo devient cliquable
        self._logo.configure(cursor="hand2", text_color=ACCENT)
        self._logo.bind("<Button-1>", lambda _: self._open_recovery())
        # Hint discret
        self._hint.configure(
            text="Mot de passe oublié ? Cliquez sur 🔐",
            text_color="#4A9EFF",
            cursor="hand2",
        )
        self._hint.bind("<Button-1>", lambda _: self._open_recovery())

    def _open_recovery(self):
        RecoveryDialog(self, self._db, self._crypto, self._on_success)

    # ── Création du coffre (premier lancement) ────────────────────────────────

    def _do_setup(self):
        pw  = self._pw_entry.get()
        pw2 = self._pw2_entry.get()
        a1  = self._a1.get().strip()
        a2  = self._a2.get().strip()
        q1  = self._q1.get()
        q2  = self._q2.get()

        if len(pw) < 8:
            self._err_label.configure(
                text="Le mot de passe doit contenir au moins 8 caractères.")
            return
        if pw != pw2:
            self._err_label.configure(
                text="Les mots de passe ne correspondent pas.")
            return
        if q1 == q2:
            self._err_label.configure(
                text="Choisissez deux questions différentes.")
            return
        if not a1 or not a2:
            self._err_label.configure(
                text="Veuillez répondre aux deux questions de secours.")
            return

        self._btn.configure(state="disabled", text="Création en cours…")
        threading.Thread(target=self._setup_async,
                         args=(pw, q1, a1, q2, a2), daemon=True).start()

    def _setup_async(self, pw, q1, a1, q2, a2):
        salt = CryptoManager.new_salt()
        hsh  = CryptoManager.hash_master(pw)
        self._db.setup_master(hsh, salt)
        self._crypto.unlock(pw, salt)

        # Sauvegarder les questions de secours (clé chiffrée avec réponses)
        rec_salt = CryptoManager.new_salt()
        rec_key  = CryptoManager.derive_recovery_key(a1, a2, rec_salt)
        enc_key  = CryptoManager.encrypt_with_key(self._crypto.raw_key, rec_key)
        self._db.save_recovery(rec_salt, q1, q2, enc_key)

        self.after(0, self._on_success)


# ── Dialogue de récupération ──────────────────────────────────────────────────

class RecoveryDialog(ctk.CTkToplevel):
    def __init__(self, parent, db: DatabaseManager, crypto: CryptoManager,
                 on_success):
        super().__init__(parent)
        self._db = db
        self._crypto = crypto
        self._on_success = on_success
        self.title("Récupération du coffre-fort")
        self.geometry("560x660")
        self.minsize(520, 580)
        self.grab_set()
        self.resizable(True, True)

        recovery = self._db.get_recovery()
        if recovery is None:
            ctk.CTkLabel(self,
                         text="Aucune question de secours configurée.",
                         font=("Segoe UI", 13)).pack(pady=60)
            return
        self._rec = recovery
        self._build()

    def _build(self):
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=4)
        px = 36

        ctk.CTkLabel(body, text="🛡", font=("Segoe UI", 52)).pack(pady=(28, 4))
        ctk.CTkLabel(body, text="Récupération du coffre-fort",
                     font=("Segoe UI", 19, "bold")).pack()
        ctk.CTkLabel(body,
                     text="Répondez correctement aux deux questions pour\n"
                          "réinitialiser votre mot de passe maître.",
                     font=("Segoe UI", 11), text_color="#94a3b8",
                     justify="center").pack(pady=(4, 20))

        q1 = self._rec["recovery_q1"].decode()
        q2 = self._rec["recovery_q2"].decode()

        # Question 1
        ctk.CTkLabel(body, text=f"Question 1 :\n{q1}",
                     font=("Segoe UI", 12, "bold"), text_color="#cbd5e1",
                     wraplength=460, justify="left").pack(anchor="w", padx=px, pady=(0, 4))
        self._a1 = ctk.CTkEntry(body, placeholder_text="Votre réponse…",
                                  height=46, font=("Segoe UI", 13), corner_radius=8)
        self._a1.pack(fill="x", padx=px)
        self._a1.focus()

        # Question 2
        ctk.CTkLabel(body, text=f"Question 2 :\n{q2}",
                     font=("Segoe UI", 12, "bold"), text_color="#cbd5e1",
                     wraplength=460, justify="left").pack(anchor="w", padx=px, pady=(16, 4))
        self._a2 = ctk.CTkEntry(body, placeholder_text="Votre réponse…",
                                  height=46, font=("Segoe UI", 13), corner_radius=8)
        self._a2.pack(fill="x", padx=px)

        # Séparateur
        ctk.CTkFrame(body, height=1, fg_color="#334155").pack(
            fill="x", padx=px, pady=20)

        ctk.CTkLabel(body, text="Nouveau mot de passe maître *",
                     font=("Segoe UI", 12), text_color="#94a3b8").pack(
                         anchor="w", padx=px, pady=(0, 4))
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", padx=px)
        self._pw = ctk.CTkEntry(row, placeholder_text="Nouveau mot de passe…",
                                 show="●", height=48, font=("Segoe UI", 13),
                                 corner_radius=8, border_color=ACCENT)
        self._pw.pack(side="left", fill="x", expand=True)
        self._pw.bind("<KeyRelease>", self._upd_strength)
        self._sv = ctk.BooleanVar()
        ctk.CTkCheckBox(row, text="", variable=self._sv, width=30,
                        checkbox_width=22, checkbox_height=22,
                        command=lambda: self._pw.configure(
                            show="" if self._sv.get() else "●")
                        ).pack(side="left", padx=(10, 0))

        self._str_lbl = ctk.CTkLabel(body, text="", font=("Segoe UI", 11))
        self._str_lbl.pack(pady=(4, 0))
        self._str_bar = ctk.CTkProgressBar(body, height=4, corner_radius=2)
        self._str_bar.set(0)
        self._str_bar.pack(fill="x", padx=px, pady=(2, 6))

        ctk.CTkLabel(body, text="Confirmer le nouveau mot de passe *",
                     font=("Segoe UI", 12), text_color="#94a3b8").pack(
                         anchor="w", padx=px, pady=(4, 4))
        self._pw2 = ctk.CTkEntry(body, placeholder_text="Confirmer…",
                                   show="●", height=48, font=("Segoe UI", 13),
                                   corner_radius=8, border_color=ACCENT)
        self._pw2.pack(fill="x", padx=px)

        self._err = ctk.CTkLabel(body, text="", text_color="#ef4444",
                                   font=("Segoe UI", 12))
        self._err.pack(pady=(10, 0))

        self._btn = ctk.CTkButton(
            body, text="Récupérer l'accès", height=50,
            font=("Segoe UI", 14, "bold"),
            fg_color=ACCENT, hover_color="#2563eb",
            corner_radius=12, command=self._do_recovery)
        self._btn.pack(fill="x", padx=px, pady=(10, 28))

    def _upd_strength(self, _=None):
        score, label, color = CryptoManager.strength(self._pw.get())
        self._str_lbl.configure(text=f"Force : {label}", text_color=color)
        self._str_bar.configure(progress_color=color)
        self._str_bar.set(score / 100)

    def _do_recovery(self):
        a1     = self._a1.get().strip()
        a2     = self._a2.get().strip()
        new_pw = self._pw.get()
        new_pw2= self._pw2.get()

        if not a1 or not a2:
            self._err.configure(text="Veuillez répondre aux deux questions.")
            return
        if len(new_pw) < 8:
            self._err.configure(
                text="Le mot de passe doit contenir au moins 8 caractères.")
            return
        if new_pw != new_pw2:
            self._err.configure(text="Les mots de passe ne correspondent pas.")
            return

        self._btn.configure(state="disabled", text="Vérification…")
        threading.Thread(target=self._recover_async,
                         args=(a1, a2, new_pw), daemon=True).start()

    def _recover_async(self, a1: str, a2: str, new_pw: str):
        try:
            rec_salt    = self._rec["recovery_salt"]
            enc_key     = self._rec["recovery_encrypted_key"]
            rec_key     = CryptoManager.derive_recovery_key(a1, a2, rec_salt)

            try:
                raw_key = CryptoManager.decrypt_with_key(enc_key, rec_key)
            except Exception:
                self.after(0, lambda: (
                    self._err.configure(
                        text="Réponses incorrectes. Vérifiez l'orthographe."),
                    self._btn.configure(state="normal",
                                        text="Récupérer l'accès"),
                ))
                return

            # Déverrouiller avec l'ancienne clé pour pouvoir déchiffrer
            self._crypto.unlock_with_raw_key(raw_key)

            # Re-chiffrer toutes les données avec le nouveau mot de passe
            self._reencrypt_all(new_pw, a1, a2)

            self.after(0, lambda: (self.destroy(), self._on_success()))

        except Exception as exc:
            self.after(0, lambda: (
                self._err.configure(text=f"Erreur inattendue : {exc}"),
                self._btn.configure(state="normal", text="Récupérer l'accès"),
            ))

    def _reencrypt_all(self, new_pw: str, a1: str, a2: str):
        """Re-chiffre intégralement le coffre avec le nouveau mot de passe."""
        new_salt   = CryptoManager.new_salt()
        new_crypto = CryptoManager()
        new_crypto.unlock(new_pw, new_salt)

        old = self._crypto
        db  = self._db

        db.begin()
        try:
            # ── Entrées du coffre mot de passe ────────────────────────────
            for row in db.get_all_vault():
                try:
                    db.replace_vault_encrypted_fields(
                        row["id"],
                        new_crypto.encrypt(old.dec(row["title"])),
                        new_crypto.enc(old.dec(row["username"])) if row["username"] else None,
                        new_crypto.encrypt(old.dec(row["password"])),
                        new_crypto.enc(old.dec(row["url"]))      if row["url"]      else None,
                        new_crypto.enc(old.dec(row["notes"]))    if row["notes"]    else None,
                    )
                except Exception:
                    pass

            # ── Notes ─────────────────────────────────────────────────────
            for row in db.get_all_notes():
                try:
                    db.replace_note_encrypted_fields(
                        row["id"],
                        new_crypto.encrypt(old.dec(row["title"])),
                        new_crypto.encrypt(old.dec(row["content"])),
                        new_crypto.enc(old.dec(row["tags"])) if row["tags"] else None,
                    )
                except Exception:
                    pass

            # ── Noms des pièces jointes (vault) ───────────────────────────
            for att in db.get_all_attachments():
                try:
                    db.replace_attachment_name(
                        att["id"],
                        new_crypto.encrypt(old.dec(att["original_name"])))
                except Exception:
                    pass

            # ── Noms des dossiers du coffre fichiers ──────────────────────
            for folder in db.get_all_file_vault_folders_flat():
                try:
                    db.rename_file_vault_folder(
                        folder["id"],
                        new_crypto.encrypt(old.dec(folder["name"])))
                except Exception:
                    pass

            # ── Titres et noms des fichiers du coffre fichiers ────────────
            for fvf in db.get_all_file_vault_files_flat():
                try:
                    db.update_file_vault_file_fields(
                        fvf["id"],
                        new_crypto.encrypt(old.dec(fvf["title"])),
                        new_crypto.encrypt(old.dec(fvf["original_name"])),
                    )
                except Exception:
                    pass

            # ── Contenu binaire des pièces jointes (disque) ───────────────
            _reencrypt_dir(old, new_crypto, ATTACHMENTS_DIR)

            # ── Contenu binaire du coffre fichiers (disque) ───────────────
            _reencrypt_dir(old, new_crypto, FILE_VAULT_DIR)

            # ── Nouveau hash maître ───────────────────────────────────────
            db.setup_master(CryptoManager.hash_master(new_pw), new_salt)

            # ── Mettre à jour la clé de récupération ──────────────────────
            rec_salt = CryptoManager.new_salt()
            rec_key  = CryptoManager.derive_recovery_key(a1, a2, rec_salt)
            enc_key  = CryptoManager.encrypt_with_key(new_crypto.raw_key, rec_key)
            q1 = self._rec["recovery_q1"].decode()
            q2 = self._rec["recovery_q2"].decode()
            db.save_recovery(rec_salt, q1, q2, enc_key)

            db.commit()

            # Basculer vers la nouvelle clé
            self._crypto.unlock_with_raw_key(new_crypto.raw_key)

        except Exception:
            db.rollback()
            raise


def _reencrypt_dir(old: CryptoManager, new: CryptoManager, directory: str):
    """Re-chiffre tous les fichiers .bin d'un dossier sur disque."""
    if not os.path.isdir(directory):
        return
    for fname in os.listdir(directory):
        if not fname.endswith(".bin"):
            continue
        path = os.path.join(directory, fname)
        try:
            with open(path, "rb") as fh:
                plain = old.decrypt_bytes(fh.read())
            with open(path, "wb") as fh:
                fh.write(new.encrypt_bytes(plain))
        except Exception:
            pass
