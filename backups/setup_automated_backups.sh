#!/bin/bash

# Script to set up automated database backups using cron
# This will add a cron job to run the backup script at the specified frequency

# Get the absolute path to the backup script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="${SCRIPT_DIR}/backup_database.sh"

# Check if the backup script exists
if [ ! -f "${BACKUP_SCRIPT}" ]; then
    echo "Error: Backup script not found at ${BACKUP_SCRIPT}"
    exit 1
fi

# Make sure the backup script is executable
chmod +x "${BACKUP_SCRIPT}"

# Display menu for backup frequency
echo "Select backup frequency:"
echo "1) Daily (at midnight)"
echo "2) Weekly (Sunday at midnight)"
echo "3) Monthly (1st of the month at midnight)"
echo "4) Custom (you'll enter a custom cron schedule)"
read -p "Enter your choice (1-4): " CHOICE

# Set the cron schedule based on the choice
case $CHOICE in
    1)
        SCHEDULE="0 0 * * *"
        DESCRIPTION="daily at midnight"
        ;;
    2)
        SCHEDULE="0 0 * * 0"
        DESCRIPTION="weekly on Sunday at midnight"
        ;;
    3)
        SCHEDULE="0 0 1 * *"
        DESCRIPTION="monthly on the 1st at midnight"
        ;;
    4)
        echo "Enter custom cron schedule (e.g., '0 0 * * *' for daily at midnight):"
        read -p "Cron schedule: " SCHEDULE
        DESCRIPTION="custom schedule: ${SCHEDULE}"
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

# Create a temporary file for the new crontab
TEMP_CRONTAB=$(mktemp)

# Export the current crontab
crontab -l > "${TEMP_CRONTAB}" 2>/dev/null

# Check if the backup job already exists
if grep -q "${BACKUP_SCRIPT}" "${TEMP_CRONTAB}"; then
    echo "A cron job for database backup already exists."
    echo "Current crontab entries:"
    grep "${BACKUP_SCRIPT}" "${TEMP_CRONTAB}"
    
    read -p "Do you want to replace it? (y/n): " REPLACE
    if [ "${REPLACE}" != "y" ] && [ "${REPLACE}" != "Y" ]; then
        echo "Operation cancelled."
        rm "${TEMP_CRONTAB}"
        exit 0
    fi
    
    # Remove existing backup job
    grep -v "${BACKUP_SCRIPT}" "${TEMP_CRONTAB}" > "${TEMP_CRONTAB}.new"
    mv "${TEMP_CRONTAB}.new" "${TEMP_CRONTAB}"
fi

# Add the new cron job
echo "# AI Ethical DM database backup ${DESCRIPTION}" >> "${TEMP_CRONTAB}"
echo "${SCHEDULE} ${BACKUP_SCRIPT} > /dev/null 2>&1" >> "${TEMP_CRONTAB}"

# Install the new crontab
crontab "${TEMP_CRONTAB}"

# Clean up
rm "${TEMP_CRONTAB}"

echo "Automated backup has been set up to run ${DESCRIPTION}."
echo "The backup script will be executed at: ${BACKUP_SCRIPT}"
echo "To view or modify your cron jobs, run: crontab -e"

exit 0
