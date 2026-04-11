# DiloPass

Coffre-fort numérique local chiffré. Gérez vos mots de passe, notes sécurisées et fichiers confidentiels sans jamais envoyer vos données sur un serveur.

## Fonctionnalités

- **Coffre mots de passe** — stockage chiffré avec titre, identifiant, mot de passe, URL, notes, catégorie et pièces jointes
- **Notes sécurisées** — notes chiffrées avec étiquettes et marquage favori
- **Coffre de fichiers** — import/export de fichiers chiffrés organisés en dossiers
- **Générateur de mots de passe** — aléatoire ou passphrase, avec indicateur de robustesse
- **Récupération** — accès de secours via deux questions secrètes
- **Journal d'audit** — historique des actions dans l'application
- **Interface sombre** — UI CustomTkinter, 100 % locale

## Sécurité

| Mécanisme | Détail |
|---|---|
| Chiffrement des données | AES-256 via Fernet |
| Dérivation de clé | PBKDF2-HMAC-SHA256 — 260 000 itérations |
| Hachage mot de passe maître | bcrypt (cost 12) |
| Récupération | PBKDF2-HMAC-SHA256 — 100 000 itérations sur les réponses |
| Stockage | SQLite local dans `~/.dilopass/vault.db` |

Aucune donnée ne quitte la machine. La clé de chiffrement n'est jamais écrite sur le disque.

## Prérequis

- Python 3.11+

## Installation

```bash
pip install -r requirements.txt
python main.py
```

## Dépendances

```
customtkinter >= 5.2.0
cryptography  >= 41.0.0
bcrypt        >= 4.0.0
Pillow        >= 10.0.0
pyperclip     >= 1.8.2
```

## Structure du projet

```
DiloPass/
├── main.py              # Point d'entrée
├── requirements.txt
├── core/
│   ├── crypto.py        # Chiffrement, hachage, générateur
│   └── database.py      # SQLite — CRUD vault, notes, fichiers
└── ui/
    ├── app.py           # Fenêtre principale
    ├── login.py         # Écran de connexion / création
    ├── vault.py         # Gestion des mots de passe
    ├── notes.py         # Notes sécurisées
    ├── filevault.py     # Coffre de fichiers
    ├── generator.py     # Générateur de mots de passe
    ├── audit.py         # Journal d'audit
    └── settings.py      # Paramètres
```

## Données locales

Toutes les données sont stockées dans `~/.dilopass/` :

```
~/.dilopass/
├── vault.db          # Base SQLite chiffrée
├── attachments/      # Pièces jointes chiffrées
└── filevault/        # Fichiers du coffre chiffrés
```

## Build (Windows)

```bat
build.bat
```

Produit un exécutable autonome via PyInstaller (`dilopass.spec`).
