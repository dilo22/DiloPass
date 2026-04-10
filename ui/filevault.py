import os
import secrets
from tkinter import filedialog

import customtkinter as ctk

from core.crypto import CryptoManager
from core.database import FILE_VAULT_DIR, DatabaseManager

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


def _fmt_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


class FileVaultView(ctk.CTkFrame):
    def __init__(self, parent, db: DatabaseManager, crypto: CryptoManager,
                 show_toast):
        super().__init__(parent, fg_color="transparent")
        self._db = db
        self._crypto = crypto
        self._toast = show_toast
        self._selected_folder_id: int | None = None
        self._selected_folder_name: str = ""
        self._expanded: set[int] = set()
        self._build()
        self.refresh()

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(16, 8))
        ctk.CTkLabel(top, text="Coffre Fichiers",
                     font=("Segoe UI", 22, "bold")).pack(side="left")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=8)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # ── Panneau gauche : arbre des dossiers ───────────────────────────
        self._left = ctk.CTkFrame(body, width=230, corner_radius=12,
                                  fg_color=("#f1f5f9", "#1e293b"))
        self._left.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        self._left.pack_propagate(False)

        folder_header = ctk.CTkFrame(self._left, fg_color="transparent")
        folder_header.pack(fill="x", padx=10, pady=(12, 6))
        ctk.CTkLabel(folder_header, text="Dossiers",
                     font=("Segoe UI", 12, "bold"),
                     text_color="#94a3b8").pack(side="left")
        ctk.CTkButton(
            folder_header, text="+", width=30, height=28,
            font=("Segoe UI", 14, "bold"),
            fg_color="#4A9EFF", hover_color="#2563eb",
            corner_radius=8,
            command=lambda: self._open_folder_dialog(parent_id=None),
        ).pack(side="right")

        self._tree = ctk.CTkScrollableFrame(self._left, fg_color="transparent")
        self._tree.pack(fill="both", expand=True, padx=4, pady=(0, 8))

        # ── Panneau droit : fichiers ───────────────────────────────────────
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        right_hdr = ctk.CTkFrame(right, fg_color="transparent")
        right_hdr.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self._folder_label = ctk.CTkLabel(
            right_hdr, text="Sélectionnez un dossier",
            font=("Segoe UI", 16, "bold"))
        self._folder_label.pack(side="left")

        self._add_file_btn = ctk.CTkButton(
            right_hdr, text="+ Ajouter un fichier",
            width=170, height=36,
            font=("Segoe UI", 13, "bold"),
            fg_color="#4A9EFF", hover_color="#2563eb",
            corner_radius=10,
            state="disabled",
            command=self._open_add_file_dialog,
        )
        self._add_file_btn.pack(side="right")

        self._file_scroll = ctk.CTkScrollableFrame(
            right, fg_color="transparent", corner_radius=12)
        self._file_scroll.grid(row=1, column=0, sticky="nsew")

    # ── Rafraîchissement ──────────────────────────────────────────────────────

    def refresh(self):
        self._refresh_tree()
        self._refresh_files()

    def _refresh_tree(self):
        for w in self._tree.winfo_children():
            w.destroy()

        root_folders = self._db.get_file_vault_folders(parent_id=None)
        if not root_folders:
            ctk.CTkLabel(
                self._tree,
                text="Aucun dossier.\nCliquez sur + pour créer.",
                font=("Segoe UI", 11),
                text_color="#64748b",
                justify="center",
            ).pack(pady=20)
            return

        for folder in root_folders:
            self._render_node(self._tree, folder, depth=0)

    def _render_node(self, parent_widget, folder, depth: int):
        folder_id = folder["id"]
        try:
            name = self._crypto.dec(folder["name"])
        except Exception:
            name = "???"

        is_selected = self._selected_folder_id == folder_id
        is_expanded = folder_id in self._expanded
        children = self._db.get_file_vault_folders(parent_id=folder_id)
        has_children = bool(children)

        node = ctk.CTkFrame(parent_widget, fg_color="transparent")
        node.pack(fill="x", pady=1)

        row = ctk.CTkFrame(
            node, corner_radius=8,
            fg_color=("#4A9EFF", "#1e3a5f") if is_selected else "transparent",
        )
        row.pack(fill="x")

        if depth > 0:
            ctk.CTkFrame(row, width=depth * 18, fg_color="transparent").pack(side="left")

        # Flèche expand/collapse
        arrow = "▼" if is_expanded else "▶" if has_children else "   "
        ctk.CTkButton(
            row, text=arrow, width=22, height=28,
            fg_color="transparent",
            hover_color=("#1e3a5f", "#1e3a5f") if is_selected else ("#dbeafe", "#334155"),
            text_color=("white", "white") if is_selected else ("#374151", "#cbd5e1"),
            font=("Segoe UI", 9),
            command=lambda fid=folder_id: self._toggle(fid),
        ).pack(side="left")

        # Bouton dossier
        ctk.CTkButton(
            row, text=f"📁  {name}",
            anchor="w", height=28,
            fg_color="transparent",
            hover_color=("#dbeafe", "#1e3a5f"),
            text_color=("white", "white") if is_selected else ("#374151", "#cbd5e1"),
            font=("Segoe UI", 12),
            command=lambda fid=folder_id, n=name: self._select_folder(fid, n),
        ).pack(side="left", fill="x", expand=True)

        # Bouton options ⋯
        ctk.CTkButton(
            row, text="⋯", width=26, height=26,
            fg_color="transparent",
            hover_color=("#e2e8f0", "#334155"),
            text_color=("white", "white") if is_selected else ("#94a3b8", "#64748b"),
            font=("Segoe UI", 13),
            command=lambda fid=folder_id, n=name: self._show_folder_menu(fid, n),
        ).pack(side="right", padx=4)

        if is_expanded:
            children_frame = ctk.CTkFrame(node, fg_color="transparent")
            children_frame.pack(fill="x")
            for child in children:
                self._render_node(children_frame, child, depth + 1)

    def _toggle(self, folder_id: int):
        if folder_id in self._expanded:
            self._expanded.discard(folder_id)
        else:
            self._expanded.add(folder_id)
        self._refresh_tree()

    def _select_folder(self, folder_id: int, name: str):
        self._selected_folder_id = folder_id
        self._selected_folder_name = name
        self._folder_label.configure(text=f"📁  {name}")
        self._add_file_btn.configure(state="normal")
        self._refresh_tree()
        self._refresh_files()

    # ── Menu contextuel dossier ───────────────────────────────────────────────

    def _show_folder_menu(self, folder_id: int, name: str):
        menu = ctk.CTkToplevel(self)
        menu.overrideredirect(True)
        x = self.winfo_pointerx()
        y = self.winfo_pointery()
        menu.geometry(f"168x130+{x}+{y}")
        menu.grab_set()
        menu.focus_set()

        def close():
            try:
                menu.destroy()
            except Exception:
                pass

        ctk.CTkButton(
            menu, text="  📁  Sous-dossier", anchor="w",
            fg_color="transparent",
            hover_color=("#e2e8f0", "#334155"),
            height=36,
            command=lambda: (close(), self._open_folder_dialog(parent_id=folder_id)),
        ).pack(fill="x", padx=4, pady=(4, 0))

        ctk.CTkButton(
            menu, text="  ✏️  Renommer", anchor="w",
            fg_color="transparent",
            hover_color=("#e2e8f0", "#334155"),
            height=36,
            command=lambda: (close(), self._open_rename_dialog(folder_id, name)),
        ).pack(fill="x", padx=4)

        ctk.CTkButton(
            menu, text="  🗑  Supprimer", anchor="w",
            fg_color="transparent",
            hover_color=("#fee2e2", "#3b1515"),
            text_color="#ef4444",
            height=36,
            command=lambda: (close(), self._delete_folder(folder_id)),
        ).pack(fill="x", padx=4, pady=(0, 4))

        menu.bind("<FocusOut>", lambda _: menu.after(50, close))

    # ── Renommer dossier ──────────────────────────────────────────────────────

    def _open_rename_dialog(self, folder_id: int, current_name: str):
        RenameFolderDialog(self, self._db, self._crypto,
                           folder_id=folder_id, current_name=current_name,
                           on_save=self._refresh_tree, toast=self._toast)

    # ── Suppression dossier ───────────────────────────────────────────────────

    def _delete_folder(self, folder_id: int):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Supprimer le dossier")
        dlg.geometry("380x170")
        dlg.grab_set()
        ctk.CTkLabel(
            dlg,
            text="Supprimer ce dossier et tout son contenu\n(sous-dossiers et fichiers) ?",
            font=("Segoe UI", 13), justify="center",
        ).pack(pady=24)
        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.pack()
        ctk.CTkButton(btns, text="Annuler", width=130,
                      fg_color=("#e2e8f0", "#334155"),
                      command=dlg.destroy).pack(side="left", padx=8)
        ctk.CTkButton(btns, text="Supprimer", width=130,
                      fg_color="#ef4444", hover_color="#dc2626",
                      command=lambda: self._confirm_delete_folder(folder_id, dlg),
                      ).pack(side="left", padx=8)

    def _confirm_delete_folder(self, folder_id: int, dlg):
        try:
            self._delete_folder_recursive(folder_id)
            self._db.delete_file_vault_folder(folder_id)

            # Réinitialiser si le dossier sélectionné est supprimé ou est un descendant
            all_ids = self._db.get_all_folder_ids_recursive(folder_id) if False else []
            deleted_ids = set(self._collect_ids(folder_id))
            if self._selected_folder_id in deleted_ids:
                self._selected_folder_id = None
                self._folder_label.configure(text="Sélectionnez un dossier")
                self._add_file_btn.configure(state="disabled")

            dlg.destroy()
            self.refresh()
            self._toast("Dossier supprimé.")
        except Exception as exc:
            self._toast(f"Erreur : {exc}", error=True)

    def _collect_ids(self, folder_id: int) -> list[int]:
        """Collecte l'ID du dossier + tous ses descendants."""
        ids = [folder_id]
        for child in self._db.get_file_vault_folders(parent_id=folder_id):
            ids.extend(self._collect_ids(child["id"]))
        return ids

    def _delete_folder_recursive(self, folder_id: int):
        """Supprime les fichiers physiques chiffrés récursivement."""
        for f in self._db.get_file_vault_files(folder_id):
            path = os.path.join(FILE_VAULT_DIR, f["stored_name"])
            if os.path.exists(path):
                os.remove(path)
        for child in self._db.get_file_vault_folders(parent_id=folder_id):
            self._delete_folder_recursive(child["id"])

    # ── Fichiers ──────────────────────────────────────────────────────────────

    def _refresh_files(self):
        for w in self._file_scroll.winfo_children():
            w.destroy()

        if self._selected_folder_id is None:
            ctk.CTkLabel(
                self._file_scroll,
                text="Sélectionnez un dossier dans le panneau de gauche.",
                font=("Segoe UI", 13), text_color="#94a3b8",
            ).pack(pady=60)
            return

        files = self._db.get_file_vault_files(self._selected_folder_id)
        if not files:
            ctk.CTkLabel(
                self._file_scroll,
                text="Aucun fichier dans ce dossier.\nCliquez sur '+ Ajouter un fichier'.",
                font=("Segoe UI", 13), text_color="#94a3b8", justify="center",
            ).pack(pady=60)
            return

        for f in files:
            self._make_file_card(f)

    def _make_file_card(self, f):
        try:
            title = self._crypto.dec(f["title"])
            original_name = self._crypto.dec(f["original_name"])
        except Exception:
            title = "???"
            original_name = "???"

        card = ctk.CTkFrame(self._file_scroll, corner_radius=12,
                            fg_color=("#f8fafc", "#1e293b"))
        card.pack(fill="x", pady=4, padx=2)

        icon_frame = ctk.CTkFrame(card, width=48, height=48, corner_radius=10,
                                  fg_color=("#dbeafe", "#16355f"))
        icon_frame.pack(side="left", padx=14, pady=12)
        icon_frame.pack_propagate(False)
        ctk.CTkLabel(icon_frame, text="📄", font=("Segoe UI", 20)).place(
            relx=0.5, rely=0.5, anchor="center")

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, pady=12)
        ctk.CTkLabel(info, text=title,
                     font=("Segoe UI", 13, "bold"), anchor="w").pack(anchor="w")
        ctk.CTkLabel(info,
                     text=f"{original_name}  •  {_fmt_size(f['size_bytes'])}",
                     font=("Segoe UI", 10), text_color="#94a3b8",
                     anchor="w").pack(anchor="w")

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.pack(side="right", padx=12, pady=12)

        ctk.CTkButton(
            btns, text="Exporter", width=90, height=32,
            fg_color=("#e2e8f0", "#334155"),
            hover_color=("#cbd5e1", "#475569"),
            text_color=("#374151", "#e2e8f0"),
            corner_radius=8,
            command=lambda file=f: self._export_file(file),
        ).pack(pady=(0, 6))

        ctk.CTkButton(
            btns, text="Supprimer", width=90, height=32,
            fg_color=("#fee2e2", "#3b1515"),
            hover_color=("#fecaca", "#5a1f1f"),
            text_color="#ef4444",
            corner_radius=8,
            command=lambda file=f: self._confirm_delete_file(file),
        ).pack()

    def _open_add_file_dialog(self):
        if self._selected_folder_id is None:
            self._toast("Sélectionnez d'abord un dossier.", error=True)
            return
        AddFileDialog(self, self._db, self._crypto, self._selected_folder_id,
                      on_save=self._refresh_files, toast=self._toast)

    def _export_file(self, f):
        try:
            original_name = self._crypto.dec(f["original_name"])
            source_path = os.path.join(FILE_VAULT_DIR, f["stored_name"])

            destination = filedialog.asksaveasfilename(
                title="Exporter le fichier",
                initialfile=original_name,
            )
            if not destination:
                return

            with open(source_path, "rb") as fh:
                encrypted = fh.read()
            plain = self._crypto.decrypt_bytes(encrypted)
            with open(destination, "wb") as fh:
                fh.write(plain)
            self._toast("Fichier exporté.")
        except Exception as exc:
            self._toast(f"Export impossible : {exc}", error=True)

    def _confirm_delete_file(self, f):
        try:
            title = self._crypto.dec(f["title"])
        except Exception:
            title = "ce fichier"

        dlg = ctk.CTkToplevel(self)
        dlg.title("Supprimer le fichier")
        dlg.geometry("360x160")
        dlg.grab_set()
        ctk.CTkLabel(dlg, text=f"Supprimer « {title} » ?\nCette action est irréversible.",
                     font=("Segoe UI", 13), justify="center").pack(pady=24)
        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.pack()
        ctk.CTkButton(btns, text="Annuler", width=120,
                      fg_color=("#e2e8f0", "#334155"),
                      command=dlg.destroy).pack(side="left", padx=8)
        ctk.CTkButton(btns, text="Supprimer", width=120,
                      fg_color="#ef4444", hover_color="#dc2626",
                      command=lambda: self._do_delete_file(f, dlg),
                      ).pack(side="left", padx=8)

    def _do_delete_file(self, f, dlg):
        try:
            path = os.path.join(FILE_VAULT_DIR, f["stored_name"])
            if os.path.exists(path):
                os.remove(path)
            self._db.delete_file_vault_file(f["id"])
            dlg.destroy()
            self._refresh_files()
            self._toast("Fichier supprimé.")
        except Exception as exc:
            self._toast(f"Suppression impossible : {exc}", error=True)

    def _open_folder_dialog(self, parent_id: int | None):
        FolderDialog(self, self._db, self._crypto,
                     parent_id=parent_id,
                     on_save=self._refresh_tree,
                     toast=self._toast)


