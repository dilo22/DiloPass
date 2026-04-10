import os
import base64
import secrets
import string
import re
import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CryptoManager:
    ITERATIONS = 260_000

    def __init__(self):
        self._fernet: Fernet | None = None

    # ── Key management ────────────────────────────────────────────────────────

    def derive_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                         salt=salt, iterations=self.ITERATIONS)
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def unlock(self, password: str, salt: bytes) -> None:
        self._raw_key = self.derive_key(password, salt)
        self._fernet = Fernet(self._raw_key)

    def unlock_with_raw_key(self, raw_key: bytes) -> None:
        self._raw_key = raw_key
        self._fernet = Fernet(raw_key)

    def lock(self) -> None:
        self._fernet = None
        self._raw_key: bytes | None = None

    @property
    def raw_key(self) -> bytes | None:
        return getattr(self, "_raw_key", None)

    @property
    def is_unlocked(self) -> bool:
        return self._fernet is not None

    # ── Encrypt / Decrypt ─────────────────────────────────────────────────────

    def encrypt(self, text: str) -> bytes:
        if not self._fernet:
            raise RuntimeError("Vault is locked")
        return self._fernet.encrypt(text.encode())

    def encrypt_bytes(self, data: bytes) -> bytes:
        if not self._fernet:
            raise RuntimeError("Vault is locked")
        return self._fernet.encrypt(data)

    def decrypt(self, data: bytes) -> str:
        if not self._fernet:
            raise RuntimeError("Vault is locked")
        try:
            return self._fernet.decrypt(data).decode()
        except InvalidToken:
            raise ValueError("Decryption failed")

    def decrypt_bytes(self, data: bytes) -> bytes:
        if not self._fernet:
            raise RuntimeError("Vault is locked")
        try:
            return self._fernet.decrypt(data)
        except InvalidToken:
            raise ValueError("Decryption failed")

    def enc(self, text: str | None) -> bytes | None:
        return self.encrypt(text) if text else None

    def dec(self, data: bytes | None) -> str:
        return self.decrypt(data) if data else ""

    # ── Master password ───────────────────────────────────────────────────────

    @staticmethod
    def hash_master(password: str) -> bytes:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))

    @staticmethod
    def verify_master(password: str, hashed: bytes) -> bool:
        return bcrypt.checkpw(password.encode(), hashed)

    @staticmethod
    def new_salt() -> bytes:
        return os.urandom(32)

    @staticmethod
    def derive_recovery_key(answer1: str, answer2: str, salt: bytes) -> bytes:
        combined = (answer1.lower().strip() + "|" + answer2.lower().strip()).encode()
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                         salt=salt, iterations=100_000)
        return base64.urlsafe_b64encode(kdf.derive(combined))

    @staticmethod
    def encrypt_with_key(data: bytes, key: bytes) -> bytes:
        return Fernet(key).encrypt(data)

    @staticmethod
    def decrypt_with_key(encrypted: bytes, key: bytes) -> bytes:
        return Fernet(key).decrypt(encrypted)

    # ── Password generator ────────────────────────────────────────────────────

    @staticmethod
    def generate(length=16, upper=True, lower=True, digits=True,
                 symbols=True, exclude_similar=False) -> str:
        pools = []
        required = []

        def add(pool, excl=""):
            p = "".join(c for c in pool if c not in excl)
            pools.append(p)
            required.append(secrets.choice(p))

        sim = "Il1O0" if exclude_similar else ""
        if upper:   add(string.ascii_uppercase, sim)
        if lower:   add(string.ascii_lowercase, sim)
        if digits:  add(string.digits, sim)
        if symbols: add("!@#$%^&*()_+-=[]{}|;:,.<>?")

        if not pools:
            pools = [string.ascii_letters + string.digits]
            required = [secrets.choice(pools[0])]

        all_chars = "".join(pools)
        while len(required) < length:
            required.append(secrets.choice(all_chars))
        secrets.SystemRandom().shuffle(required)
        return "".join(required)

    @staticmethod
    def generate_passphrase(words=4) -> str:
        wordlist = [
            "correct","horse","battery","staple","cloud","ocean","river",
            "mountain","forest","desert","tiger","eagle","falcon","dragon",
            "crystal","silver","golden","shadow","thunder","storm","brave",
            "swift","noble","cosmic","lunar","solar","frozen","blazing",
            "ancient","mystic","cyber","neon","quantum","phantom","vortex"
        ]
        chosen = [secrets.choice(wordlist) for _ in range(words)]
        sep = secrets.choice(["-", "_", ".", "#"])
        num = str(secrets.randbelow(99))
        return sep.join(chosen) + num

    # ── Strength ──────────────────────────────────────────────────────────────

    @staticmethod
    def strength(password: str) -> tuple[int, str, str]:
        """Returns (score 0-100, label, color)"""
        if not password:
            return 0, "—", "#6b7280"
        s = 0
        ln = len(password)
        if ln >= 8:  s += 10
        if ln >= 12: s += 10
        if ln >= 16: s += 10
        if ln >= 20: s += 10
        if re.search(r'[A-Z]', password): s += 10
        if re.search(r'[a-z]', password): s += 10
        if re.search(r'\d',    password): s += 10
        if re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password): s += 20
        unique = len(set(password))
        if unique > 8:  s += 5
        if unique > 12: s += 5
        if re.search(r'(.)\1{2,}', password): s -= 10
        weak = {'password','123456','qwerty','letmein','abc123','111111'}
        if password.lower() in weak: s = 5
        s = max(0, min(100, s))
        if s < 20: return s, "Très faible", "#ef4444"
        if s < 40: return s, "Faible",      "#f97316"
        if s < 60: return s, "Moyen",       "#eab308"
        if s < 80: return s, "Fort",        "#22c55e"
        return s,             "Très fort",  "#06b6d4"
