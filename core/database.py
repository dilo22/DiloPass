import sqlite3
import time
import os
from dataclasses import dataclass, field
from typing import Optional


DATA_DIR = os.path.join(os.path.expanduser("~"), ".dilopass")
DB_PATH  = os.path.join(DATA_DIR, "vault.db")
ATTACHMENTS_DIR = os.path.join(DATA_DIR, "attachments")
FILE_VAULT_DIR  = os.path.join(DATA_DIR, "filevault")


@dataclass
class VaultEntry:
    title: str
    username: str
    password: str
    url: str = ""
    notes: str = ""
    category: str = "General"
    is_favorite: bool = False
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    last_used: Optional[float] = None
    id: Optional[int] = None


@dataclass
class SecureNote:
    title: str
    content: str
    color: str = "#4A9EFF"
    tags: str = ""
    is_favorite: bool = False
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    id: Optional[int] = None


@dataclass
class FileVaultFolder:
    name: str
    parent_id: Optional[int] = None
    created_at: float = field(default_factory=time.time)
    id: Optional[int] = None


@dataclass
class FileVaultFile:
    folder_id: int
    title: str
    stored_name: str
    original_name: str
    size_bytes: int
    created_at: float = field(default_factory=time.time)
    id: Optional[int] = None


@dataclass
class VaultAttachment:
    entry_id: int
    stored_name: str
    original_name: str
    size_bytes: int
    created_at: float = field(default_factory=time.time)
    id: Optional[int] = None


