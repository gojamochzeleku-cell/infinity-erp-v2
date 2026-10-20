#!/bin/bash
echo "=========================================="
echo "🛡️  INFINITY ERP: DATABASE BACKUP"
echo "=========================================="

# Define variables
DB_FILE="infinity_erp.db"
BACKUP_DIR="backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/infinity_erp_backup_$TIMESTAMP.db"

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Check if database exists
if [ -f "$DB_FILE" ]; then
    echo "Backing up $DB_FILE to $BACKUP_FILE..."
    cp "$DB_FILE" "$BACKUP_FILE"
    
    if [ -f "$BACKUP_FILE" ]; then
        echo "✅ Backup completed successfully!"
        echo "📁 Saved at: $BACKUP_FILE"
        
        # Keep only the last 5 backups to save space
        ls -t $BACKUP_DIR/*.db | tail -n +6 | xargs -r rm
        echo "🧹 Old backups cleaned up (keeping last 5)."
    else
        echo "❌ Backup failed!"
    fi
else
    echo "⚠️  Database file not found. Nothing to backup."
fi
echo "=========================================="
