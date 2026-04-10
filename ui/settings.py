import os
import threading

import customtkinter as ctk

from core.crypto import CryptoManager
from core.database import ATTACHMENTS_DIR, DB_PATH, DatabaseManager


class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, db: DatabaseManager, crypto: CryptoManager,
                 show_toast, on_theme_change):
        super().__init__(parent, fg_color="transparent")
        self._db = db
        self._crypto = crypto
        self._toast = show_toast
        self._on_theme = on_theme_change
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Parametres",
                     font=("Segoe UI", 22, "bold")).pack(
                         anchor="w", padx=20, pady=(16, 16))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                        corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=20)

        self._section(scroll, "Apparence")

        mode_row = self._row(scroll, "Theme")
        self._theme_seg = ctk.CTkSegmentedButton(
            mode_row,
            values=["Sombre", "Clair", "Systeme"],
            command=self._change_theme)
        cur = self._db.get_setting("theme", "Sombre")
        if cur == "Systeme":
            cur = "Systeme"
        self._theme_seg.set(cur)
        self._theme_seg.pack(side="right")

        self._section(scroll, "Securite")

        lock_row = self._row(scroll, "Verrouillage auto (minutes)")
        self._lock_var = ctk.StringVar(
            value=self._db.get_setting("auto_lock_min", "5"))
        ctk.CTkOptionMenu(
            lock_row,
            values=["1", "2", "5", "10", "15", "30", "Jamais"],
            variable=self._lock_var,
            command=lambda v: self._db.set_setting("auto_lock_min", v),
        ).pack(side="right")

        clip_row = self._row(scroll, "Effacer presse-papiers apres (s)")
        self._clip_var = ctk.StringVar(
            value=self._db.get_setting("clipboard_clear_s", "30"))
        ctk.CTkOptionMenu(
            clip_row,
            values=["10", "20", "30", "60", "120", "Jamais"],
            variable=self._clip_var,
            command=lambda v: self._db.set_setting("clipboard_clear_s", v),
        ).pack(side="right")

        self._section(scroll, "Mot de passe maitre")
        ctk.CTkButton(
            scroll,
            text="Changer le mot de passe maitre",
            height=40,
            corner_radius=10,
            fg_color=("#e2e8f0", "#334155"),
            hover_color=("#cbd5e1", "#475569"),
            text_color=("#374151", "#e2e8f0"),
            font=("Segoe UI", 13),
            command=self._change_master,
        ).pack(anchor="w", pady=(4, 8))

        self._section(scroll, "Donnees")

        ctk.CTkButton(
            scroll,
            text="Tout effacer (reinitialisation)",
            height=40,
            corner_radius=10,
            fg_color=("#fee2e2", "#3b1515"),
            hover_color=("#fecaca", "#5a1f1f"),
            text_color="#ef4444",
            font=("Segoe UI", 13),
            command=self._confirm_wipe,
        ).pack(anchor="w", pady=4)

        self._section(scroll, "A propos")
        about = ctk.CTkFrame(scroll, corner_radius=12,
                             fg_color=("#f1f5f9", "#1e293b"))
        about.pack(fill="x", pady=4)
        ctk.CTkLabel(about, text="DiloPass v1.0",
                     font=("Segoe UI", 14, "bold")).pack(
                         anchor="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(
            about,
            text="Coffre-fort numerique chiffre AES-256\n"
                 "Chiffrement Fernet · PBKDF2-HMAC-SHA256 · bcrypt",
            font=("Segoe UI", 11),
            text_color="#94a3b8",
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 12))

    def _section(self, parent, title):
        ctk.CTkLabel(parent, text=title,
                     font=("Segoe UI", 14, "bold")).pack(
                         anchor="w", pady=(16, 4))
        ctk.CTkFrame(parent, height=1,
                     fg_color=("#cbd5e1", "#334155")).pack(fill="x", pady=2)

    def _row(self, parent, label):
        row = ctk.CTkFrame(parent, fg_color=("#f8fafc", "#1e293b"),
                           corner_radius=10)
        row.pack(fill="x", pady=3)
        ctk.CTkLabel(row, text=label, font=("Segoe UI", 12)).pack(
            side="left", padx=14, pady=10)
        return row

    def _change_theme(self, mode):
        stored_mode = "Systeme" if mode == "Systeme" else mode
        self._db.set_setting("theme", stored_mode)
        mapping = {"Sombre": "dark", "Clair": "light", "Systeme": "system"}
        ctk.set_appearance_mode(mapping.get(mode, "dark"))
        self._on_theme(mode)

    def _change_master(self):
        ChangeMasterDialog(self, self._db, self._crypto, self._toast)

    def _confirm_wipe(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Attention")
        dlg.geometry("380x180")
        dlg.grab_set()
        ctk.CTkLabel(dlg, text="Effacer TOUTES les donnees ?",
                     font=("Segoe UI", 14, "bold"),
                     text_color="#ef4444").pack(pady=(20, 4))
        ctk.CTkLabel(dlg, text="Cette action est irreversible.",
                     font=("Segoe UI", 12), text_color="#94a3b8").pack()
        brow = ctk.CTkFrame(dlg, fg_color="transparent")
        brow.pack(pady=16)
        ctk.CTkButton(brow, text="Annuler", width=120,
                      fg_color=("#e2e8f0", "#334155"),
                      command=dlg.destroy).pack(side="left", padx=8)
        ctk.CTkButton(brow, text="Tout effacer", width=120,
                      fg_color="#ef4444", hover_color="#dc2626",
                      command=lambda: self._wipe(dlg)).pack(side="left")

    def _wipe(self, dlg):
        dlg.destroy()
        self._crypto.lock()
        self._db.close()
        try:
            os.remove(DB_PATH)
        except Exception:
            pass
        try:
            for name in os.listdir(ATTACHMENTS_DIR):
                path = os.path.join(ATTACHMENTS_DIR, name)
                if os.path.isfile(path):
                    os.remove(path)
        except Exception:
            pass
        self.winfo_toplevel().destroy()


class ChangeMasterDialog(ctk.CTkToplevel):
    def __init__(self, parent, db, crypto, toast):
        super().__init__(parent)
        self._db = db
        self._crypto = crypto
        self._toast = toast
        self.title("Changer le mot de passe maitre")
        self.geometry("420x380")
        self.grab_set()
        self._build()

    def _field(self, label):
        ctk.CTkLabel(self, text=label, font=("Segoe UI", 12),
                     text_color="#94a3b8").pack(anchor="w", padx=24, pady=(8, 2))
        e = ctk.CTkEntry(self, show="*", height=38, corner_radius=8,
                         font=("Segoe UI", 13))
        e.pack(fill="x", padx=24)
        return e

    def _build(self):
        ctk.CTkLabel(self, text="Changer le mot de passe maitre",
                     font=("Segoe UI", 15, "bold")).pack(pady=(20, 8))
        self._old = self._field("Mot de passe actuel")
        self._new1 = self._field("Nouveau mot de passe")
        self._new2 = self._field("Confirmer le nouveau")

        self._str_lbl = ctk.CTkLabel(self, text="", font=("Segoe UI", 11))
        self._str_lbl.pack(padx=24, anchor="w")
        self._str_bar = ctk.CTkProgressBar(self, height=4, corner_radius=2)
        self._str_bar.set(0)
        self._str_bar.pack(fill="x", padx=24)
        self._new1.bind("<KeyRelease>", self._upd)

        self._err = ctk.CTkLabel(self, text="", text_color="#ef4444",
                                 font=("Segoe UI", 11))
        self._err.pack(pady=4)

        ctk.CTkButton(self, text="Enregistrer", height=44,
                      font=("Segoe UI", 14, "bold"),
                      fg_color="#4A9EFF", hover_color="#2563eb",
                      corner_radius=10,
                      command=self._save).pack(fill="x", padx=24, pady=12)

    def _upd(self, _=None):
        sc, lb, col = CryptoManager.strength(self._new1.get())
        self._str_lbl.configure(text=f"Force : {lb}", text_color=col)
        self._str_bar.configure(progress_color=col)
        self._str_bar.set(sc / 100)

    def _save(self):
        old = self._old.get()
        new = self._new1.get()
        new2 = self._new2.get()
        hsh = self._db.get_master_hash()

        if not CryptoManager.verify_master(old, hsh):
            self._err.configure(text="Mot de passe actuel incorrect.")
            return
        if len(new) < 8:
            self._err.configure(text="Au moins 8 caracteres requis.")
            return
        if new != new2:
            self._err.configure(text="Les mots de passe ne correspondent pas.")
            return

        def work():
            try:
                old_salt = self._db.get_salt()
                old_crypto = CryptoManager()
                old_crypto.unlock(old, old_salt)

                new_salt = CryptoManager.new_salt()
                new_hsh = CryptoManager.hash_master(new)
                new_crypto = CryptoManager()
                new_crypto.unlock(new, new_salt)

                self._db.begin()

                for row in self._db.get_all_vault():
                    self._db.replace_vault_encrypted_fields(
                        row["id"],
                        new_crypto.encrypt(old_crypto.dec(row["title"])),
                        new_crypto.enc(old_crypto.dec(row["username"])),
                        new_crypto.encrypt(old_crypto.dec(row["password"])),
                        new_crypto.enc(old_crypto.dec(row["url"])),
                        new_crypto.enc(old_crypto.dec(row["notes"])),
                    )

                for row in self._db.get_all_notes():
                    self._db.replace_note_encrypted_fields(
                        row["id"],
                        new_crypto.encrypt(old_crypto.dec(row["title"])),
                        new_crypto.encrypt(old_crypto.dec(row["content"])),
                        new_crypto.enc(old_crypto.dec(row["tags"])),
                    )

                for row in self._db.get_all_attachments():
                    path = os.path.join(ATTACHMENTS_DIR, row["stored_name"])
                    with open(path, "rb") as fh:
                        encrypted_bytes = fh.read()
                    plain_bytes = old_crypto.decrypt_bytes(encrypted_bytes)
                    with open(path, "wb") as fh:
                        fh.write(new_crypto.encrypt_bytes(plain_bytes))
                    self._db.replace_attachment_name(
                        row["id"],
                        new_crypto.encrypt(old_crypto.dec(row["original_name"])),
                    )

                self._db.setup_master(new_hsh, new_salt)
                self._db.commit()
                self._crypto.unlock(new, new_salt)
                self.after(0, lambda: [self._toast("Mot de passe maitre modifie."),
                                       self.destroy()])
            except Exception as exc:
                try:
                    self._db.rollback()
                except Exception:
                    pass
                self.after(0, lambda: self._err.configure(
                    text=f"Migration impossible : {exc}"))

        threading.Thread(target=work, daemon=True).start()