# ── Dialogue : créer un dossier ───────────────────────────────────────────────

class FolderDialog(ctk.CTkToplevel):
    def __init__(self, parent, db, crypto, parent_id, on_save, toast):
        super().__init__(parent)
        self._db = db
        self._crypto = crypto
        self._parent_id = parent_id
        self._on_save = on_save
        self._toast = toast
        self.title("Nouveau sous-dossier" if parent_id else "Nouveau dossier")
        self.geometry("400x200")
        self.resizable(False, False)
        self.grab_set()
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Nom du dossier *",
                     font=("Segoe UI", 16, "bold")).pack(pady=(24, 12))
        self._name = ctk.CTkEntry(self, height=40, corner_radius=8,
                                   font=("Segoe UI", 13), width=320)
        self._name.pack(padx=24)
        self._name.focus()
        self._name.bind("<Return>", lambda _: self._save())
        ctk.CTkButton(
            self, text="Créer", height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color="#4A9EFF", hover_color="#2563eb",
            corner_radius=10, command=self._save,
        ).pack(fill="x", padx=24, pady=16)

    def _save(self):
        name = self._name.get().strip()
        if not name:
            self._toast("Le nom est obligatoire.", error=True)
            return
        try:
            self._db.add_file_vault_folder(
                name=self._crypto.encrypt(name),
                parent_id=self._parent_id,
            )
            self._on_save()
            self.destroy()
            self._toast("Dossier créé.")
        except Exception as exc:
            self._toast(f"Erreur : {exc}", error=True)


