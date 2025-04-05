# Database Backup and Restore Instructions

## Recent Backup Information

A backup of the current database has been created:

- **Backup filename**: `ai_ethical_dm_backup_20250405_182557.dump`
- **Backup size**: 154K
- **Backup date**: April 5, 2025, 6:25:57 PM
- **Location**: `/home/chris/ai-ethical-dm/backups/`

## How to Restore from this Backup

To restore the database from this backup, run:

```bash
cd /home/chris/ai-ethical-dm
bash backups/restore_database.sh backups/ai_ethical_dm_backup_20250405_182557.dump
```

When prompted, type `y` to confirm the restoration.

### What happens during restoration

1. The script will drop the existing `ai_ethical_dm` database
2. Create a new empty database with the same name
3. Restore all data from the backup file
4. Report success or any errors that occurred

## Alternative Backups

If you need to use a different backup, you can:

1. View all available backups:
   ```bash
   ls -lh backups/ai_ethical_dm_backup_*.dump
   ```

2. Restore from any backup by specifying its filename:
   ```bash
   bash backups/restore_database.sh backups/FILENAME.dump
   ```

## Database Configuration

The backup and restore scripts use these database settings:

- **Database name**: `ai_ethical_dm`
- **Database user**: `postgres`
- **Database host**: `localhost`
- **Database port**: `5432`

## Creating Additional Backups

To create a new backup at any time:

```bash
bash backups/backup_database.sh
```

## Automated Backups

If you'd like to set up automated backups:

```bash
bash backups/setup_automated_backups.sh
```

This will guide you through setting up a cron job to create backups at your preferred frequency.
