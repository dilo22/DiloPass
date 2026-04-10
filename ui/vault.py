import os
import secrets
import tempfile
from tkinter import filedialog

import customtkinter as ctk
import pyperclip

from core.crypto import CryptoManager
from core.database import ATTACHMENTS_DIR, DatabaseManager, VaultAttachment, VaultEntry


CATEGORIES = ["Tous", "General", "Social", "Travail", "Finance",
              "Gaming", "Email", "Shopping", "Autre"]

CAT_COLORS = {
    "General": "#6b7280",
    "Social": "#4A9EFF",
    "Travail": "#22c55e",
    "Finance": "#eab308",
    "Gaming": "#a855f7",
    "Email": "#f97316",
    "Shopping": "#ec4899",
    "Autre": "#94a3b8",
}

MAX_ATTACHMENT_SIZE = 25 * 1024 * 1024


def format_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


class VaultView(ctk.CTkFrame):
    def __init__(self, parent, db: DatabaseManager, crypto: CryptoManager,
                 show_toast):
        super().__init__(parent, fg_color="transparent")
        self._db = db
        self._crypto = crypto
        self._toast = show_toast
        self._filter_cat = "Tous"
        self._search_query = ""
        self._build()
        self.refresh()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(16, 8))

        ctk.CTkLabel(top, text="Coffre-Fort",
                     font=("Segoe UI", 22, "bold")).pack(side="left")

        ctk.CTkButton(
            top,
            text="+ Ajouter",
            width=120,
            height=36,
            font=("Segoe UI", 13, "bold"),
            fg_color="#4A9EFF",
            hover_color="#2563eb",
            corner_radius=10,
            command=self._open_add_dialog,
        ).pack(side="right", padx=(8, 0))

        self._search = ctk.CTkEntry(
            top,
            placeholder_text="Recherche...",
            width=240,
            height=36,
            corner_radius=10,
        )
        self._search.pack(side="right")
        self._search.bind("<KeyRelease>", self._on_search)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=8)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(body, width=150, corner_radius=12,
                               fg_color=("#f1f5f9", "#1e293b"))
        sidebar.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        sidebar.pack_propagate(False)

        ctk.CTkLabel(sidebar, text="Categories",
                     font=("Segoe UI", 11, "bold"),
                     text_color="#94a3b8").pack(pady=(12, 4), padx=10)

        self._cat_btns: dict[str, ctk.CTkButton] = {}
        for cat in CATEGORIES:
            btn = ctk.CTkButton(
                sidebar,
                text=cat,
                anchor="w",
                height=32,
                font=("Segoe UI", 12),
                fg_color=("#4A9EFF", "#4A9EFF") if cat == "Tous" else "transparent",
                hover_color=("#dbeafe", "#1e3a5f"),
                text_color=("white", "white") if cat == "Tous"
                else ("#374151", "#cbd5e1"),
                corner_radius=8,
                command=lambda c=cat: self._filter(c),
            )
            btn.pack(fill="x", padx=8, pady=2)
            self._cat_btns[cat] = btn

        self._scroll = ctk.CTkScrollableFrame(body, corner_radius=12,
                                              fg_color="transparent")
        self._scroll.grid(row=0, column=1, sticky="nsew")

    def _filter(self, cat: str):
        self._filter_cat = cat
        for key, btn in self._cat_btns.items():
            if key == cat:
                btn.configure(fg_color="#4A9EFF", text_color="white")
            else:
                btn.configure(fg_color="transparent",
                              text_color=("#374151", "#cbd5e1"))
        self.refresh()

    def _on_search(self, _=None):
        self._search_query = self._search.get().lower().strip()
        self.refresh()

    def refresh(self):
        for widget in self._scroll.winfo_children():
            widget.destroy()

        entries = []
        for row in self._db.get_all_vault():
            try:
                title = self._crypto.dec(row["title"])
                username = self._crypto.dec(row["username"])
                category = row["category"]
                attachments = self._db.get_attachments_for_entry(row["id"])
                if self._filter_cat != "Tous" and category != self._filter_cat:
                    continue
                if self._search_query:
                    haystacks = [title.lower(), username.lower()]
                    if all(self._search_query not in value for value in haystacks):
                        continue
                entries.append((row, title, username, category, len(attachments)))
            except Exception:
                continue

        if not entries:
            ctk.CTkLabel(
                self._scroll,
                text="Aucune entree trouvee.\nCliquez sur '+ Ajouter' pour commencer.",
                font=("Segoe UI", 14),
                text_color="#94a3b8",
                justify="center",
            ).pack(expand=True, pady=60)
            return

        frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        frame.pack(fill="both", expand=True)
        for col in range(3):
            frame.columnconfigure(col, weight=1)

        for idx, (row, title, username, category, attachment_count) in enumerate(entries):
            self._make_card(frame, row, title, username, category, attachment_count,
                            row_n=idx // 3, col=idx % 3)

    def _make_card(self, parent, row, title, username, category,
                   attachment_count, row_n, col):
        color = CAT_COLORS.get(category, "#6b7280")
        card = ctk.CTkFrame(parent, corner_radius=14,
                            fg_color=("#f8fafc", "#1e293b"),
                            border_color=color, border_width=1)
        card.grid(row=row_n, column=col, padx=6, pady=6, sticky="ew")

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(12, 4))

        badge = ctk.CTkFrame(top, corner_radius=6, fg_color=color, width=1)
        badge.pack(side="left")
        ctk.CTkLabel(badge, text=category, font=("Segoe UI", 9, "bold"),
                     text_color="white").pack(padx=6, pady=2)

        ctk.CTkLabel(top, text="*" if row["is_favorite"] else "",
                     text_color="#eab308", font=("Segoe UI", 14)).pack(side="right")

        initials = title[:1].upper() if title else "?"
        avatar = ctk.CTkFrame(card, width=44, height=44, corner_radius=22,
                              fg_color=color)
        avatar.pack(pady=(4, 2))
        avatar.pack_propagate(False)
        ctk.CTkLabel(avatar, text=initials,
                     font=("Segoe UI", 18, "bold"),
                     text_color="white").place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(card, text=title, font=("Segoe UI", 13, "bold"),
                     wraplength=160).pack(padx=12)
        ctk.CTkLabel(card, text=username or "-", font=("Segoe UI", 11),
                     text_color="#94a3b8", wraplength=160).pack(
                         padx=12, pady=(0, 4))
        ctk.CTkLabel(card, text=f"Fichiers : {attachment_count}",
                     font=("Segoe UI", 10), text_color="#64748b").pack(
                         padx=12, pady=(0, 8))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=10, pady=(0, 12))

        ctk.CTkButton(
            actions, text="User", width=50, height=28,
            fg_color=("#e2e8f0", "#334155"),
            hover_color=("#cbd5e1", "#475569"),
            text_color=("#374151", "#e2e8f0"),
            corner_radius=8, font=("Segoe UI", 11),
            command=lambda r=row: self._copy_user(r),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            actions, text="MDP", width=50, height=28,
            fg_color=("#e2e8f0", "#334155"),
            hover_color=("#cbd5e1", "#475569"),
            text_color=("#374151", "#e2e8f0"),
            corner_radius=8, font=("Segoe UI", 11),
            command=lambda r=row: self._copy_pass(r),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            actions, text="Fich.", width=50, height=28,
            fg_color=("#dbeafe", "#16355f"),
            hover_color=("#bfdbfe", "#1d4b85"),
            text_color=("#1d4b85", "white"),
            corner_radius=8, font=("Segoe UI", 11),
            command=lambda r=row: self._open_attachments(r),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            actions, text="Editer", width=56, height=28,
            fg_color=("#e2e8f0", "#334155"),
            hover_color=("#cbd5e1", "#475569"),
            corner_radius=8, font=("Segoe UI", 11),
            command=lambda r=row: self._open_edit_dialog(r),
        ).pack(side="right", padx=2)

        ctk.CTkButton(
            actions, text="Suppr", width=56, height=28,
            fg_color=("#fee2e2", "#3b1515"),
            hover_color=("#fecaca", "#5a1f1f"),
            text_color="#ef4444",
            corner_radius=8, font=("Segoe UI", 11),
            command=lambda r=row: self._delete(r),
        ).pack(side="right", padx=2)

    def _attachment_path(self, stored_name: str) -> str:
        return os.path.join(ATTACHMENTS_DIR, stored_name)

    def _delete_attachment_file(self, attachment_row):
        path = self._attachment_path(attachment_row["stored_name"])
        if os.path.exists(path):
            os.remove(path)

    def _copy_user(self, row):
        try:
            pyperclip.copy(self._crypto.dec(row["username"]))
            self._db.touch_vault(row["id"])
            self._toast("Identifiant copie.")
        except Exception as exc:
            self._toast(f"Erreur : {exc}", error=True)

    def _copy_pass(self, row):
        try:
            pyperclip.copy(self._crypto.dec(row["password"]))
            self._db.touch_vault(row["id"])
            self._toast("Mot de passe copie.")
            self.after(30_000, lambda: pyperclip.copy(""))
        except Exception as exc:
            self._toast(f"Erreur : {exc}", error=True)

    def _delete(self, row):
        title = self._crypto.dec(row["title"])
        dlg = ctk.CTkToplevel(self)
        dlg.title("Confirmer la suppression")
        dlg.geometry("360x160")
        dlg.grab_set()
        ctk.CTkLabel(dlg, text=f"Supprimer '{title}' ?",
                     font=("Segoe UI", 13)).pack(pady=24)
        buttons = ctk.CTkFrame(dlg, fg_color="transparent")
        buttons.pack()
        ctk.CTkButton(
            buttons, text="Annuler", width=120,
            fg_color=("#e2e8f0", "#334155"),
            command=dlg.destroy,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            buttons, text="Supprimer", width=120,
            fg_color="#ef4444", hover_color="#dc2626",
            command=lambda: self._confirm_delete_entry(row, dlg),
        ).pack(side="left", padx=8)

    def _confirm_delete_entry(self, row, dlg):
        try:
            for attachment in self._db.get_attachments_for_entry(row["id"]):
                self._delete_attachment_file(attachment)
            self._db.delete_vault(row["id"])
            dlg.destroy()
            self.refresh()
            self._toast("Entree supprimee.")
        except Exception as exc:
            self._toast(f"Suppression impossible : {exc}", error=True)

    def _open_add_dialog(self):
        EntryDialog(self, self._db, self._crypto, None, self.refresh, self._toast)

    def _open_edit_dialog(self, row):
        EntryDialog(self, self._db, self._crypto, row, self.refresh, self._toast)

    def _open_attachments(self, row):
        AttachmentsDialog(self, self._db, self._crypto, row, self.refresh, self._toast)


