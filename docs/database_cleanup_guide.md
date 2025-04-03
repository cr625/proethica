# Database Cleanup Guide

This guide provides instructions for cleaning and recreating the database when you need a fresh start for development or testing.

## Option 1: Complete Database Recreation (Recommended)

The fastest and most reliable approach is to completely drop and recreate the database. This approach ensures a clean state with no orphaned data or foreign key issues.

### Using the drop_and_recreate_db.sh Script

```bash
# With all steps (backup, migrations, and admin user creation)
./scripts/drop_and_recreate_db.sh

# Skip backup if you don't need it
./scripts/drop_and_recreate_db.sh --no-backup

# Only recreate the database without migrations or admin user
./scripts/drop_and_recreate_db.sh --no-migrate --no-admin
```

This script will:
1. Create a backup of your database (unless --no-backup is specified)
2. Drop the entire database
3. Recreate the database with the same name and owner
4. Enable required extensions (pgvector)
5. Run migrations (unless --no-migrate is specified)
6. Create the admin user (unless --no-admin is specified)

**Note**: This script requires PostgreSQL superuser access (it will prompt for sudo password).

### Using the Direct SQL Script

You can also run the SQL script directly as PostgreSQL superuser:

```bash
sudo -u postgres psql -f scripts/direct_recreate_db.sql
```

After running this script, you'll need to:
1. Run migrations: `flask db upgrade`
2. Create an admin user: `python scripts/create_admin_user.py`

## Option 2: Clean Existing Database

If you don't want to drop the database, you can use these scripts to clean specific parts:

### Using recreate_clean_db.py

This script keeps the database but drops all tables and recreates them:

```bash
python scripts/recreate_clean_db.py

# Skip backup
python scripts/recreate_clean_db.py --no-backup

# Skip confirmation
python scripts/recreate_clean_db.py --force
```

### Deleting Specific Worlds

If you just need to delete a specific world that's causing issues:

```bash
# Use the force delete script (handles foreign key constraints)
python scripts/force_delete_world.py WORLD_ID

# Force deletion without confirmation
python scripts/force_delete_world.py WORLD_ID --force

# Or use direct SQL deletion (handles complex constraints)
python scripts/direct_delete_world.py WORLD_ID --force
```

## Restoring from Backup

If you need to revert to a previous state:

```bash
bash backups/restore_database.sh BACKUP_NAME
```

Where BACKUP_NAME is the name of the backup file without the .dump extension.

## When to Clean the Database

Consider cleaning or recreating the database when:

1. You've made significant schema changes
2. You're implementing a new data model (like RDF triples)
3. You have corruption or constraint issues
4. You want to start fresh with test data

A clean database ensures that your schema matches your models exactly, eliminating any inconsistencies that may arise during development.
