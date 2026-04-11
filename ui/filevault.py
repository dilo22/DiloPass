import os
import secrets
import tempfile
import threading
from io import BytesIO
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image
from ui.window_utils import apply_window_icon

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

from core.crypto import CryptoManager
from core.database import FILE_VAULT_DIR, DatabaseManager



def _fmt_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


class FileVaultView(ctk.CTkFrame):
    def __init__(self, parent, db: DatabaseManager, crypto: CryptoManager, show_toast):
        super().__init__(parent, fg_color="transparent")
        self._db = db
        self._crypto = crypto
        self._toast = show_toast
        self._is_revealed = False
        self._root_folder_id = self._ensure_root_folder()
        self._selected_folder_id: int | None = self._root_folder_id
        self._selected_folder_name: str = "Mes fichiers"
        self._expanded: set[int] = set()
        self._selected_files: set[int] = set()
        self._file_vars: dict[int, ctk.BooleanVar] = {}
        self._build()
        self.refresh()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(16, 8))

        title_row = ctk.CTkFrame(top, fg_color="transparent")
        title_row.pack(side="left")
        ctk.CTkLabel(title_row, text="Coffre Fichiers", font=("Segoe UI", 22, "bold")).pack(side="left")
        self._reveal_btn = ctk.CTkButton(
            title_row,
            text="?",
            width=26,
            height=26,
            font=("Segoe UI", 12, "bold"),
            corner_radius=13,
            fg_color=("#e2e8f0", "#334155"),
            hover_color=("#cbd5e1", "#475569"),
            text_color=("#374151", "#e2e8f0"),
            command=self._toggle_reveal,
        )
        self._reveal_btn.pack(side="left", padx=(8, 0))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=8)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self._left = ctk.CTkFrame(body, width=230, corner_radius=12, fg_color=("#f1f5f9", "#1e293b"))
        self._left.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        self._left.pack_propagate(False)

        folder_header = ctk.CTkFrame(self._left, fg_color="transparent")
        folder_header.pack(fill="x", padx=10, pady=(12, 6))
        ctk.CTkLabel(folder_header, text="Dossiers", font=("Segoe UI", 12, "bold"), text_color="#94a3b8").pack(side="left")
        ctk.CTkButton(
            folder_header,
            text="+",
            width=30,
            height=28,
            font=("Segoe UI", 14, "bold"),
            fg_color="#4A9EFF",
            hover_color="#2563eb",
            corner_radius=8,
            command=lambda: self._open_folder_dialog(parent_id=None),
        ).pack(side="right")

        self._tree = ctk.CTkScrollableFrame(self._left, fg_color="transparent")
        self._tree.pack(fill="both", expand=True, padx=4, pady=(0, 8))

        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(2, weight=1)
        right.columnconfigure(0, weight=1)

        right_hdr = ctk.CTkFrame(right, fg_color="transparent")
        right_hdr.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        self._folder_label = ctk.CTkLabel(right_hdr, text="Mes fichiers", font=("Segoe UI", 16, "bold"))
        self._folder_label.pack(side="left")

        self._add_file_btn = ctk.CTkButton(
            right_hdr,
            text="+ Ajouter un fichier",
            width=170,
            height=36,
            font=("Segoe UI", 13, "bold"),
            fg_color="#4A9EFF",
            hover_color="#2563eb",
            corner_radius=10,
            command=self._open_add_file_dialog,
        )
        self._add_file_btn.pack(side="right")

        # Barre d'actions groupées (masquée jusqu'à ce qu'un fichier soit sélectionné)
        self._bulk_bar = ctk.CTkFrame(right, corner_radius=10,
                                      fg_color=("#e0f2fe", "#0f2744"),
                                      border_width=1, border_color=("#7dd3fc", "#1e3a5f"))
        self._bulk_bar.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self._bulk_bar.grid_remove()

        self._bulk_label = ctk.CTkLabel(self._bulk_bar, text="", font=("Segoe UI", 12, "bold"),
                                        text_color=("#0369a1", "#7dd3fc"))
        self._bulk_label.pack(side="left", padx=12)

        self._select_all_var = ctk.BooleanVar(value=False)
        self._select_all_chk = ctk.CTkCheckBox(
            self._bulk_bar, text="Tout", variable=self._select_all_var,
            font=("Segoe UI", 12), width=60,
            command=self._toggle_select_all,
        )
        self._select_all_chk.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            self._bulk_bar, text="Deplacer", width=90, height=30,
            font=("Segoe UI", 12), corner_radius=8,
            fg_color=("#dbeafe", "#1e3a5f"), hover_color=("#bfdbfe", "#1e4a7f"),
            text_color=("#1e3a8a", "#93c5fd"),
            command=self._bulk_move,
        ).pack(side="right", padx=(0, 6), pady=6)

        ctk.CTkButton(
            self._bulk_bar, text="Exporter", width=90, height=30,
            font=("Segoe UI", 12), corner_radius=8,
            fg_color=("#e2e8f0", "#334155"), hover_color=("#cbd5e1", "#475569"),
            text_color=("#374151", "#e2e8f0"),
            command=self._bulk_export,
        ).pack(side="right", padx=(0, 4), pady=6)

        ctk.CTkButton(
            self._bulk_bar, text="Supprimer", width=90, height=30,
            font=("Segoe UI", 12), corner_radius=8,
            fg_color=("#fee2e2", "#3b1515"), hover_color=("#fecaca", "#5a1f1f"),
            text_color="#ef4444",
            command=self._bulk_delete,
        ).pack(side="right", padx=(0, 4), pady=6)

        self._file_scroll = ctk.CTkScrollableFrame(right, fg_color="transparent", corner_radius=12)
        self._file_scroll.grid(row=2, column=0, sticky="nsew")

    def refresh(self):
        if not self._is_revealed:
            self._refresh_hidden()
            return
        self._refresh_tree()
        self._refresh_files()

    def _refresh_hidden(self):
        for w in self._tree.winfo_children():
            w.destroy()
        for w in self._file_scroll.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._file_scroll,
            text="Le coffre fichiers est masque.\nCliquez sur ? pour afficher le contenu.",
            font=("Segoe UI", 13),
            text_color="#94a3b8",
            justify="center",
        ).pack(pady=60)

    def _refresh_tree(self):
        for w in self._tree.winfo_children():
            w.destroy()

        root_folders = self._db.get_file_vault_folders(parent_id=None)
        if not root_folders:
            ctk.CTkLabel(
                self._tree,
                text="Aucun dossier.\nCliquez sur + pour creer.",
                font=("Segoe UI", 11),
                text_color="#64748b",
                justify="center",
            ).pack(pady=20)
            return

        if self._selected_folder_id is None:
            self._selected_folder_id = root_folders[0]["id"]

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

        row = ctk.CTkFrame(node, corner_radius=8, fg_color=("#4A9EFF", "#1e3a5f") if is_selected else "transparent")
        row.pack(fill="x")

        if depth > 0:
            ctk.CTkFrame(row, width=depth * 18, fg_color="transparent").pack(side="left")

        arrow = "v" if is_expanded else ">" if has_children else " "
        ctk.CTkButton(
            row,
            text=arrow,
            width=22,
            height=28,
            fg_color="transparent",
            hover_color=("#1e3a5f", "#1e3a5f") if is_selected else ("#dbeafe", "#334155"),
            text_color=("white", "white") if is_selected else ("#374151", "#cbd5e1"),
            font=("Segoe UI", 9),
            command=lambda fid=folder_id: self._toggle(fid),
        ).pack(side="left")

        ctk.CTkButton(
            row,
            text=name,
            anchor="w",
            height=28,
            fg_color="transparent",
            hover_color=("#dbeafe", "#1e3a5f"),
            text_color=("white", "white") if is_selected else ("#374151", "#cbd5e1"),
            font=("Segoe UI", 12),
            command=lambda fid=folder_id, n=name: self._select_folder(fid, n),
        ).pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            row,
            text="...",
            width=26,
            height=26,
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
        self._folder_label.configure(text=name)
        self._refresh_tree()
        self._refresh_files()

    def _show_folder_menu(self, folder_id: int, name: str):
        is_root = folder_id == self._root_folder_id
        height = 50 if is_root else 130

        # Overlay transparent plein-écran : un clic en dehors du menu le ferme
        overlay = ctk.CTkToplevel(self)
        overlay.overrideredirect(True)
        overlay.attributes("-alpha", 0.01)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        overlay.geometry(f"{sw}x{sh}+0+0")

        menu = ctk.CTkToplevel(self)
        menu.overrideredirect(True)
        x = self.winfo_pointerx()
        y = self.winfo_pointery()
        menu.geometry(f"168x{height}+{x}+{y}")
        menu.lift()

        def close():
            try:
                overlay.destroy()
            except Exception:
                pass
            try:
                menu.destroy()
            except Exception:
                pass

        overlay.bind("<Button-1>", lambda _: close())

        frame = ctk.CTkFrame(menu, corner_radius=8, fg_color=("#ffffff", "#1e293b"),
                             border_width=1, border_color=("#e2e8f0", "#334155"))
        frame.pack(fill="both", expand=True, padx=2, pady=2)

        ctk.CTkButton(
            frame,
            text="  Sous-dossier",
            anchor="w",
            fg_color="transparent",
            hover_color=("#e2e8f0", "#334155"),
            height=36,
            command=lambda: (close(), self._open_folder_dialog(parent_id=folder_id)),
        ).pack(fill="x", padx=4, pady=(4, 0))

        if not is_root:
            ctk.CTkButton(
                frame,
                text="  Renommer",
                anchor="w",
                fg_color="transparent",
                hover_color=("#e2e8f0", "#334155"),
                height=36,
                command=lambda: (close(), self._open_rename_dialog(folder_id, name)),
            ).pack(fill="x", padx=4)

            ctk.CTkButton(
                frame,
                text="  Supprimer",
                anchor="w",
                fg_color="transparent",
                hover_color=("#fee2e2", "#3b1515"),
                text_color="#ef4444",
                height=36,
                command=lambda: (close(), self._delete_folder(folder_id)),
            ).pack(fill="x", padx=4, pady=(0, 4))

    def _open_rename_dialog(self, folder_id: int, current_name: str):
        RenameFolderDialog(
            self,
            self._db,
            self._crypto,
            folder_id=folder_id,
            current_name=current_name,
            on_save=self._refresh_tree,
            toast=self._toast,
        )

    def _delete_folder(self, folder_id: int):
        if folder_id == self._root_folder_id:
            self._toast("Le dossier racine ne peut pas etre supprime.", error=True)
            return
        dlg = ctk.CTkToplevel(self)
        dlg.title("Supprimer le dossier")
        dlg.geometry("380x170")
        dlg.grab_set()
        ctk.CTkLabel(
            dlg,
            text="Supprimer ce dossier et tout son contenu\n(sous-dossiers et fichiers) ?",
            font=("Segoe UI", 13),
            justify="center",
        ).pack(pady=24)
        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.pack()
        ctk.CTkButton(btns, text="Annuler", width=130, fg_color=("#e2e8f0", "#334155"), command=dlg.destroy).pack(side="left", padx=8)
        ctk.CTkButton(
            btns,
            text="Supprimer",
            width=130,
            fg_color="#ef4444",
            hover_color="#dc2626",
            command=lambda: self._confirm_delete_folder(folder_id, dlg),
        ).pack(side="left", padx=8)

    def _confirm_delete_folder(self, folder_id: int, dlg):
        try:
            deleted_ids = set(self._collect_ids(folder_id))
            self._delete_folder_recursive(folder_id)
            self._db.delete_file_vault_folder(folder_id)

            if self._selected_folder_id in deleted_ids:
                self._selected_folder_id = self._root_folder_id
                self._folder_label.configure(text="Mes fichiers")

            dlg.destroy()
            self.refresh()
            self._toast("Dossier supprime.")
        except Exception as exc:
            self._toast(f"Erreur : {exc}", error=True)

    def _collect_ids(self, folder_id: int) -> list[int]:
        ids = [folder_id]
        for child in self._db.get_file_vault_folders(parent_id=folder_id):
            ids.extend(self._collect_ids(child["id"]))
        return ids

    def _delete_folder_recursive(self, folder_id: int):
        for f in self._db.get_file_vault_files(folder_id):
            path = os.path.join(FILE_VAULT_DIR, f["stored_name"])
            if os.path.exists(path):
                os.remove(path)
        for child in self._db.get_file_vault_folders(parent_id=folder_id):
            self._delete_folder_recursive(child["id"])

    def _refresh_files(self):
        self._selected_files.clear()
        self._file_vars.clear()
        self._select_all_var.set(False)
        self._bulk_bar.grid_remove()

        for w in self._file_scroll.winfo_children():
            w.destroy()

        if self._selected_folder_id is None:
            self._selected_folder_id = self._root_folder_id
            ctk.CTkLabel(
                self._file_scroll,
                text="Aucun dossier selectionne.",
                font=("Segoe UI", 13),
                text_color="#94a3b8",
            ).pack(pady=60)
            return

        files = self._db.get_file_vault_files(self._selected_folder_id)
        if not files:
            ctk.CTkLabel(
                self._file_scroll,
                text="Aucun fichier dans ce dossier.\nCliquez sur '+ Ajouter un fichier'.",
                font=("Segoe UI", 13),
                text_color="#94a3b8",
                justify="center",
            ).pack(pady=60)
            return

        for f in files:
            self._make_file_card(f)

    def _make_file_card(self, f):
        file_id = f["id"]
        try:
            title = self._crypto.dec(f["title"])
            original_name = self._crypto.dec(f["original_name"])
        except Exception:
            title = "???"
            original_name = "???"

        var = ctk.BooleanVar(value=False)
        self._file_vars[file_id] = var

        card = ctk.CTkFrame(self._file_scroll, corner_radius=12, fg_color=("#f8fafc", "#1e293b"))
        card.pack(fill="x", pady=4, padx=2)

        chk = ctk.CTkCheckBox(card, text="", variable=var, width=20,
                               command=lambda fid=file_id, v=var, c=card: self._on_file_check(fid, v, c))
        chk.pack(side="left", padx=(12, 0), pady=12)

        icon_frame = ctk.CTkFrame(card, width=48, height=48, corner_radius=10, fg_color=("#dbeafe", "#16355f"))
        icon_frame.pack(side="left", padx=10, pady=12)
        icon_frame.pack_propagate(False)
        ctk.CTkLabel(icon_frame, text="F", font=("Segoe UI", 20)).place(relx=0.5, rely=0.5, anchor="center")

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, pady=12)
        ctk.CTkLabel(info, text=title, font=("Segoe UI", 13, "bold"), anchor="w").pack(anchor="w")
        ctk.CTkLabel(
            info,
            text=f"{original_name} - {_fmt_size(f['size_bytes'])}",
            font=("Segoe UI", 10),
            text_color="#94a3b8",
            anchor="w",
        ).pack(anchor="w")

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.pack(side="right", padx=12, pady=12)

        ctk.CTkButton(
            btns,
            text="Voir",
            width=90,
            height=32,
            fg_color=("#dbeafe", "#16355f"),
            hover_color=("#bfdbfe", "#1e3a8a"),
            text_color=("#1e3a8a", "#dbeafe"),
            corner_radius=8,
            command=lambda file=f: self._preview_file(file),
        ).pack(pady=(0, 6))

        ctk.CTkButton(
            btns,
            text="Exporter",
            width=90,
            height=32,
            fg_color=("#e2e8f0", "#334155"),
            hover_color=("#cbd5e1", "#475569"),
            text_color=("#374151", "#e2e8f0"),
            corner_radius=8,
            command=lambda file=f: self._export_file(file),
        ).pack(pady=(0, 6))

        ctk.CTkButton(
            btns,
            text="Supprimer",
            width=90,
            height=32,
            fg_color=("#fee2e2", "#3b1515"),
            hover_color=("#fecaca", "#5a1f1f"),
            text_color="#ef4444",
            corner_radius=8,
            command=lambda file=f: self._confirm_delete_file(file),
        ).pack()

    def _on_file_check(self, file_id: int, var: ctk.BooleanVar, card: ctk.CTkFrame):
        if var.get():
            self._selected_files.add(file_id)
            card.configure(fg_color=("#dbeafe", "#0f2744"))
        else:
            self._selected_files.discard(file_id)
            card.configure(fg_color=("#f8fafc", "#1e293b"))
        self._update_bulk_bar()

    def _update_bulk_bar(self):
        n = len(self._selected_files)
        if n == 0:
            self._bulk_bar.grid_remove()
            self._select_all_var.set(False)
        else:
            self._bulk_label.configure(text=f"{n} selectionne(s)")
            all_checked = n == len(self._file_vars)
            self._select_all_var.set(all_checked)
            self._bulk_bar.grid()

    def _toggle_select_all(self):
        select = self._select_all_var.get()
        for file_id, var in self._file_vars.items():
            var.set(select)
            if select:
                self._selected_files.add(file_id)
            else:
                self._selected_files.discard(file_id)
        # Mettre à jour la couleur de chaque carte
        for card in self._file_scroll.winfo_children():
            widgets = card.winfo_children()
            if not widgets:
                continue
            chk = widgets[0]
            if isinstance(chk, ctk.CTkCheckBox):
                var = chk.cget("variable") if hasattr(chk, "cget") else None
                card.configure(fg_color=("#dbeafe", "#0f2744") if select else ("#f8fafc", "#1e293b"))
        self._update_bulk_bar()

    def _bulk_delete(self):
        if not self._selected_files:
            return
        n = len(self._selected_files)
        dlg = ctk.CTkToplevel(self)
        dlg.title("Supprimer les fichiers")
        dlg.geometry("380x160")
        dlg.grab_set()
        ctk.CTkLabel(
            dlg,
            text=f"Supprimer {n} fichier(s) ?\nCette action est irreversible.",
            font=("Segoe UI", 13), justify="center",
        ).pack(pady=24)
        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.pack()
        ctk.CTkButton(btns, text="Annuler", width=120,
                      fg_color=("#e2e8f0", "#334155"), command=dlg.destroy).pack(side="left", padx=8)
        ctk.CTkButton(
            btns, text=f"Supprimer {n}", width=130,
            fg_color="#ef4444", hover_color="#dc2626",
            command=lambda: self._do_bulk_delete(dlg),
        ).pack(side="left", padx=8)

    def _do_bulk_delete(self, dlg):
        try:
            for file_id in list(self._selected_files):
                files = [f for f in self._db.get_file_vault_files(self._selected_folder_id)
                         if f["id"] == file_id]
                if files:
                    path = os.path.join(FILE_VAULT_DIR, files[0]["stored_name"])
                    if os.path.exists(path):
                        os.remove(path)
                    self._db.delete_file_vault_file(file_id)
            dlg.destroy()
            self._toast(f"{len(self._selected_files)} fichier(s) supprimes.")
            self._refresh_files()
        except Exception as exc:
            self._toast(f"Erreur : {exc}", error=True)

    def _bulk_export(self):
        if not self._selected_files:
            return
        folder = filedialog.askdirectory(title="Choisir le dossier de destination")
        if not folder:
            return
        exported = 0
        errors = 0
        all_files = self._db.get_file_vault_files(self._selected_folder_id)
        for f in all_files:
            if f["id"] not in self._selected_files:
                continue
            try:
                original_name = self._crypto.dec(f["original_name"])
                source_path = os.path.join(FILE_VAULT_DIR, f["stored_name"])
                with open(source_path, "rb") as fh:
                    plain = self._crypto.decrypt_bytes(fh.read())
                dest = os.path.join(folder, original_name)
                # Evite les collisions de noms
                base, ext = os.path.splitext(original_name)
                counter = 1
                while os.path.exists(dest):
                    dest = os.path.join(folder, f"{base}_{counter}{ext}")
                    counter += 1
                with open(dest, "wb") as fh:
                    fh.write(plain)
                exported += 1
            except Exception:
                errors += 1
        if errors:
            self._toast(f"{exported} exporte(s), {errors} echec(s).", error=True)
        else:
            self._toast(f"{exported} fichier(s) exporte(s).")

    def _bulk_move(self):
        if not self._selected_files:
            return
        FolderPickerDialog(
            self, self._db, self._crypto,
            exclude_folder_id=self._selected_folder_id,
            on_pick=self._do_bulk_move,
        )

    def _do_bulk_move(self, target_folder_id: int):
        try:
            for file_id in list(self._selected_files):
                self._db.move_file_vault_file(file_id, target_folder_id)
            n = len(self._selected_files)
            self._toast(f"{n} fichier(s) deplace(s).")
            self._refresh_files()
        except Exception as exc:
            self._toast(f"Erreur : {exc}", error=True)

    def _open_add_file_dialog(self):
        folder_id = self._selected_folder_id or self._root_folder_id
        AddFileDialog(self, self._db, self._crypto, folder_id, on_save=self._refresh_files, toast=self._toast)

    def _toggle_reveal(self):
        self._is_revealed = not self._is_revealed
        if self._is_revealed:
            self._reveal_btn.configure(fg_color=("#bfdbfe", "#1e3a8a"))
            self._toast("Fichiers affiches.")
        else:
            self._reveal_btn.configure(fg_color=("#e2e8f0", "#334155"))
            self._toast("Fichiers masques.")
        self.refresh()

    def _ensure_root_folder(self) -> int:
        raw = self._db.get_setting("filevault_root_id", "")
        if raw.isdigit():
            folder_id = int(raw)
            row = self._db.get_file_vault_folder(folder_id)
            if row:
                return folder_id
        folder_id = self._db.add_file_vault_folder(name=self._crypto.encrypt("Mes fichiers"), parent_id=None)
        self._db.set_setting("filevault_root_id", str(folder_id))
        return folder_id

    def _preview_file(self, f):
        try:
            source_path = os.path.join(FILE_VAULT_DIR, f["stored_name"])
            with open(source_path, "rb") as fh:
                encrypted = fh.read()
            plain = self._crypto.decrypt_bytes(encrypted)
            original_name = self._crypto.dec(f["original_name"])
            FilePreviewDialog(self, original_name, plain, self._toast)
        except Exception as exc:
            self._toast(f"Previsualisation impossible : {exc}", error=True)

    def _export_file(self, f):
        try:
            original_name = self._crypto.dec(f["original_name"])
            source_path = os.path.join(FILE_VAULT_DIR, f["stored_name"])

            destination = filedialog.asksaveasfilename(title="Exporter le fichier", initialfile=original_name)
            if not destination:
                return

            with open(source_path, "rb") as fh:
                encrypted = fh.read()
            plain = self._crypto.decrypt_bytes(encrypted)
            with open(destination, "wb") as fh:
                fh.write(plain)
            self._toast("Fichier exporte.")
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
        ctk.CTkLabel(dlg, text=f"Supprimer {title} ?\nCette action est irreversible.", font=("Segoe UI", 13), justify="center").pack(pady=24)
        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.pack()
        ctk.CTkButton(btns, text="Annuler", width=120, fg_color=("#e2e8f0", "#334155"), command=dlg.destroy).pack(side="left", padx=8)
        ctk.CTkButton(
            btns,
            text="Supprimer",
            width=120,
            fg_color="#ef4444",
            hover_color="#dc2626",
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
            self._toast("Fichier supprime.")
        except Exception as exc:
            self._toast(f"Suppression impossible : {exc}", error=True)

    def _open_folder_dialog(self, parent_id: int | None):
        FolderDialog(self, self._db, self._crypto, parent_id=parent_id, on_save=self._refresh_tree, toast=self._toast)


class FolderPickerDialog(ctk.CTkToplevel):
    """Dialogue de sélection d'un dossier destination pour un déplacement groupé."""

    def __init__(self, parent, db, crypto, exclude_folder_id: int, on_pick):
        super().__init__(parent)
        apply_window_icon(self)
        self._db = db
        self._crypto = crypto
        self._exclude = exclude_folder_id
        self._on_pick = on_pick
        self._selected_id: int | None = None
        self.title("Choisir le dossier destination")
        self.geometry("360x420")
        self.resizable(False, False)
        self.grab_set()
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Deplacer vers :", font=("Segoe UI", 15, "bold")).pack(pady=(20, 8), padx=20, anchor="w")

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self._btn_confirm = ctk.CTkButton(
            self, text="Deplacer ici", height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color="#4A9EFF", hover_color="#2563eb",
            corner_radius=10, state="disabled",
            command=self._confirm,
        )
        self._btn_confirm.pack(fill="x", padx=20, pady=(0, 16))

        self._render_folders(None, depth=0)

    def _render_folders(self, parent_id, depth: int):
        folders = self._db.get_file_vault_folders(parent_id=parent_id)
        for folder in folders:
            fid = folder["id"]
            try:
                name = self._crypto.dec(folder["name"])
            except Exception:
                name = "???"

            row = ctk.CTkFrame(self._scroll, corner_radius=8, fg_color="transparent")
            row.pack(fill="x", pady=1)

            if depth > 0:
                ctk.CTkFrame(row, width=depth * 16, fg_color="transparent").pack(side="left")

            prefix = "  " * depth + ("📁 " if depth == 0 else "└ ")
            btn = ctk.CTkButton(
                row, text=f"{prefix}{name}", anchor="w",
                height=32, fg_color="transparent",
                hover_color=("#dbeafe", "#1e3a5f"),
                text_color=("#374151", "#cbd5e1"),
                font=("Segoe UI", 12),
                state="disabled" if fid == self._exclude else "normal",
                command=lambda fid=fid, b=None, n=name: self._select(fid, n),
            )
            btn.pack(fill="x", side="left", expand=True)
            # Garder la référence du bouton pour le highlight
            btn.configure(command=lambda fid=fid, b=btn, n=name: self._select(fid, b, n))

            self._render_folders(parent_id=fid, depth=depth + 1)

    def _select(self, folder_id: int, btn: ctk.CTkButton, name: str):
        # Réinitialiser tous les boutons
        for w in self._scroll.winfo_children():
            for child in w.winfo_children():
                if isinstance(child, ctk.CTkButton):
                    child.configure(fg_color="transparent")
        btn.configure(fg_color=("#4A9EFF", "#1e3a5f"))
        self._selected_id = folder_id
        self._btn_confirm.configure(state="normal", text=f'Deplacer ici : "{name}"')

    def _confirm(self):
        if self._selected_id is not None:
            self.destroy()
            self._on_pick(self._selected_id)


class FolderDialog(ctk.CTkToplevel):
    def __init__(self, parent, db, crypto, parent_id, on_save, toast):
        super().__init__(parent)
        apply_window_icon(self)
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
        ctk.CTkLabel(self, text="Nom du dossier *", font=("Segoe UI", 16, "bold")).pack(pady=(24, 12))
        self._name = ctk.CTkEntry(self, height=40, corner_radius=8, font=("Segoe UI", 13), width=320)
        self._name.pack(padx=24)
        self._name.focus()
        self._name.bind("<Return>", lambda _: self._save())
        ctk.CTkButton(
            self,
            text="Creer",
            height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color="#4A9EFF",
            hover_color="#2563eb",
            corner_radius=10,
            command=self._save,
        ).pack(fill="x", padx=24, pady=16)

    def _save(self):
        name = self._name.get().strip()
        if not name:
            self._toast("Le nom est obligatoire.", error=True)
            return
        try:
            self._db.add_file_vault_folder(name=self._crypto.encrypt(name), parent_id=self._parent_id)
            self._on_save()
            self.destroy()
            self._toast("Dossier cree.")
        except Exception as exc:
            self._toast(f"Erreur : {exc}", error=True)


class RenameFolderDialog(ctk.CTkToplevel):
    def __init__(self, parent, db, crypto, folder_id, current_name, on_save, toast):
        super().__init__(parent)
        apply_window_icon(self)
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
        ctk.CTkLabel(self, text="Nouveau nom *", font=("Segoe UI", 16, "bold")).pack(pady=(24, 12))
        self._name = ctk.CTkEntry(self, height=40, corner_radius=8, font=("Segoe UI", 13), width=320)
        self._name.pack(padx=24)
        self._name.insert(0, current_name)
        self._name.focus()
        self._name.select_range(0, "end")
        self._name.bind("<Return>", lambda _: self._save())
        ctk.CTkButton(
            self,
            text="Renommer",
            height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color="#4A9EFF",
            hover_color="#2563eb",
            corner_radius=10,
            command=self._save,
        ).pack(fill="x", padx=24, pady=16)

    def _save(self):
        name = self._name.get().strip()
        if not name:
            self._toast("Le nom est obligatoire.", error=True)
            return
        try:
            self._db.rename_file_vault_folder(folder_id=self._folder_id, name=self._crypto.encrypt(name))
            self._on_save()
            self.destroy()
            self._toast("Dossier renomme.")
        except Exception as exc:
            self._toast(f"Erreur : {exc}", error=True)


class AddFileDialog(ctk.CTkToplevel):
    def __init__(self, parent, db, crypto, folder_id, on_save, toast):
        super().__init__(parent)
        apply_window_icon(self)
        self._db = db
        self._crypto = crypto
        self._folder_id = folder_id
        self._on_save = on_save
        self._toast = toast
        self._chosen_paths: list[str] = []
        self.title("Ajouter des fichiers")
        self.geometry("520x360")
        self.resizable(False, False)
        self.grab_set()
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Ajouter des fichiers", font=("Segoe UI", 16, "bold")).pack(pady=(20, 4))

        ctk.CTkLabel(self, text="Fichiers *", font=("Segoe UI", 12), text_color="#94a3b8").pack(anchor="w", padx=24, pady=(14, 2))

        file_row = ctk.CTkFrame(self, fg_color="transparent")
        file_row.pack(fill="x", padx=24)

        self._file_label = ctk.CTkLabel(file_row, text="Aucun fichier selectionne", font=("Segoe UI", 11), text_color="#94a3b8", anchor="w")
        self._file_label.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            file_row,
            text="Parcourir...",
            width=120,
            height=34,
            fg_color=("#e2e8f0", "#334155"),
            hover_color=("#cbd5e1", "#475569"),
            text_color=("#374151", "#e2e8f0"),
            corner_radius=8,
            command=self._pick_files,
        ).pack(side="right")

        ctk.CTkLabel(
            self,
            text="Le titre est deduit automatiquement du nom de chaque fichier.",
            font=("Segoe UI", 11),
            text_color="#94a3b8",
        ).pack(anchor="w", padx=24, pady=(8, 0))

        self._progress_label = ctk.CTkLabel(self, text="", font=("Segoe UI", 11), text_color="#4A9EFF")
        self._progress_label.pack(anchor="w", padx=24)

        self._progress_bar = ctk.CTkProgressBar(self, width=470, corner_radius=6)
        self._progress_bar.pack(padx=24, pady=(4, 0))
        self._progress_bar.set(0)
        self._progress_bar.pack_forget()

        self._save_btn = ctk.CTkButton(
            self,
            text="Enregistrer",
            height=42,
            font=("Segoe UI", 13, "bold"),
            fg_color="#4A9EFF",
            hover_color="#2563eb",
            corner_radius=10,
            command=self._save,
        )
        self._save_btn.pack(fill="x", padx=24, pady=20)

    def _pick_files(self):
        paths = list(filedialog.askopenfilenames(title="Choisir un ou plusieurs fichiers"))
        if paths:
            self._chosen_paths = paths
            count = len(paths)
            preview = os.path.basename(paths[0])
            txt = f"{count} fichier(s) selectionne(s) - ex: {preview}"
            self._file_label.configure(text=txt, text_color=("#374151", "#e2e8f0"))

    def _save(self):
        if not self._chosen_paths:
            self._toast("Veuillez selectionner au moins un fichier.", error=True)
            return

        self._save_btn.configure(state="disabled", text="Chiffrement en cours...")
        self._progress_bar.pack(padx=24, pady=(4, 0))
        self._progress_bar.set(0)

        total = len(self._chosen_paths)

        def worker():
            added = 0
            try:
                for i, path in enumerate(self._chosen_paths):
                    name = os.path.basename(path)
                    self.after(0, lambda n=name, idx=i: (
                        self._progress_label.configure(text=f"({idx + 1}/{total}) {n}"),
                        self._progress_bar.set((idx) / total),
                    ))

                    size = os.path.getsize(path)
                    with open(path, "rb") as fh:
                        plain_bytes = fh.read()

                    stored_name = secrets.token_hex(16) + ".bin"
                    target_path = os.path.join(FILE_VAULT_DIR, stored_name)
                    encrypted_bytes = self._crypto.encrypt_bytes(plain_bytes)

                    with open(target_path, "wb") as fh:
                        fh.write(encrypted_bytes)

                    original_name = os.path.basename(path)
                    title = os.path.splitext(original_name)[0] or original_name
                    self._db.add_file_vault_file(
                        folder_id=self._folder_id,
                        title=self._crypto.encrypt(title),
                        stored_name=stored_name,
                        original_name=self._crypto.encrypt(original_name),
                        size_bytes=size,
                    )
                    added += 1

                def on_done():
                    self._on_save()
                    self.destroy()
                    self._toast(f"{added} fichier(s) ajoutes au coffre.")

                self.after(0, on_done)

            except Exception as exc:
                def on_error(e=exc):
                    self._save_btn.configure(state="normal", text="Enregistrer")
                    self._progress_bar.pack_forget()
                    self._progress_label.configure(text="")
                    self._toast(f"Ajout impossible : {e}", error=True)
                self.after(0, on_error)

        threading.Thread(target=worker, daemon=True).start()


