# Database Backup and Restore

This directory contains scripts and database backups for the AI Ethical Decision Making application.

## Quick Start

### Local Environment
- To create a backup: `./backup_database.sh`
- To restore from a backup: `./restore_database.sh <backup_filename>`
- To set up automated backups: `./setup_automated_backups.sh`

### CodeSpace Environment
- To create a backup: `./backup_codespace_db.sh`
- To restore from a backup: `./restore_codespace_db.sh <backup_filename>`

## Backup Files

Backup files are stored in this directory with the naming format:
```
ai_ethical_dm_backup_YYYYMMDD_HHMMSS.dump
```

Where:
- `YYYYMMDD` is the date (year, month, day)
- `HHMMSS` is the time (hour, minute, second)

Backup files are compatible between the local and CodeSpace environments, though you'll need to use the appropriate restore script for your environment.

## Backup Scripts

### Local Environment

To create a new backup of the database in a local environment, run:

```bash
./backup_database.sh
```

### CodeSpace Environment

To create a new backup of the database in the CodeSpace environment (which uses Docker containers), run:

```bash
./backup_codespace_db.sh
```

Both scripts will:
1. Create a new backup file with the current timestamp
2. Store it in this directory
3. Display information about the backup
4. List all available backups

## Restore Scripts

### Local Environment

To restore the database from a backup in a local environment, run:

```bash
./restore_database.sh <backup_filename>
```

For example:
```bash
./restore_database.sh ai_ethical_dm_backup_20250323_135340.dump
```

### CodeSpace Environment

To restore the database from a backup in the CodeSpace environment, run:

```bash
./restore_codespace_db.sh <backup_filename>
```

For example:
```bash
./restore_codespace_db.sh ai_ethical_dm_backup_20250516_223754.dump
```

If you run either script without specifying a backup file, it will show you a list of available backups.

**WARNING**: Restoring will overwrite the current database with the data from the backup file. Make sure you have a backup of the current state if needed.

## Database Configuration

### Local Environment

The local environment scripts are configured to use the following database settings:

- Database name: `ai_ethical_dm`
- Database user: `postgres`
- Database host: `localhost`
- Database port: `5432`

### CodeSpace Environment

The CodeSpace scripts are configured to use the following settings:

- Container name: `proethica-postgres`
- Database name: `ai_ethical_dm`
- Database user: `postgres`
- Database password: `PASS` (default for CodeSpace)
- Internal port: `5432`
- External port: `5433` (mapped to 5432 inside the container)

If you need to change these settings, edit the configuration section at the top of each script.

## Automated Backups

### Local Environment

You can set up automated backups using the provided script:

```bash
./setup_automated_backups.sh
```

This script will:
1. Ask you to select a backup frequency (daily, weekly, monthly, or custom)
2. Set up a cron job to run the backup script automatically at the specified frequency
3. Show you how to view or modify your cron jobs

### CodeSpace Environment

For CodeSpace environments, automated backups would need to be set up differently due to the ephemeral nature of GitHub Codespaces. Consider implementing a workflow that:

1. Creates backups before shutting down the Codespace
2. Stores backups in GitHub repository or other persistent storage
3. Restores from the backup when the Codespace is restarted

Automated backups will be stored in this directory with the same naming format as manual backups.
