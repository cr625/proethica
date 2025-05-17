# Database Backup and Restore Instructions

## Recent Backup Information

Backups of the database are stored in the `backups/` directory with filenames following the pattern `ai_ethical_dm_backup_YYYYMMDD_HHMMSS.dump`.

## How to Restore from a Backup

### In CodeSpace Environment

To restore the database in a CodeSpace environment (with Docker containers):

```bash
cd /workspaces/ai-ethical-dm
bash backups/restore_codespace_db.sh backups/ai_ethical_dm_backup_YYYYMMDD_HHMMSS.dump
```

When prompted, type `y` to confirm the restoration.

### In Local Development Environment

To restore the database in a local development environment:

```bash
cd /path/to/ai-ethical-dm
bash backups/restore_database.sh backups/ai_ethical_dm_backup_YYYYMMDD_HHMMSS.dump
```

When prompted, type `y` to confirm the restoration.

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

For CodeSpace environment:
```bash
bash backups/restore_codespace_db.sh backups/FILENAME.dump
```

For local environment:
```bash
bash backups/restore_database.sh backups/FILENAME.dump
```

## Database Configuration

### CodeSpace Environment 

The CodeSpace scripts use these settings:

- **Container name**: `proethica-postgres`
- **Database name**: `ai_ethical_dm`
- **Database user**: `postgres`
- **Database password**: `PASS` (default for CodeSpace)

### Local Environment

The local environment scripts use these settings:

- **Database name**: `ai_ethical_dm`
- **Database user**: `postgres`
- **Database host**: `localhost`
- **Database port**: `5433` (CodeSpace) or `5432` (local)

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