class EntryDialog(ctk.CTkToplevel):
    def __init__(self, parent, db, crypto, row, on_save, toast):
        super().__init__(parent)
        self._db = db
        self._crypto = crypto
        self._row = row
        self._on_save = on_save
        self._toast = toast
        self.title("Modifier" if row else "Nouvelle entree")
        self.geometry("520x760")
        self.minsize(480, 660)
        self.resizable(True, True)
        self.grab_set()
        self._build()
        if row:
            self._populate()

    def _field(self, parent, label, show=None):
        ctk.CTkLabel(parent, text=label, font=("Segoe UI", 12),
                     text_color="#94a3b8").pack(anchor="w", padx=24, pady=(8, 2))
        entry = ctk.CTkEntry(parent, height=38, corner_radius=8,
                             show=show, font=("Segoe UI", 13))
        entry.pack(fill="x", padx=24)
        return entry

    def _build(self):
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)

        ctk.CTkLabel(body, text="Modifier l'entree" if self._row else "Nouvelle entree",
                     font=("Segoe UI", 16, "bold")).pack(pady=(20, 8))

        self._title = self._field(body, "Titre *")
        self._user = self._field(body, "Identifiant / Email")
        self._pw = self._field(body, "Mot de passe *", show="*")

        self._str_lbl = ctk.CTkLabel(body, text="", font=("Segoe UI", 11))
        self._str_lbl.pack(anchor="w", padx=24)
        self._str_bar = ctk.CTkProgressBar(body, height=4, corner_radius=2)
        self._str_bar.set(0)
        self._str_bar.pack(fill="x", padx=24, pady=2)
        self._pw.bind("<KeyRelease>", self._upd_strength)

        pw_row = ctk.CTkFrame(body, fg_color="transparent")
        pw_row.pack(fill="x", padx=24, pady=2)
        self._show_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            pw_row, text="Afficher le mot de passe",
            variable=self._show_var,
            command=self._toggle_show,
            font=("Segoe UI", 11),
        ).pack(side="left")
        ctk.CTkButton(
            pw_row, text="Generer", width=110, height=28,
            font=("Segoe UI", 11),
            fg_color=("#e2e8f0", "#334155"),
            hover_color=("#cbd5e1", "#475569"),
            text_color=("#374151", "#e2e8f0"),
            corner_radius=8,
            command=self._gen_pw,
        ).pack(side="right")

        self._url = self._field(body, "URL")

        ctk.CTkLabel(body, text="Categorie", font=("Segoe UI", 12),
                     text_color="#94a3b8").pack(anchor="w", padx=24, pady=(8, 2))
        self._cat = ctk.CTkOptionMenu(body, values=CATEGORIES[1:],
                                      height=38, corner_radius=8,
                                      font=("Segoe UI", 13))
        self._cat.pack(fill="x", padx=24)

        self._fav = ctk.CTkCheckBox(body, text="Favori",
                                    font=("Segoe UI", 12))
        self._fav.pack(anchor="w", padx=24, pady=8)

        files_card = ctk.CTkFrame(body, corner_radius=12,
                                  fg_color=("#f8fafc", "#1e293b"))
        files_card.pack(fill="x", padx=24, pady=(8, 12))
        ctk.CTkLabel(files_card, text="Fichiers joints",
                     font=("Segoe UI", 13, "bold")).pack(
                         anchor="w", padx=14, pady=(12, 4))
        self._files_hint = ctk.CTkLabel(
            files_card,
            text="Enregistrez l'entree, puis ajoutez des fichiers.",
            font=("Segoe UI", 11),
            text_color="#94a3b8",
            justify="left",
        )
        self._files_hint.pack(anchor="w", padx=14, pady=(0, 12))
        self._files_button = ctk.CTkButton(
            files_card,
            text="Gerer les fichiers",
            height=34,
            fg_color="#4A9EFF",
            hover_color="#2563eb",
            corner_radius=10,
            command=self._open_attachments,
            state="disabled" if self._row is None else "normal",
        )
        self._files_button.pack(fill="x", padx=14, pady=(0, 12))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=(8, 24))

        ctk.CTkButton(
            footer, text="Enregistrer", height=44,
            font=("Segoe UI", 14, "bold"),
            fg_color="#4A9EFF",
            hover_color="#2563eb",
            corner_radius=10,
            command=self._save,
        ).pack(fill="x")

    def _upd_strength(self, _=None):
        score, label, color = CryptoManager.strength(self._pw.get())
        self._str_lbl.configure(text=f"Force : {label}", text_color=color)
        self._str_bar.configure(progress_color=color)
        self._str_bar.set(score / 100)

    def _toggle_show(self):
        self._pw.configure(show="" if self._show_var.get() else "*")

    def _gen_pw(self):
        password = CryptoManager.generate()
        self._pw.delete(0, "end")
        self._pw.insert(0, password)
        self._upd_strength()

    def _populate(self):
        row = self._row
        crypto = self._crypto
        self._title.insert(0, crypto.dec(row["title"]))
        self._user.insert(0, crypto.dec(row["username"]))
        self._pw.insert(0, crypto.dec(row["password"]))
        if row["url"]:
            self._url.insert(0, crypto.dec(row["url"]))
        self._cat.set(row["category"])
        if row["is_favorite"]:
            self._fav.select()
        self._files_hint.configure(
            text=f"{len(self._db.get_attachments_for_entry(row['id']))} fichier(s) joint(s).")
        self._upd_strength()

    def _open_attachments(self):
        if self._row is None:
            self._toast("Enregistrez d'abord l'entree pour ajouter des fichiers.",
                        error=True)
            return
        AttachmentsDialog(self, self._db, self._crypto, self._row, None, self._toast,
                          on_close=self._refresh_attachment_count)

    def _refresh_attachment_count(self):
        if self._row is None:
            return
        count = len(self._db.get_attachments_for_entry(self._row["id"]))
        self._files_hint.configure(text=f"{count} fichier(s) joint(s).")
        self._on_save()

    def _save(self):
        title = self._title.get().strip()
        password = self._pw.get()
        if not title or not password:
            self._toast("Le titre et le mot de passe sont obligatoires.",
                        error=True)
            return

        crypto = self._crypto
        entry = VaultEntry(
            title=crypto.encrypt(title),
            username=crypto.enc(self._user.get().strip()),
            password=crypto.encrypt(password),
            url=crypto.enc(self._url.get().strip()),
            category=self._cat.get(),
            is_favorite=bool(self._fav.get()),
        )

        if self._row:
            entry.id = self._row["id"]
            entry.created_at = self._row["created_at"]
            self._db.update_vault(entry)
        else:
            entry.id = self._db.add_vault(entry)
            self._row = next(
                row for row in self._db.get_all_vault() if row["id"] == entry.id
            )
            self._files_button.configure(state="normal")
            self._files_hint.configure(text="Entree creee. Vous pouvez maintenant joindre des fichiers.")

        self._on_save()
        self._toast("Entree enregistree.")


