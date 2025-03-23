# Database Backup and Restore

This directory contains scripts and database backups for the AI Ethical Decision Making application.

## Quick Start

- To create a backup: `./backup_database.sh`
- To restore from a backup: `./restore_database.sh <backup_filename>`
- To set up automated backups: `./setup_automated_backups.sh`

## Backup Files

Backup files are stored in this directory with the naming format:
```
ai_ethical_dm_backup_YYYYMMDD_HHMMSS.dump
```

Where:
- `YYYYMMDD` is the date (year, month, day)
- `HHMMSS` is the time (hour, minute, second)

## Backup Script

To create a new backup of the database, run:

```bash
./backup_database.sh
```

This will:
1. Create a new backup file with the current timestamp
2. Store it in this directory
3. Display information about the backup

## Restore Script

To restore the database from a backup, run:

```bash
./restore_database.sh <backup_filename>
```

For example:
```bash
./restore_database.sh ai_ethical_dm_backup_20250323_135340.dump
```

If you run the script without specifying a backup file, it will show you a list of available backups:
```bash
./restore_database.sh
```

**WARNING**: Restoring will overwrite the current database with the data from the backup file. Make sure you have a backup of the current state if needed.

## Database Configuration

Both scripts are configured to use the following database settings:

- Database name: `ai_ethical_dm`
- Database user: `postgres`
- Database host: `localhost`
- Database port: `5432`

If you need to change these settings, edit the configuration section at the top of each script.

## Automated Backups

You can set up automated backups using the provided script:

```bash
./setup_automated_backups.sh
```

This script will:
1. Ask you to select a backup frequency (daily, weekly, monthly, or custom)
2. Set up a cron job to run the backup script automatically at the specified frequency
3. Show you how to view or modify your cron jobs

Automated backups will be stored in this directory with the same naming format as manual backups.
