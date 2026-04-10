import customtkinter as ctk
import pyperclip
from core.crypto import CryptoManager


class GeneratorView(ctk.CTkFrame):
    def __init__(self, parent, show_toast):
        super().__init__(parent, fg_color="transparent")
        self._toast = show_toast
        self._history: list[str] = []
        self._build()
        self._generate()

    def _build(self):
        ctk.CTkLabel(self, text="Générateur de Mots de Passe",
                     font=("Segoe UI", 22, "bold")).pack(
                         anchor="w", padx=20, pady=(16, 16))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)

        # ── Left panel ────────────────────────────────────────────────────
        left = ctk.CTkFrame(body, corner_radius=16,
                            fg_color=("#f8fafc", "#1e293b"))
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        ctk.CTkLabel(left, text="Mot de passe généré",
                     font=("Segoe UI", 12), text_color="#94a3b8").pack(
                         anchor="w", padx=20, pady=(20, 4))

        # Password display
        pw_frame = ctk.CTkFrame(left, corner_radius=10,
                                 fg_color=("#0f172a", "#0f172a"))
        pw_frame.pack(fill="x", padx=20, pady=4)
        self._pw_label = ctk.CTkLabel(
            pw_frame, text="",
            font=("Courier New", 20, "bold"),
            text_color="#4A9EFF",
            wraplength=380)
        self._pw_label.pack(padx=16, pady=16)

        # Strength bar
        str_row = ctk.CTkFrame(left, fg_color="transparent")
        str_row.pack(fill="x", padx=20, pady=(4, 2))
        self._str_lbl = ctk.CTkLabel(str_row, text="",
                                      font=("Segoe UI", 12))
        self._str_lbl.pack(side="left")
        self._entropy_lbl = ctk.CTkLabel(str_row, text="",
                                          font=("Segoe UI", 11),
                                          text_color="#6b7280")
        self._entropy_lbl.pack(side="right")
        self._str_bar = ctk.CTkProgressBar(left, height=8, corner_radius=4)
        self._str_bar.set(0)
        self._str_bar.pack(fill="x", padx=20, pady=(0, 12))

        # Buttons
        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkButton(btn_row, text="⚡ Régénérer", height=40,
                      font=("Segoe UI", 13, "bold"),
                      fg_color="#4A9EFF", hover_color="#2563eb",
                      corner_radius=10,
                      command=self._generate).pack(side="left",
                                                    expand=True, fill="x",
                                                    padx=(0, 6))
        ctk.CTkButton(btn_row, text="📋 Copier", height=40,
                      font=("Segoe UI", 13, "bold"),
                      fg_color=("#e2e8f0", "#334155"),
                      hover_color=("#cbd5e1", "#475569"),
                      text_color=("#374151", "#e2e8f0"),
                      corner_radius=10,
                      command=self._copy).pack(side="left",
                                               expand=True, fill="x",
                                               padx=(6, 0))

        # ── Options ───────────────────────────────────────────────────────
        ctk.CTkLabel(left, text="Options",
                     font=("Segoe UI", 13, "bold")).pack(
                         anchor="w", padx=20, pady=(8, 4))

        # Tabs: Password / Passphrase
        self._mode = ctk.CTkSegmentedButton(
            left,
            values=["Mot de passe", "Phrase secrète"],
            command=self._switch_mode)
        self._mode.set("Mot de passe")
        self._mode.pack(fill="x", padx=20, pady=(0, 12))

        # Password options frame
        self._pw_opts = ctk.CTkFrame(left, fg_color="transparent")
        self._pw_opts.pack(fill="x", padx=20)

        # Length slider
        len_row = ctk.CTkFrame(self._pw_opts, fg_color="transparent")
        len_row.pack(fill="x", pady=4)
        ctk.CTkLabel(len_row, text="Longueur :",
                     font=("Segoe UI", 12)).pack(side="left")
        self._len_lbl = ctk.CTkLabel(len_row, text="16",
                                      font=("Segoe UI", 12, "bold"),
                                      text_color="#4A9EFF", width=30)
        self._len_lbl.pack(side="right")
        self._len_slider = ctk.CTkSlider(self._pw_opts, from_=4, to=64,
                                          number_of_steps=60,
                                          command=self._upd_len)
        self._len_slider.set(16)
        self._len_slider.pack(fill="x", pady=2)

        # Character options
        self._upper   = self._checkbox(self._pw_opts, "Majuscules (A-Z)", True)
        self._lower   = self._checkbox(self._pw_opts, "Minuscules (a-z)", True)
        self._digits  = self._checkbox(self._pw_opts, "Chiffres (0-9)", True)
        self._symbols = self._checkbox(self._pw_opts, "Symboles (!@#...)", True)
        self._no_sim  = self._checkbox(self._pw_opts, "Exclure caractères similaires (Il1O0)", False)

        # Passphrase options frame (hidden initially)
        self._pp_opts = ctk.CTkFrame(left, fg_color="transparent")

        wrd_row = ctk.CTkFrame(self._pp_opts, fg_color="transparent")
        wrd_row.pack(fill="x", pady=4)
        ctk.CTkLabel(wrd_row, text="Nombre de mots :",
                     font=("Segoe UI", 12)).pack(side="left")
        self._word_lbl = ctk.CTkLabel(wrd_row, text="4",
                                       font=("Segoe UI", 12, "bold"),
                                       text_color="#4A9EFF", width=30)
        self._word_lbl.pack(side="right")
        self._word_slider = ctk.CTkSlider(self._pp_opts, from_=3, to=8,
                                           number_of_steps=5,
                                           command=self._upd_words)
        self._word_slider.set(4)
        self._word_slider.pack(fill="x", pady=2)

        # ── Right panel: history ──────────────────────────────────────────
        right = ctk.CTkFrame(body, corner_radius=16,
                             fg_color=("#f8fafc", "#1e293b"))
        right.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(right, text="Historique",
                     font=("Segoe UI", 14, "bold")).pack(
                         anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(right, text="10 derniers générés",
                     font=("Segoe UI", 11), text_color="#6b7280").pack(
                         anchor="w", padx=16, pady=(0, 8))

        self._hist_frame = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self._hist_frame.pack(fill="both", expand=True, padx=8, pady=(0, 16))

    def _checkbox(self, parent, text, default):
        var = ctk.BooleanVar(value=default)
        ctk.CTkCheckBox(parent, text=text, variable=var,
                        font=("Segoe UI", 12),
                        command=self._generate).pack(anchor="w", pady=2)
        return var

    def _upd_len(self, val):
        self._len_lbl.configure(text=str(int(val)))
        self._generate()

    def _upd_words(self, val):
        self._word_lbl.configure(text=str(int(val)))
        self._generate()

    def _switch_mode(self, mode):
        if mode == "Mot de passe":
            self._pp_opts.pack_forget()
            self._pw_opts.pack(fill="x", padx=20)
        else:
            self._pw_opts.pack_forget()
            self._pp_opts.pack(fill="x", padx=20)
        self._generate()

    def _generate(self, _=None):
        mode = self._mode.get()
        if mode == "Phrase secrète":
            pw = CryptoManager.generate_passphrase(int(self._word_slider.get()))
        else:
            pw = CryptoManager.generate(
                length         = int(self._len_slider.get()),
                upper          = self._upper.get(),
                lower          = self._lower.get(),
                digits         = self._digits.get(),
                symbols        = self._symbols.get(),
                exclude_similar= self._no_sim.get(),
            )
        self._current_pw = pw
        self._pw_label.configure(text=pw)
        sc, lb, col = CryptoManager.strength(pw)
        self._str_lbl.configure(text=f"Force : {lb}", text_color=col)
        self._str_bar.configure(progress_color=col)
        self._str_bar.set(sc / 100)
        # Entropy estimate
        import math
        charset = 0
        if any(c.isupper() for c in pw): charset += 26
        if any(c.islower() for c in pw): charset += 26
        if any(c.isdigit() for c in pw): charset += 10
        if any(not c.isalnum() for c in pw): charset += 32
        if charset:
            bits = len(pw) * math.log2(charset)
            self._entropy_lbl.configure(text=f"~{bits:.0f} bits d'entropie")
        # Add to history
        self._history.insert(0, pw)
        self._history = self._history[:10]
        self._refresh_history()

    def _refresh_history(self):
        for w in self._hist_frame.winfo_children():
            w.destroy()
        for pw in self._history:
            row = ctk.CTkFrame(self._hist_frame, corner_radius=8,
                               fg_color=("#e2e8f0", "#0f172a"))
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=pw, font=("Courier New", 10),
                         text_color="#4A9EFF",
                         wraplength=160).pack(side="left", padx=8, pady=6)
            ctk.CTkButton(row, text="📋", width=28, height=24,
                          fg_color="transparent", hover_color=("#cbd5e1","#334155"),
                          font=("Segoe UI", 12),
                          command=lambda p=pw: self._copy_hist(p)).pack(
                              side="right", padx=4)

    def _copy(self):
        pyperclip.copy(self._current_pw)
        self._toast("Mot de passe copié !")
        self.after(30_000, lambda: pyperclip.copy(""))

    def _copy_hist(self, pw):
        pyperclip.copy(pw)
        self._toast("Copié !")
        self.after(30_000, lambda: pyperclip.copy(""))