class AttachmentsDialog(ctk.CTkToplevel):
    def __init__(self, parent, db, crypto, row, on_refresh, toast, on_close=None):
        super().__init__(parent)
        self._db = db
        self._crypto = crypto
        self._row = row
        self._on_refresh = on_refresh
        self._toast = toast
        self._on_close = on_close
        self.title("Fichiers joints")
        self.geometry("560x420")
        self.minsize(520, 380)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build()
        self.refresh()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(16, 10))

        ctk.CTkLabel(header, text="Fichiers joints",
                     font=("Segoe UI", 18, "bold")).pack(side="left")
        ctk.CTkButton(
            header, text="+ Ajouter un fichier", height=34,
            fg_color="#4A9EFF", hover_color="#2563eb",
            corner_radius=10, command=self._add_file,
        ).pack(side="right")

        self._list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._list.pack(fill="both", expand=True, padx=18, pady=(0, 18))

    def _ask_open_file(self) -> str:
        self.grab_release()
        try:
            self.lift()
            self.focus_force()
            return filedialog.askopenfilename(
                parent=self,
                title="Choisir un fichier",
            )
        finally:
            self.grab_set()

    def _ask_save_file(self, initial_name: str) -> str:
        self.grab_release()
        try:
            self.lift()
            self.focus_force()
            return filedialog.asksaveasfilename(
                parent=self,
                title="Exporter le fichier",
                initialfile=initial_name,
            )
        finally:
            self.grab_set()

    def _close(self):
        if self._on_close:
            self._on_close()
        self.destroy()

    def refresh(self):
        for widget in self._list.winfo_children():
            widget.destroy()

        attachments = self._db.get_attachments_for_entry(self._row["id"])
        if not attachments:
            ctk.CTkLabel(
                self._list,
                text="Aucun fichier joint pour cette entree.",
                font=("Segoe UI", 12),
                text_color="#94a3b8",
            ).pack(pady=40)
            return

        for attachment in attachments:
            name = self._crypto.dec(attachment["original_name"])
            row = ctk.CTkFrame(self._list, corner_radius=12,
                               fg_color=("#f8fafc", "#1e293b"))
            row.pack(fill="x", pady=4)

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=12, pady=10)
            ctk.CTkLabel(info, text=name, font=("Segoe UI", 12, "bold")).pack(anchor="w")
            ctk.CTkLabel(info, text=format_size(attachment["size_bytes"]),
                         font=("Segoe UI", 10), text_color="#94a3b8").pack(anchor="w")

            ctk.CTkButton(
                row, text="Exporter", width=90, height=30,
                fg_color=("#e2e8f0", "#334155"),
                hover_color=("#cbd5e1", "#475569"),
                text_color=("#374151", "#e2e8f0"),
                corner_radius=8,
                command=lambda a=attachment: self._export_attachment(a),
            ).pack(side="right", padx=6)
            ctk.CTkButton(
                row, text="Supprimer", width=90, height=30,
                fg_color=("#fee2e2", "#3b1515"),
                hover_color=("#fecaca", "#5a1f1f"),
                text_color="#ef4444",
                corner_radius=8,
                command=lambda a=attachment: self._delete_attachment(a),
            ).pack(side="right", padx=6)

    def _add_file(self):
        path = self._ask_open_file()
        if not path:
            return
        try:
            size = os.path.getsize(path)
            if size > MAX_ATTACHMENT_SIZE:
                self._toast("Fichier trop volumineux. Limite : 25 MB.", error=True)
                return

            with open(path, "rb") as fh:
                plain_bytes = fh.read()

            stored_name = secrets.token_hex(16) + ".bin"
            target_path = os.path.join(ATTACHMENTS_DIR, stored_name)
            encrypted_bytes = self._crypto.encrypt_bytes(plain_bytes)

            with open(target_path, "wb") as fh:
                fh.write(encrypted_bytes)

            self._db.add_attachment(VaultAttachment(
                entry_id=self._row["id"],
                stored_name=stored_name,
                original_name=self._crypto.encrypt(os.path.basename(path)),
                size_bytes=size,
            ))

            self.refresh()
            if self._on_refresh:
                self._on_refresh()
            self._toast("Fichier ajoute au coffre.")
        except Exception as exc:
            self._toast(f"Ajout impossible : {exc}", error=True)

    def _export_attachment(self, attachment):
        try:
            original_name = self._crypto.dec(attachment["original_name"])
            source_path = os.path.join(ATTACHMENTS_DIR, attachment["stored_name"])
            initial_path = os.path.join(tempfile.gettempdir(), original_name)
            destination = self._ask_save_file(os.path.basename(initial_path))
            if not destination:
                return

            with open(source_path, "rb") as fh:
                encrypted_bytes = fh.read()
            plain_bytes = self._crypto.decrypt_bytes(encrypted_bytes)
            with open(destination, "wb") as fh:
                fh.write(plain_bytes)
            self._toast("Fichier exporte.")
        except Exception as exc:
            self._toast(f"Export impossible : {exc}", error=True)

    def _delete_attachment(self, attachment):
        try:
            path = os.path.join(ATTACHMENTS_DIR, attachment["stored_name"])
            if os.path.exists(path):
                os.remove(path)
            self._db.delete_attachment(attachment["id"])
            self.refresh()
            if self._on_refresh:
                self._on_refresh()
            self._toast("Fichier supprime.")
        except Exception as exc:
            self._toast(f"Suppression impossible : {exc}", error=True)
