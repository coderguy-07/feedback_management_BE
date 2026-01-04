# Backend Scripts

This directory contains utility scripts for managing the Feedback Management System backend.

## 🛠️ Available Scripts

### `init_admin.py`
Initializes the system by performing essential first-run tasks:
- Updates database schema (backfilling new columns if necessary).
- Creates the default `admin` superuser if it doesn't exist.

**Usage:**
```bash
python scripts/init_admin.py
```

### `add_user.py`
A Command Line Interface (CLI) to add new users to the system manually. Useful for setting up initial accounts for District Officers or Retail Outlets.

**Usage:**
Interactive mode:
```bash
python scripts/add_user.py --interactive
```

Command line arguments:
```bash
python scripts/add_user.py --username "john_doe" --password "secret123" --role "RO" --branch-code "BR101" --fullname "John Doe"
```

### Migrations
Various `migrate_*.py` files are present to handle legacy database schema updates. Use these only if specifically upgrading from an older version of the database.
