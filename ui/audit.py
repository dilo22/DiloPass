import time
import customtkinter as ctk
from core.crypto import CryptoManager
from core.database import DatabaseManager


class AuditView(ctk.CTkFrame):
    def __init__(self, parent, db: DatabaseManager, crypto: CryptoManager,
                 show_toast):
        super().__init__(parent, fg_color="transparent")
        self._db = db
        self._crypto = crypto
        self._toast = show_toast
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Audit de Sécurité",
                     font=("Segoe UI", 22, "bold")).pack(
                         anchor="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(self,
                     text="Identifiez les failles dans votre coffre-fort",
                     font=("Segoe UI", 12), text_color="#94a3b8").pack(
                         anchor="w", padx=20, pady=(0, 12))

        ctk.CTkButton(self, text="⟳ Analyser maintenant",
                      width=200, height=38,
                      font=("Segoe UI", 13, "bold"),
                      fg_color="#4A9EFF", hover_color="#2563eb",
                      corner_radius=10,
                      command=self._run_audit).pack(anchor="w", padx=20,
                                                     pady=(0, 16))

        # Score card
        self._score_frame = ctk.CTkFrame(self, corner_radius=16,
                                          fg_color=("#f8fafc", "#1e293b"))
        self._score_frame.pack(fill="x", padx=20, pady=(0, 12))

        # Issues
        self._scroll = ctk.CTkScrollableFrame(self, corner_radius=16,
                                               fg_color=("#f8fafc","#1e293b"))
        self._scroll.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        ctk.CTkLabel(self._scroll,
                     text="Cliquez sur 'Analyser' pour démarrer l'audit.",
                     font=("Segoe UI", 13), text_color="#94a3b8").pack(pady=40)

    def _run_audit(self):
        # Clear
        for w in self._score_frame.winfo_children():
            w.destroy()
        for w in self._scroll.winfo_children():
            w.destroy()

        rows = self._db.get_all_vault()
        entries = []
        for r in rows:
            try:
                title = self._crypto.dec(r["title"])
                pw    = self._crypto.dec(r["password"])
                entries.append((r, title, pw))
            except Exception:
                continue

        total   = len(entries)
        weak    = []
        dupes   = {}
        old     = []
        now     = time.time()
        ago_90  = now - 90 * 86400

        for r, title, pw in entries:
            sc, lb, _ = CryptoManager.strength(pw)
            if sc < 40:
                weak.append((r, title, pw, lb))
            dupes.setdefault(pw, []).append((r, title))
            if r["updated_at"] and r["updated_at"] < ago_90:
                old.append((r, title))

        dup_groups = [(pw, items) for pw, items in dupes.items()
                      if len(items) > 1]
        dup_count  = sum(len(items) for _, items in dup_groups)

        issues = len(weak) + dup_count + len(old)
        score  = max(0, 100 - issues * 10) if total else 100

        # Score row
        sc_row = ctk.CTkFrame(self._score_frame, fg_color="transparent")
        sc_row.pack(fill="x", padx=20, pady=16)

        color = "#22c55e" if score >= 80 else "#eab308" if score >= 50 else "#ef4444"
        ctk.CTkLabel(sc_row, text=f"{score}",
                     font=("Segoe UI", 48, "bold"),
                     text_color=color).pack(side="left")
        ctk.CTkLabel(sc_row, text="/100\nScore de sécurité",
                     font=("Segoe UI", 13), text_color="#94a3b8",
                     justify="left").pack(side="left", padx=8)

        # Stat cards
        stats = [
            (len(weak),    "Faibles",    "#ef4444"),
            (dup_count,    "Doublons",   "#f97316"),
            (len(old),     "Anciens",    "#eab308"),
            (total,        "Total",      "#4A9EFF"),
        ]
        stat_frame = ctk.CTkFrame(sc_row, fg_color="transparent")
        stat_frame.pack(side="right", padx=20)
        for val, lbl, col in stats:
            c = ctk.CTkFrame(stat_frame, corner_radius=10,
                             fg_color=("#e2e8f0", "#0f172a"))
            c.pack(side="left", padx=4)
            ctk.CTkLabel(c, text=str(val), font=("Segoe UI", 20, "bold"),
                         text_color=col).pack(padx=12, pady=(8, 0))
            ctk.CTkLabel(c, text=lbl, font=("Segoe UI", 10),
                         text_color="#94a3b8").pack(padx=12, pady=(0, 8))

        # Issues list
        if not issues:
            ctk.CTkLabel(self._scroll,
                         text="✅  Aucun problème détecté — excellent !",
                         font=("Segoe UI", 14), text_color="#22c55e").pack(pady=40)
            return

        self._section(self._scroll, f"Mots de passe faibles ({len(weak)})",
                      "#ef4444")
        for r, title, pw, lb in weak:
            self._issue_row(self._scroll, "⚠", title, lb, "#ef4444")

        if dup_groups:
            self._section(self._scroll, f"Mots de passe dupliqués ({dup_count})",
                          "#f97316")
            for _, items in dup_groups:
                names = ", ".join(t for _, t in items)
                self._issue_row(self._scroll, "♻", names,
                                "Même mot de passe", "#f97316")

        if old:
            self._section(self._scroll, f"Mots de passe anciens (>90j) ({len(old)})",
                          "#eab308")
            for r, title in old:
                days = int((time.time() - r["updated_at"]) / 86400)
                self._issue_row(self._scroll, "🕐", title,
                                f"Non modifié depuis {days}j", "#eab308")

    def _section(self, parent, text, color):
        ctk.CTkLabel(parent, text=text, font=("Segoe UI", 13, "bold"),
                     text_color=color).pack(anchor="w", padx=16, pady=(12, 4))

    def _issue_row(self, parent, icon, title, detail, color):
        row = ctk.CTkFrame(parent, corner_radius=8,
                           fg_color=("#e2e8f0", "#0f172a"),
                           border_color=color, border_width=1)
        row.pack(fill="x", padx=12, pady=3)
        ctk.CTkLabel(row, text=icon, font=("Segoe UI", 16),
                     text_color=color).pack(side="left", padx=12, pady=8)
        ctk.CTkLabel(row, text=title, font=("Segoe UI", 12, "bold")).pack(
            side="left")
        ctk.CTkLabel(row, text=f"  {detail}", font=("Segoe UI", 11),
                     text_color="#94a3b8").pack(side="left")
