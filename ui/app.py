import time
import customtkinter as ctk
from core.crypto import CryptoManager
from core.database import DatabaseManager
from ui.login import LoginView
from ui.vault import VaultView
from ui.notes import NotesView
from ui.generator import GeneratorView
from ui.audit import AuditView
from ui.settings import SettingsView
from ui.filevault import FileVaultView
from ui.window_utils import apply_window_icon


NAV_ITEMS = [
    ("🏠", "Tableau de bord", "dashboard"),
    ("🔑", "Coffre-Fort",     "vault"),
    ("📁", "Coffre Fichiers", "filevault"),
    ("📝", "Notes",           "notes"),
    ("⚡", "Générateur",      "generator"),
    ("🛡", "Audit",           "audit"),
]

ACCENT = "#4A9EFF"


class DiloPassApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        apply_window_icon(self)
        self.title("DiloPass")
        self.geometry("1160x720")
        self.minsize(900, 600)
        self._db     = DatabaseManager()
        self._crypto = CryptoManager()
        self._active_view: str = "dashboard"
        self._views: dict = {}
        self._last_activity = time.time()
        self._auto_lock_after = 5 * 60  # seconds

        self._build_shell()
        self._show_login()

    # ── Shell (sidebar + content area) ───────────────────────────────────────

    def _build_shell(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ── Sidebar ───────────────────────────────────────────────────────
        self._sidebar = ctk.CTkFrame(self, width=200, corner_radius=0,
                                      fg_color=("#0f172a", "#020617"))
        self._sidebar.grid(row=0, column=0, sticky="ns")
        self._sidebar.grid_propagate(False)
        self._sidebar.rowconfigure(10, weight=1)

        # Logo
        logo_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        logo_frame.grid(row=0, column=0, pady=(24, 20), padx=16, sticky="ew")
        ctk.CTkLabel(logo_frame, text="🔐",
                     font=("Segoe UI", 28)).pack(side="left")
        ctk.CTkLabel(logo_frame, text="DiloPass",
                     font=("Segoe UI", 18, "bold"),
                     text_color=ACCENT).pack(side="left", padx=8)

        # Nav buttons
        self._nav_btns: dict[str, ctk.CTkButton] = {}
        for i, (icon, label, key) in enumerate(NAV_ITEMS, start=1):
            btn = ctk.CTkButton(
                self._sidebar,
                text=f"  {icon}  {label}",
                anchor="w", height=42,
                font=("Segoe UI", 13),
                fg_color="transparent",
                hover_color=("#1e293b", "#1e293b"),
                text_color=("#94a3b8", "#94a3b8"),
                corner_radius=10,
                command=lambda k=key: self._switch_view(k))
            btn.grid(row=i, column=0, padx=10, pady=2, sticky="ew")
            self._nav_btns[key] = btn

        # Spacer
        ctk.CTkFrame(self._sidebar, fg_color="transparent").grid(
            row=10, column=0, sticky="nsew")

        # Lock button
        ctk.CTkButton(
            self._sidebar, text="  🔒  Verrouiller", anchor="w",
            height=42, font=("Segoe UI", 13),
            fg_color="transparent",
            hover_color=("#1e293b", "#1e293b"),
            text_color=("#ef4444", "#ef4444"),
            corner_radius=10,
            command=self._lock).grid(row=11, column=0, padx=10,
                                     pady=(4, 4), sticky="ew")

        # Settings
        ctk.CTkButton(
            self._sidebar, text="  ⚙️  Paramètres", anchor="w",
            height=42, font=("Segoe UI", 13),
            fg_color="transparent",
            hover_color=("#1e293b", "#1e293b"),
            text_color=("#94a3b8", "#94a3b8"),
            corner_radius=10,
            command=lambda: self._switch_view("settings")).grid(
                row=12, column=0, padx=10, pady=(0, 20), sticky="ew")

        # ── Top bar ───────────────────────────────────────────────────────
        self._topbar = ctk.CTkFrame(self, height=56, corner_radius=0,
                                     fg_color=("#f1f5f9", "#0f172a"))
        self._topbar.grid(row=0, column=1, sticky="new")
        self._topbar.pack_propagate(False)
        self._topbar.columnconfigure(0, weight=1)

        self._page_title = ctk.CTkLabel(
            self._topbar, text="Tableau de bord",
            font=("Segoe UI", 15, "bold"))
        self._page_title.pack(side="left", padx=20)

        # Global search
        self._global_search = ctk.CTkEntry(
            self._topbar, placeholder_text="🔍  Recherche globale…",
            width=260, height=34, corner_radius=10)
        self._global_search.pack(side="right", padx=(8, 20))
        self._global_search.bind("<Return>", self._global_search_cb)

        # Toast label (in-app notifications)
        self._toast_label = ctk.CTkLabel(
            self._topbar, text="", font=("Segoe UI", 12),
            text_color="#22c55e")
        self._toast_label.pack(side="right", padx=8)

        # ── Main content ──────────────────────────────────────────────────
        self._content = ctk.CTkFrame(self, corner_radius=0,
                                      fg_color=("#f8fafc", "#0d1117"))
        self._content.grid(row=0, column=1, sticky="nsew",
                           pady=(56, 0))  # below topbar
        self._content.rowconfigure(0, weight=1)
        self._content.columnconfigure(0, weight=1)

        # ── Login overlay ─────────────────────────────────────────────────
        self._overlay = ctk.CTkFrame(self, corner_radius=0,
                                      fg_color=("#0f172a", "#020617"))
        self._overlay.grid(row=0, column=0, columnspan=2, sticky="nsew")

    # ── Login flow ────────────────────────────────────────────────────────────

    def _show_login(self):
        self._overlay.tkraise()
        # Clear previous login view if any
        for w in self._overlay.winfo_children():
            w.destroy()
        login = LoginView(self._overlay, self._db, self._crypto,
                          on_success=self._on_unlocked)
        login.pack(fill="both", expand=True)

    def _on_unlocked(self):
        """Called after successful login."""
        self._overlay.lower()
        self._load_views()
        self._switch_view("dashboard")
        self._start_activity_monitor()
        # Load auto-lock setting
        val = self._db.get_setting("auto_lock_min", "5")
        if val == "Jamais":
            self._auto_lock_after = None
        else:
            try:
                self._auto_lock_after = int(val) * 60
            except ValueError:
                self._auto_lock_after = 300

    def _lock(self):
        self._crypto.lock()
        # Destroy cached views so they get rebuilt on next unlock
        for v in self._views.values():
            v.destroy()
        self._views.clear()
        self._show_login()

    # ── Views ─────────────────────────────────────────────────────────────────

    def _load_views(self):
        self._views["dashboard"] = DashboardView(
            self._content, self._db, self._crypto, self._switch_view)
        self._views["vault"] = VaultView(
            self._content, self._db, self._crypto, self._show_toast)
        self._views["filevault"] = FileVaultView(
            self._content, self._db, self._crypto, self._show_toast)
        self._views["notes"] = NotesView(
            self._content, self._db, self._crypto, self._show_toast)
        self._views["generator"] = GeneratorView(
            self._content, self._show_toast)
        self._views["audit"] = AuditView(
            self._content, self._db, self._crypto, self._show_toast)
        self._views["settings"] = SettingsView(
            self._content, self._db, self._crypto, self._show_toast,
            self._on_theme_change)
        for v in self._views.values():
            v.grid(row=0, column=0, sticky="nsew")

    def _switch_view(self, key: str):
        self._last_activity = time.time()
        if key not in self._views:
            return
        self._active_view = key
        self._views[key].tkraise()
        # Refresh data views
        if key in ("vault", "notes", "audit", "filevault"):
            self._views[key].refresh() if hasattr(self._views[key], "refresh") else None

        titles = {k: lbl for _, lbl, k in NAV_ITEMS}
        titles["settings"] = "Paramètres"
        titles["filevault"] = "Coffre Fichiers"
        self._page_title.configure(text=titles.get(key, key.title()))

        # Update nav highlight
        for k, btn in self._nav_btns.items():
            if k == key:
                btn.configure(fg_color=("#1e3a5f", "#1e3a5f"),
                               text_color=("white", "white"))
            else:
                btn.configure(fg_color="transparent",
                               text_color=("#94a3b8", "#94a3b8"))

    # ── Toast notifications ───────────────────────────────────────────────────

    def _show_toast(self, msg: str, error: bool = False):
        color = "#ef4444" if error else "#22c55e"
        self._toast_label.configure(text=msg, text_color=color)
        self.after(3000, lambda: self._toast_label.configure(text=""))

    # ── Global search ─────────────────────────────────────────────────────────

    def _global_search_cb(self, _=None):
        q = self._global_search.get().strip()
        if not q:
            return
        self._switch_view("vault")
        v = self._views.get("vault")
        if v and hasattr(v, "_search"):
            v._search.delete(0, "end")
            v._search.insert(0, q)
            v._on_search()
        self._global_search.delete(0, "end")

    # ── Auto-lock ─────────────────────────────────────────────────────────────

    def _start_activity_monitor(self):
        self.bind_all("<Motion>",     self._reset_activity)
        self.bind_all("<KeyPress>",   self._reset_activity)
        self.bind_all("<Button>",     self._reset_activity)
        self._check_lock()

    def _reset_activity(self, _=None):
        self._last_activity = time.time()

    def _check_lock(self):
        if self._crypto.is_unlocked and self._auto_lock_after is not None:
            idle = time.time() - self._last_activity
            if idle >= self._auto_lock_after:
                self._show_toast("Verrouillage automatique.", error=True)
                self._lock()
                return
        self.after(10_000, self._check_lock)

    def _on_theme_change(self, _=None):
        pass  # theme applied directly


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardView(ctk.CTkFrame):
    def __init__(self, parent, db, crypto, switch_view):
        super().__init__(parent, fg_color="transparent")
        self._db = db
        self._crypto = crypto
        self._switch = switch_view
        self._build()

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(24, 16))
        ctk.CTkLabel(hdr, text="Bonjour 👋",
                     font=("Segoe UI", 26, "bold")).pack(anchor="w")
        ctk.CTkLabel(hdr, text="Voici l'état de votre coffre-fort.",
                     font=("Segoe UI", 13), text_color="#94a3b8").pack(anchor="w")

        # Stat cards
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", padx=24, pady=(0, 20))
        s = self._db.stats()
        self._stat_card(stats_frame, "🔑", str(s["vault"]),  "Mots de passe", "#4A9EFF",
                        lambda: self._switch("vault"))
        self._stat_card(stats_frame, "📁", str(s["files"]),  "Fichiers chiffrés", "#a855f7",
                        lambda: self._switch("filevault"))
        self._stat_card(stats_frame, "📝", str(s["notes"]),  "Notes sécurisées", "#22c55e",
                        lambda: self._switch("notes"))
        self._stat_card(stats_frame, "★",  str(s["favorites"]), "Favoris", "#eab308",
                        lambda: self._switch("vault"))

        # Quick actions
        ctk.CTkLabel(self, text="Actions rapides",
                     font=("Segoe UI", 15, "bold")).pack(
                         anchor="w", padx=24, pady=(0, 8))
        acts = ctk.CTkFrame(self, fg_color="transparent")
        acts.pack(fill="x", padx=24)
        self._quick_btn(acts, "➕  Nouveau mot de passe", "#4A9EFF", "#2563eb",
                        lambda: self._switch("vault"))
        self._quick_btn(acts, "📁  Coffre fichiers", "#a855f7", "#7c3aed",
                        lambda: self._switch("filevault"))
        self._quick_btn(acts, "📝  Nouvelle note", "#22c55e", "#16a34a",
                        lambda: self._switch("notes"))
        self._quick_btn(acts, "⚡  Générer un mot de passe", "#6366f1", "#4338ca",
                        lambda: self._switch("generator"))
        self._quick_btn(acts, "🛡  Lancer l'audit", "#f97316", "#ea580c",
                        lambda: self._switch("audit"))

        # Security tip
        tips = [
            "Utilisez un mot de passe unique pour chaque compte.",
            "Activez l'authentification à deux facteurs quand c'est possible.",
            "Ne partagez jamais votre mot de passe maître.",
            "Mettez à jour vos mots de passe importants tous les 90 jours.",
            "Utilisez des mots de passe d'au moins 16 caractères.",
        ]
        import random
        tip = random.choice(tips)
        tip_card = ctk.CTkFrame(self, corner_radius=14,
                                fg_color=("#eff6ff", "#1e3a5f"),
                                border_color="#4A9EFF", border_width=1)
        tip_card.pack(fill="x", padx=24, pady=20)
        ctk.CTkLabel(tip_card, text="💡  Conseil du jour",
                     font=("Segoe UI", 12, "bold"),
                     text_color=ACCENT).pack(anchor="w", padx=16, pady=(10, 2))
        ctk.CTkLabel(tip_card, text=tip, font=("Segoe UI", 12),
                     text_color=("#374151", "#cbd5e1"),
                     wraplength=700, justify="left").pack(
                         anchor="w", padx=16, pady=(0, 12))

    def _stat_card(self, parent, icon, value, label, color, cmd):
        card = ctk.CTkFrame(parent, corner_radius=14,
                            fg_color=("#f8fafc", "#1e293b"),
                            cursor="hand2")
        card.pack(side="left", padx=6, expand=True, fill="x")
        card.bind("<Button-1>", lambda _: cmd())
        ctk.CTkLabel(card, text=icon, font=("Segoe UI", 28)).pack(pady=(16, 0))
        ctk.CTkLabel(card, text=value,
                     font=("Segoe UI", 32, "bold"),
                     text_color=color).pack()
        ctk.CTkLabel(card, text=label, font=("Segoe UI", 11),
                     text_color="#94a3b8").pack(pady=(0, 16))

    def _quick_btn(self, parent, text, fg, hover, cmd):
        ctk.CTkButton(parent, text=text, height=44,
                      font=("Segoe UI", 13, "bold"),
                      fg_color=fg, hover_color=hover,
                      corner_radius=12,
                      command=cmd).pack(side="left", padx=6,
                                        expand=True, fill="x")
