# Database Backup and Restore Instructions

## Recent Backup Information

Backups of the database are stored in the `backups/` directory with filenames following the pattern `ai_ethical_dm_backup_YYYYMMDD_HHMMSS.dump`.

## How to Restore from a Backup

### One unified command

Use the consolidated script which works with Docker (default) or local tools and supports .dump, .sql, .sql.gz:

```bash
cd /path/to/ai-ethical-dm
bash backups/restore_db.sh backups/ai_ethical_dm_backup_YYYYMMDD_HHMMSS.dump
```

Options:

```bash
# Restore into a specific DB name
bash backups/restore_db.sh backups/file.dump --db ai_ethical_dm

# Local restore (psql tools), specifying host/port
bash backups/restore_db.sh backups/file.sql.gz --mode local --host localhost --port 5433

# Non-interactive
bash backups/restore_db.sh backups/file.dump --no-prompt
```

### What happens during restoration

1. The script will drop the existing `ai_ethical_dm` database
2. Create a new empty database with the same name
3. Restore all data from the backup file (using a Docker container in CodeSpace environment)
4. Report success or any errors that occurred

## Managing Backups

### View Available Backups

To view all available backups:

```bash
ls -lh backups/ai_ethical_dm_backup_*.dump
```

### Restore from a Specific Backup

To restore from any backup, specify its filename:

Use the unified script for any file:
```bash
bash backups/restore_db.sh backups/FILENAME.dump
# or .sql / .sql.gz
bash backups/restore_db.sh backups/FILENAME.sql.gz
```

## Database Configuration

### Defaults

- Container: `proethica-postgres`
- Database: `ai_ethical_dm`
- User: `postgres`
- Host: `localhost`
- Port: `5433` (as mapped in docker-compose)

You can override via flags: `--db`, `--user`, `--host`, `--port`, `--container`, `--mode`.

## Creating Additional Backups

### CodeSpace Environment

To create a new backup in the CodeSpace environment:

```bash
bash backups/backup_codespace_db.sh
```

### Local Environment

To create a new backup in a local environment:

```bash
bash backups/backup_database.sh
```

## Automated Backups

If you'd like to set up automated backups:

```bash
bash backups/setup_automated_backups.sh
```

This will guide you through setting up a cron job to create backups at your preferred frequency.