class FilePreviewDialog(ctk.CTkToplevel):
    def __init__(self, parent, filename: str, data: bytes, toast):
        super().__init__(parent)
        apply_window_icon(self)
        self._toast = toast
        self._filename = filename
        self._data = data
        self._img_ref = None
        self._pdf_doc = None
        self._pdf_page_index = 0
        self._temp_files: list[str] = []
        self.title(f"Previsualisation - {filename}")
        self.geometry("780x560")
        self.minsize(640, 420)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()

    def _on_close(self):
        for path in self._temp_files:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
        self.destroy()

    def _open_with_system(self):
        try:
            suffix = os.path.splitext(self._filename)[1] or ".bin"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix,
                                              prefix="dilopass_", dir=tempfile.gettempdir())
            tmp.write(self._data)
            tmp.close()
            self._temp_files.append(tmp.name)
            os.startfile(tmp.name)
        except Exception as exc:
            self._toast(f"Impossible d'ouvrir : {exc}", error=True)

    def _build(self):
        ext = os.path.splitext(self._filename.lower())[1]
        if ext == ".pdf":
            self._build_pdf_preview()
            return
        if ext in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}:
            self._build_image_preview()
            return
        if ext in {".txt", ".md", ".json", ".csv", ".py", ".log", ".xml", ".yaml", ".yml"}:
            self._build_text_preview()
            return
        self._build_fallback()

    def _build_image_preview(self):
        try:
            img = Image.open(BytesIO(self._data))
            img.thumbnail((720, 480))
            self._img_ref = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            frame = ctk.CTkFrame(self, fg_color="transparent")
            frame.pack(fill="both", expand=True, padx=20, pady=20)
            ctk.CTkLabel(frame, text=self._filename, font=("Segoe UI", 14, "bold")).pack(anchor="w")
            ctk.CTkLabel(frame, image=self._img_ref, text="").pack(expand=True, pady=12)
        except Exception as exc:
            self._toast(f"Impossible d'afficher l'image : {exc}", error=True)
            self.destroy()

    def _build_text_preview(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(frame, text=self._filename, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        box = ctk.CTkTextbox(frame, font=("Consolas", 12))
        box.pack(fill="both", expand=True, pady=(10, 0))
        content = self._data.decode("utf-8", errors="replace")
        if len(content) > 20000:
            content = content[:20000] + "\n\n[...] Apercu tronque"
        box.insert("1.0", content)
        box.configure(state="disabled")

    def _build_fallback(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(frame, text=self._filename, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        center = ctk.CTkFrame(frame, fg_color="transparent")
        center.pack(expand=True)
        ctk.CTkLabel(
            center,
            text="Apercu non disponible pour ce type de fichier.",
            font=("Segoe UI", 12),
            text_color="#94a3b8",
        ).pack(pady=(0, 16))
        ctk.CTkButton(
            center,
            text="Ouvrir avec l'application systeme",
            height=40,
            width=260,
            font=("Segoe UI", 13, "bold"),
            fg_color="#4A9EFF",
            hover_color="#2563eb",
            corner_radius=10,
            command=self._open_with_system,
        ).pack()

    def _build_pdf_preview(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(frame, text=self._filename, font=("Segoe UI", 14, "bold")).pack(anchor="w")

        if fitz is None:
            ctk.CTkLabel(
                frame,
                text="Apercu PDF indisponible. Installez PyMuPDF puis relancez l'app.",
                font=("Segoe UI", 12),
                text_color="#94a3b8",
            ).pack(expand=True)
            return

        try:
            self._pdf_doc = fitz.open(stream=self._data, filetype="pdf")
        except Exception as exc:
            ctk.CTkLabel(
                frame,
                text=f"Impossible de lire ce PDF: {exc}",
                font=("Segoe UI", 12),
                text_color="#ef4444",
            ).pack(expand=True)
            return

        controls = ctk.CTkFrame(frame, fg_color="transparent")
        controls.pack(fill="x", pady=(8, 8))
        self._pdf_info = ctk.CTkLabel(controls, text="", font=("Segoe UI", 12), text_color="#94a3b8")
        self._pdf_info.pack(side="left")
        ctk.CTkButton(controls, text="<", width=36, command=lambda: self._pdf_change(-1)).pack(side="right", padx=(4, 0))
        ctk.CTkButton(controls, text=">", width=36, command=lambda: self._pdf_change(1)).pack(side="right")

        self._pdf_image_label = ctk.CTkLabel(frame, text="")
        self._pdf_image_label.pack(fill="both", expand=True)
        self._pdf_render()

    def _pdf_change(self, delta: int):
        if self._pdf_doc is None:
            return
        new_index = self._pdf_page_index + delta
        if new_index < 0 or new_index >= len(self._pdf_doc):
            return
        self._pdf_page_index = new_index
        self._pdf_render()

    def _pdf_render(self):
        if self._pdf_doc is None:
            return
        page = self._pdf_doc[self._pdf_page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img.thumbnail((720, 460))
        self._img_ref = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
        self._pdf_image_label.configure(image=self._img_ref, text="")
        self._pdf_info.configure(text=f"Page {self._pdf_page_index + 1}/{len(self._pdf_doc)}")