class DatabaseManager:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
        os.makedirs(FILE_VAULT_DIR, exist_ok=True)
        self._conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        c = self._conn
        c.executescript("""
            CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value BLOB NOT NULL
            );
            CREATE TABLE IF NOT EXISTS vault (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       BLOB NOT NULL,
                username    BLOB,
                password    BLOB NOT NULL,
                url         BLOB,
                notes       BLOB,
                category    TEXT NOT NULL DEFAULT 'General',
                is_favorite INTEGER NOT NULL DEFAULT 0,
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL,
                last_used   REAL
            );
            CREATE TABLE IF NOT EXISTS notes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       BLOB NOT NULL,
                content     BLOB NOT NULL,
                color       TEXT NOT NULL DEFAULT '#4A9EFF',
                tags        BLOB,
                is_favorite INTEGER NOT NULL DEFAULT 0,
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attachments (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id      INTEGER NOT NULL,
                stored_name   TEXT NOT NULL UNIQUE,
                original_name BLOB NOT NULL,
                size_bytes    INTEGER NOT NULL,
                created_at    REAL NOT NULL,
                FOREIGN KEY (entry_id) REFERENCES vault(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS file_vault_folders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        BLOB NOT NULL,
                parent_id   INTEGER,
                created_at  REAL NOT NULL,
                FOREIGN KEY (parent_id) REFERENCES file_vault_folders(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS file_vault_files (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_id     INTEGER NOT NULL,
                title         BLOB NOT NULL,
                stored_name   TEXT NOT NULL UNIQUE,
                original_name BLOB NOT NULL,
                size_bytes    INTEGER NOT NULL,
                created_at    REAL NOT NULL,
                FOREIGN KEY (folder_id) REFERENCES file_vault_folders(id) ON DELETE CASCADE
            );
        """)
        c.commit()

    # ── Config ────────────────────────────────────────────────────────────────

    def is_first_run(self) -> bool:
        row = self._conn.execute(
            "SELECT value FROM config WHERE key='password_hash'").fetchone()
        return row is None

    def setup_master(self, password_hash: bytes, salt: bytes):
        self._conn.execute(
            "INSERT OR REPLACE INTO config VALUES ('password_hash', ?)", (password_hash,))
        self._conn.execute(
            "INSERT OR REPLACE INTO config VALUES ('salt', ?)", (salt,))
        self._conn.commit()

    def get_master_hash(self) -> bytes:
        row = self._conn.execute(
            "SELECT value FROM config WHERE key='password_hash'").fetchone()
        return bytes(row["value"]) if row else b""

    def get_salt(self) -> bytes:
        row = self._conn.execute(
            "SELECT value FROM config WHERE key='salt'").fetchone()
        return bytes(row["value"]) if row else b""

    def get_setting(self, key: str, default: str = "") -> str:
        row = self._conn.execute(
            "SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return row["value"].decode() if row else default

    def set_setting(self, key: str, value: str):
        self._conn.execute(
            "INSERT OR REPLACE INTO config VALUES (?, ?)", (key, value.encode()))
        self._conn.commit()

    # ── Vault CRUD ────────────────────────────────────────────────────────────

    def add_vault(self, e: VaultEntry) -> int:
        cur = self._conn.execute(
            """INSERT INTO vault (title,username,password,url,notes,category,
               is_favorite,created_at,updated_at,last_used)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (e.title, e.username, e.password, e.url, e.notes,
             e.category, int(e.is_favorite), e.created_at, e.updated_at, e.last_used))
        self._conn.commit()
        return cur.lastrowid

    def update_vault(self, e: VaultEntry):
        e.updated_at = time.time()
        self._conn.execute(
            """UPDATE vault SET title=?,username=?,password=?,url=?,notes=?,
               category=?,is_favorite=?,updated_at=?,last_used=? WHERE id=?""",
            (e.title, e.username, e.password, e.url, e.notes,
             e.category, int(e.is_favorite), e.updated_at, e.last_used, e.id))
        self._conn.commit()

    def delete_vault(self, entry_id: int):
        self._conn.execute("DELETE FROM attachments WHERE entry_id=?", (entry_id,))
        self._conn.execute("DELETE FROM vault WHERE id=?", (entry_id,))
        self._conn.commit()

    def get_all_vault(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM vault ORDER BY updated_at DESC").fetchall()

    def replace_vault_encrypted_fields(self, entry_id: int, title, username,
                                       password, url, notes):
        self._conn.execute(
            """UPDATE vault
               SET title=?, username=?, password=?, url=?, notes=?, updated_at=?
               WHERE id=?""",
            (title, username, password, url, notes, time.time(), entry_id))

    def touch_vault(self, entry_id: int):
        self._conn.execute(
            "UPDATE vault SET last_used=? WHERE id=?", (time.time(), entry_id))
        self._conn.commit()

    # Attachments

    def add_attachment(self, attachment: VaultAttachment) -> int:
        cur = self._conn.execute(
            """INSERT INTO attachments
               (entry_id, stored_name, original_name, size_bytes, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (attachment.entry_id, attachment.stored_name,
             attachment.original_name, attachment.size_bytes,
             attachment.created_at))
        self._conn.commit()
        return cur.lastrowid

    def get_attachments_for_entry(self, entry_id: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM attachments WHERE entry_id=? ORDER BY created_at DESC",
            (entry_id,)).fetchall()

    def get_all_attachments(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM attachments ORDER BY created_at DESC").fetchall()

    def delete_attachment(self, attachment_id: int):
        self._conn.execute("DELETE FROM attachments WHERE id=?", (attachment_id,))
        self._conn.commit()

    def replace_attachment_name(self, attachment_id: int, original_name):
        self._conn.execute(
            "UPDATE attachments SET original_name=? WHERE id=?",
            (original_name, attachment_id))

    # ── Notes CRUD ────────────────────────────────────────────────────────────

    def add_note(self, n: SecureNote) -> int:
        cur = self._conn.execute(
            """INSERT INTO notes (title,content,color,tags,is_favorite,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (n.title, n.content, n.color, n.tags,
             int(n.is_favorite), n.created_at, n.updated_at))
        self._conn.commit()
        return cur.lastrowid

    def update_note(self, n: SecureNote):
        n.updated_at = time.time()
        self._conn.execute(
            """UPDATE notes SET title=?,content=?,color=?,tags=?,is_favorite=?,
               updated_at=? WHERE id=?""",
            (n.title, n.content, n.color, n.tags,
             int(n.is_favorite), n.updated_at, n.id))
        self._conn.commit()

    def delete_note(self, note_id: int):
        self._conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
        self._conn.commit()

    def get_all_notes(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM notes ORDER BY updated_at DESC").fetchall()

    def replace_note_encrypted_fields(self, note_id: int, title, content, tags):
        self._conn.execute(
            """UPDATE notes
               SET title=?, content=?, tags=?, updated_at=?
               WHERE id=?""",
            (title, content, tags, time.time(), note_id))

    # ── File Vault Folders ────────────────────────────────────────────────────

    def add_file_vault_folder(self, name: bytes, parent_id: Optional[int] = None) -> int:
        cur = self._conn.execute(
            "INSERT INTO file_vault_folders (name, parent_id, created_at) VALUES (?, ?, ?)",
            (name, parent_id, time.time()))
        self._conn.commit()
        return cur.lastrowid

    def get_file_vault_folders(self, parent_id: Optional[int] = None) -> list:
        return self._conn.execute(
            "SELECT * FROM file_vault_folders WHERE parent_id IS ? ORDER BY created_at ASC",
            (parent_id,)).fetchall()

    def rename_file_vault_folder(self, folder_id: int, name: bytes):
        self._conn.execute(
            "UPDATE file_vault_folders SET name=? WHERE id=?", (name, folder_id))
        self._conn.commit()

    def delete_file_vault_folder(self, folder_id: int):
        self._conn.execute("DELETE FROM file_vault_folders WHERE id=?", (folder_id,))
        self._conn.commit()

    def get_all_folder_ids_recursive(self, folder_id: int) -> list[int]:
        """Retourne l'ID du dossier + tous ses descendants."""
        ids = [folder_id]
        for child in self.get_file_vault_folders(parent_id=folder_id):
            ids.extend(self.get_all_folder_ids_recursive(child["id"]))
        return ids

    # ── File Vault Files ──────────────────────────────────────────────────────

    def add_file_vault_file(self, folder_id: int, title: bytes,
                            stored_name: str, original_name: bytes,
                            size_bytes: int) -> int:
        cur = self._conn.execute(
            """INSERT INTO file_vault_files
               (folder_id, title, stored_name, original_name, size_bytes, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (folder_id, title, stored_name, original_name, size_bytes, time.time()))
        self._conn.commit()
        return cur.lastrowid

    def get_file_vault_files(self, folder_id: int) -> list:
        return self._conn.execute(
            "SELECT * FROM file_vault_files WHERE folder_id=? ORDER BY created_at DESC",
            (folder_id,)).fetchall()

    def get_file_vault_folder(self, folder_id: int):
        return self._conn.execute(
            "SELECT * FROM file_vault_folders WHERE id=?",
            (folder_id,)).fetchone()

    def delete_file_vault_file(self, file_id: int):
        self._conn.execute("DELETE FROM file_vault_files WHERE id=?", (file_id,))
        self._conn.commit()

    def get_all_file_vault_folders_flat(self) -> list:
        return self._conn.execute("SELECT * FROM file_vault_folders").fetchall()

    def get_all_file_vault_files_flat(self) -> list:
        return self._conn.execute("SELECT * FROM file_vault_files").fetchall()

    def update_file_vault_file_fields(self, file_id: int,
                                      title: bytes, original_name: bytes):
        self._conn.execute(
            "UPDATE file_vault_files SET title=?, original_name=? WHERE id=?",
            (title, original_name, file_id))

    def move_file_vault_file(self, file_id: int, folder_id: int):
        self._conn.execute(
            "UPDATE file_vault_files SET folder_id=? WHERE id=?",
            (folder_id, file_id))
        self._conn.commit()

    # ── Recovery ──────────────────────────────────────────────────────────────

    def save_recovery(self, salt: bytes, q1: str, q2: str,
                      encrypted_key: bytes):
        for k, v in [
            ("recovery_salt",          salt),
            ("recovery_q1",            q1.encode()),
            ("recovery_q2",            q2.encode()),
            ("recovery_encrypted_key", encrypted_key),
        ]:
            self._conn.execute(
                "INSERT OR REPLACE INTO config VALUES (?, ?)", (k, v))
        self._conn.commit()

    def get_recovery(self) -> dict | None:
        keys = ["recovery_salt", "recovery_q1", "recovery_q2",
                "recovery_encrypted_key"]
        result = {}
        for k in keys:
            row = self._conn.execute(
                "SELECT value FROM config WHERE key=?", (k,)).fetchone()
            if row is None:
                return None
            result[k] = bytes(row["value"])
        return result

    def begin(self):
        self._conn.execute("BEGIN")

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        v = self._conn.execute("SELECT COUNT(*) FROM vault").fetchone()[0]
        n = self._conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        f = self._conn.execute(
            "SELECT COUNT(*) FROM vault WHERE is_favorite=1").fetchone()[0]
        fv = self._conn.execute("SELECT COUNT(*) FROM file_vault_files").fetchone()[0]
        return {"vault": v, "notes": n, "favorites": f, "files": fv}

    def close(self):
        self._conn.close()
