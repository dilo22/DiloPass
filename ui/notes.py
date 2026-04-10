import time
import customtkinter as ctk
from core.crypto import CryptoManager
from core.database import DatabaseManager, SecureNote

NOTE_COLORS = ["#4A9EFF", "#22c55e", "#f97316", "#a855f7",
               "#ef4444", "#eab308", "#06b6d4", "#ec4899"]


class NotesView(ctk.CTkFrame):
    def __init__(self, parent, db: DatabaseManager, crypto: CryptoManager,
                 show_toast):
        super().__init__(parent, fg_color="transparent")
        self._db = db
        self._crypto = crypto
        self._toast = show_toast
        self._build()
        self.refresh()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(16, 8))
        ctk.CTkLabel(top, text="Notes Sécurisées",
                     font=("Segoe UI", 22, "bold")).pack(side="left")
        ctk.CTkButton(top, text="+ Nouvelle note", width=150, height=36,
                      font=("Segoe UI", 13, "bold"),
                      fg_color="#22c55e", hover_color="#16a34a",
                      corner_radius=10,
                      command=self._open_add).pack(side="right")

        self._search = ctk.CTkEntry(top, placeholder_text="🔍  Rechercher…",
                                    width=220, height=36, corner_radius=10)
        self._search.pack(side="right", padx=8)
        self._search.bind("<KeyRelease>", lambda _: self.refresh())

        self._scroll = ctk.CTkScrollableFrame(self, corner_radius=0,
                                               fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=20, pady=8)

    def refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        q = self._search.get().lower() if hasattr(self, "_search") else ""
        rows = self._db.get_all_notes()
        entries = []
        for r in rows:
            try:
                title   = self._crypto.dec(r["title"])
                content = self._crypto.dec(r["content"])
                if q and q not in title.lower() and q not in content.lower():
                    continue
                entries.append((r, title, content))
            except Exception:
                continue

        if not entries:
            ctk.CTkLabel(self._scroll,
                         text="Aucune note. Créez-en une !",
                         font=("Segoe UI", 14), text_color="#94a3b8").pack(
                             pady=60)
            return

        frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        frame.pack(fill="both", expand=True)
        for col in range(3):
            frame.columnconfigure(col, weight=1)

        for idx, (r, title, content) in enumerate(entries):
            self._make_card(frame, r, title, content,
                            row_n=idx // 3, col=idx % 3)

    def _make_card(self, parent, row, title, content, row_n, col):
        color = row["color"]
        card = ctk.CTkFrame(parent, corner_radius=14,
                            fg_color=("#f8fafc", "#1e293b"),
                            border_color=color, border_width=2)
        card.grid(row=row_n, column=col, padx=6, pady=6, sticky="ew")

        # color strip
        strip = ctk.CTkFrame(card, height=6, corner_radius=0,
                              fg_color=color)
        strip.pack(fill="x")

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(hdr, text=title,
                     font=("Segoe UI", 13, "bold"),
                     wraplength=170, anchor="w").pack(side="left")
        if row["is_favorite"]:
            ctk.CTkLabel(hdr, text="★", text_color="#eab308",
                         font=("Segoe UI", 14)).pack(side="right")

        # preview (first 100 chars)
        preview = content[:100] + ("…" if len(content) > 100 else "")
        ctk.CTkLabel(card, text=preview, font=("Segoe UI", 11),
                     text_color="#94a3b8", wraplength=180,
                     justify="left").pack(padx=12, pady=4, anchor="w")

        # date
        ts = time.strftime("%d/%m/%Y", time.localtime(row["updated_at"]))
        ctk.CTkLabel(card, text=ts, font=("Segoe UI", 9),
                     text_color="#6b7280").pack(padx=12, anchor="w")

        acts = ctk.CTkFrame(card, fg_color="transparent")
        acts.pack(fill="x", padx=10, pady=(4, 10))
        ctk.CTkButton(acts, text="✏️ Modifier", width=90, height=28,
                      fg_color=("#e2e8f0", "#334155"),
                      hover_color=("#cbd5e1", "#475569"),
                      corner_radius=8, font=("Segoe UI", 11),
                      command=lambda r=row: self._open_edit(r)).pack(
                          side="left", padx=2)
        ctk.CTkButton(acts, text="🗑", width=36, height=28,
                      fg_color=("#fee2e2", "#3b1515"),
                      hover_color=("#fecaca", "#5a1f1f"),
                      text_color="#ef4444", corner_radius=8,
                      command=lambda r=row: self._delete(r)).pack(
                          side="right", padx=2)

    def _delete(self, row):
        title = self._crypto.dec(row["title"])
        dlg = ctk.CTkToplevel(self)
        dlg.title("Supprimer la note")
        dlg.geometry("360x140")
        dlg.grab_set()
        ctk.CTkLabel(dlg, text=f"Supprimer « {title} » ?",
                     font=("Segoe UI", 13)).pack(pady=20)
        brow = ctk.CTkFrame(dlg, fg_color="transparent")
        brow.pack()
        ctk.CTkButton(brow, text="Annuler", width=110,
                      fg_color=("#e2e8f0", "#334155"),
                      command=dlg.destroy).pack(side="left", padx=8)
        ctk.CTkButton(brow, text="Supprimer", width=110,
                      fg_color="#ef4444", hover_color="#dc2626",
                      command=lambda: [self._db.delete_note(row["id"]),
                                       dlg.destroy(), self.refresh(),
                                       self._toast("Note supprimée.")]).pack(
                                           side="left")

    def _open_add(self):
        NoteDialog(self, self._db, self._crypto, None, self.refresh,
                   self._toast)

    def _open_edit(self, row):
        NoteDialog(self, self._db, self._crypto, row, self.refresh,
                   self._toast)


class NoteDialog(ctk.CTkToplevel):
    def __init__(self, parent, db, crypto, row, on_save, toast):
        super().__init__(parent)
        self._db = db
        self._crypto = crypto
        self._row = row
        self._on_save = on_save
        self._toast = toast
        self.title("Modifier la note" if row else "Nouvelle note")
        self.geometry("540x520")
        self.grab_set()
        self._selected_color = row["color"] if row else NOTE_COLORS[0]
        self._build()
        if row:
            self._populate()

    def _build(self):
        ctk.CTkLabel(self, text="Nouvelle note" if not self._row else "Modifier",
                     font=("Segoe UI", 16, "bold")).pack(pady=(20, 8))

        ctk.CTkLabel(self, text="Titre", font=("Segoe UI", 12),
                     text_color="#94a3b8").pack(anchor="w", padx=24)
        self._title = ctk.CTkEntry(self, height=38, corner_radius=8,
                                    font=("Segoe UI", 13))
        self._title.pack(fill="x", padx=24, pady=(2, 8))

        ctk.CTkLabel(self, text="Contenu", font=("Segoe UI", 12),
                     text_color="#94a3b8").pack(anchor="w", padx=24)
        self._content = ctk.CTkTextbox(self, height=200, corner_radius=8,
                                        font=("Segoe UI", 13))
        self._content.pack(fill="x", padx=24, pady=(2, 8))

        ctk.CTkLabel(self, text="Couleur", font=("Segoe UI", 12),
                     text_color="#94a3b8").pack(anchor="w", padx=24)
        color_row = ctk.CTkFrame(self, fg_color="transparent")
        color_row.pack(anchor="w", padx=24, pady=(2, 12))
        self._color_btns = []
        for c in NOTE_COLORS:
            btn = ctk.CTkButton(
                color_row, text="", width=28, height=28,
                corner_radius=14, fg_color=c,
                hover_color=c,
                border_width=3,
                border_color="white" if c == self._selected_color else c,
                command=lambda col=c: self._pick_color(col))
            btn.pack(side="left", padx=3)
            self._color_btns.append((c, btn))

        self._fav = ctk.CTkCheckBox(self, text="Favori ★",
                                    font=("Segoe UI", 12))
        self._fav.pack(anchor="w", padx=24, pady=4)

        ctk.CTkButton(self, text="Enregistrer", height=44,
                      font=("Segoe UI", 14, "bold"),
                      fg_color="#22c55e", hover_color="#16a34a",
                      corner_radius=10,
                      command=self._save).pack(fill="x", padx=24,
                                               pady=(8, 24))

    def _pick_color(self, color: str):
        self._selected_color = color
        for c, btn in self._color_btns:
            btn.configure(border_color="white" if c == color else c)

    def _populate(self):
        r = self._row
        c = self._crypto
        self._title.insert(0, c.dec(r["title"]))
        self._content.insert("1.0", c.dec(r["content"]))
        if r["is_favorite"]:
            self._fav.select()

    def _save(self):
        title   = self._title.get().strip()
        content = self._content.get("1.0", "end").strip()
        if not title:
            self._toast("Le titre est obligatoire.", error=True)
            return
        c = self._crypto
        note = SecureNote(
            title       = c.encrypt(title),
            content     = c.encrypt(content) if content else c.encrypt(""),
            color       = self._selected_color,
            is_favorite = bool(self._fav.get()),
        )
        if self._row:
            note.id         = self._row["id"]
            note.created_at = self._row["created_at"]
            self._db.update_note(note)
        else:
            self._db.add_note(note)
        self._on_save()
        self._toast("Note enregistrée ✓")
        self.destroy()