# ── Dialogue : renommer un dossier ────────────────────────────────────────────

class RenameFolderDialog(ctk.CTkToplevel):
    def __init__(self, parent, db, crypto, folder_id, current_name, on_save, toast):
        super().__init__(parent)
        self._db = db
        self._crypto = crypto
        self._folder_id = folder_id
        self._on_save = on_save
        self._toast = toast
        self.title("Renommer le dossier")
        self.geometry("400x200")
        self.resizable(False, False)
        self.grab_set()
        self._build(current_name)

    def _build(self, current_name: str):
        ctk.CTkLabel(self, text="Nouveau nom *",
                     font=("Segoe UI", 16, "bold")).pack(pady=(24, 12))
        self._name = ctk.CTkEntry(self, height=40, corner_radius=8,
                                   font=("Segoe UI", 13), width=320)
        self._name.pack(padx=24)
        self._name.insert(0, current_name)
        self._name.focus()
        self._name.select_range(0, "end")
        self._name.bind("<Return>", lambda _: self._save())
        ctk.CTkButton(
            self, text="Renommer", height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color="#4A9EFF", hover_color="#2563eb",
            corner_radius=10, command=self._save,
        ).pack(fill="x", padx=24, pady=16)

    def _save(self):
        name = self._name.get().strip()
        if not name:
            self._toast("Le nom est obligatoire.", error=True)
            return
        try:
            self._db.rename_file_vault_folder(
                folder_id=self._folder_id,
                name=self._crypto.encrypt(name),
            )
            self._on_save()
            self.destroy()
            self._toast("Dossier renommé.")
        except Exception as exc:
            self._toast(f"Erreur : {exc}", error=True)


# ── Dialogue : ajouter un fichier ─────────────────────────────────────────────

class AddFileDialog(ctk.CTkToplevel):
    def __init__(self, parent, db, crypto, folder_id, on_save, toast):
        super().__init__(parent)
        self._db = db
        self._crypto = crypto
        self._folder_id = folder_id
        self._on_save = on_save
        self._toast = toast
        self._chosen_path: str | None = None
        self.title("Ajouter un fichier")
        self.geometry("480x310")
        self.resizable(False, False)
        self.grab_set()
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Ajouter un fichier",
                     font=("Segoe UI", 16, "bold")).pack(pady=(20, 4))

        ctk.CTkLabel(self, text="Titre *", font=("Segoe UI", 12),
                     text_color="#94a3b8").pack(anchor="w", padx=24, pady=(10, 2))
        self._title = ctk.CTkEntry(self, height=38, corner_radius=8,
                                    font=("Segoe UI", 13))
        self._title.pack(fill="x", padx=24)
        self._title.focus()

        ctk.CTkLabel(self, text="Fichier *", font=("Segoe UI", 12),
                     text_color="#94a3b8").pack(anchor="w", padx=24, pady=(14, 2))

        file_row = ctk.CTkFrame(self, fg_color="transparent")
        file_row.pack(fill="x", padx=24)

        self._file_label = ctk.CTkLabel(
            file_row, text="Aucun fichier sélectionné",
            font=("Segoe UI", 11), text_color="#94a3b8", anchor="w")
        self._file_label.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            file_row, text="Parcourir…", width=110, height=34,
            fg_color=("#e2e8f0", "#334155"),
            hover_color=("#cbd5e1", "#475569"),
            text_color=("#374151", "#e2e8f0"),
            corner_radius=8, command=self._pick_file,
        ).pack(side="right")

        ctk.CTkButton(
            self, text="Enregistrer", height=42,
            font=("Segoe UI", 13, "bold"),
            fg_color="#4A9EFF", hover_color="#2563eb",
            corner_radius=10, command=self._save,
        ).pack(fill="x", padx=24, pady=20)

    def _pick_file(self):
        path = filedialog.askopenfilename(title="Choisir un fichier")
        if path:
            self._chosen_path = path
            name = os.path.basename(path)
            display = name if len(name) <= 45 else name[:42] + "…"
            self._file_label.configure(text=display,
                                        text_color=("#374151", "#e2e8f0"))

    def _save(self):
        title = self._title.get().strip()
        if not title:
            self._toast("Le titre est obligatoire.", error=True)
            return
        if not self._chosen_path:
            self._toast("Veuillez sélectionner un fichier.", error=True)
            return

        try:
            size = os.path.getsize(self._chosen_path)
            if size > MAX_FILE_SIZE:
                self._toast("Fichier trop volumineux. Limite : 100 MB.", error=True)
                return

            with open(self._chosen_path, "rb") as fh:
                plain_bytes = fh.read()

            stored_name = secrets.token_hex(16) + ".bin"
            target_path = os.path.join(FILE_VAULT_DIR, stored_name)
            encrypted_bytes = self._crypto.encrypt_bytes(plain_bytes)

            with open(target_path, "wb") as fh:
                fh.write(encrypted_bytes)

            self._db.add_file_vault_file(
                folder_id=self._folder_id,
                title=self._crypto.encrypt(title),
                stored_name=stored_name,
                original_name=self._crypto.encrypt(os.path.basename(self._chosen_path)),
                size_bytes=size,
            )

            self._on_save()
            self.destroy()
            self._toast("Fichier ajouté au coffre.")
        except Exception as exc:
            self._toast(f"Ajout impossible : {exc}", error=True)
