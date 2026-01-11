#!/bin/bash

# 备份和恢复脚本
# 用于定期备份数据库、配置文件和文件存储

# 配置
BACKUP_DIR="/app/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DB_PATH="/app/app.db"
STORAGE_PATH="/app/storage"
CONFIG_PATH="/app/.env"
BACKUP_RETENTION_DAYS=7

# AWS S3配置（可选）
S3_BUCKET="your-s3-bucket"
AWS_REGION="us-east-1"

# GCP Cloud Storage配置（可选）
GCS_BUCKET="your-gcs-bucket"

# 创建备份目录
mkdir -p $BACKUP_DIR

# 函数：备份数据库
backup_database() {
    echo "Backing up database..."
    sqlite3 $DB_PATH ".backup '$BACKUP_DIR/db_backup_$TIMESTAMP.sqlite'"
    gzip "$BACKUP_DIR/db_backup_$TIMESTAMP.sqlite"
    echo "Database backup completed: $BACKUP_DIR/db_backup_$TIMESTAMP.sqlite.gz"
}

# 函数：备份存储目录
backup_storage() {
    echo "Backing up storage directory..."
    tar -czf "$BACKUP_DIR/storage_backup_$TIMESTAMP.tar.gz" -C $(dirname $STORAGE_PATH) $(basename $STORAGE_PATH)
    echo "Storage backup completed: $BACKUP_DIR/storage_backup_$TIMESTAMP.tar.gz"
}

# 函数：备份配置文件
backup_config() {
    echo "Backing up configuration files..."
    cp $CONFIG_PATH "$BACKUP_DIR/config_backup_$TIMESTAMP.env"
    echo "Config backup completed: $BACKUP_DIR/config_backup_$TIMESTAMP.env"
}

# 函数：上传到S3
upload_to_s3() {
    echo "Uploading backups to S3..."
    aws s3 cp --region $AWS_REGION "$BACKUP_DIR/" "s3://$S3_BUCKET/backups/" --recursive
    echo "Upload to S3 completed"
}

# 函数：上传到GCS
upload_to_gcs() {
    echo "Uploading backups to GCS..."
    gsutil cp "$BACKUP_DIR/*" "gs://$GCS_BUCKET/backups/"
    echo "Upload to GCS completed"
}

# 函数：清理旧备份
cleanup_old_backups() {
    echo "Cleaning up old backups..."
    find $BACKUP_DIR -name "*.gz" -type f -mtime +$BACKUP_RETENTION_DAYS -delete
    find $BACKUP_DIR -name "*.env" -type f -mtime +$BACKUP_RETENTION_DAYS -delete
    echo "Old backups cleaned up"
}

# 函数：恢复数据库
restore_database() {
    local backup_file=$1
    if [ -f "$backup_file" ]; then
        echo "Restoring database from $backup_file..."
        gunzip -c "$backup_file" > "$DB_PATH"
        echo "Database restored successfully"
    else
        echo "Backup file not found: $backup_file"
        exit 1
    fi
}

# 函数：恢复存储目录
restore_storage() {
    local backup_file=$1
    if [ -f "$backup_file" ]; then
        echo "Restoring storage from $backup_file..."
        rm -rf $STORAGE_PATH
        mkdir -p $STORAGE_PATH
        tar -xzf "$backup_file" -C $(dirname $STORAGE_PATH)
        echo "Storage restored successfully"
    else
        echo "Backup file not found: $backup_file"
        exit 1
    fi
}

# 函数：恢复配置文件
restore_config() {
    local backup_file=$1
    if [ -f "$backup_file" ]; then
        echo "Restoring configuration from $backup_file..."
        cp "$backup_file" $CONFIG_PATH
        echo "Configuration restored successfully"
    else
        echo "Backup file not found: $backup_file"
        exit 1
    fi
}

# 主菜单
main() {
    case "$1" in
        backup)
            backup_database
            backup_storage
            backup_config
            cleanup_old_backups
            ;;
        backup-aws)
            backup_database
            backup_storage
            backup_config
            upload_to_s3
            cleanup_old_backups
            ;;
        backup-gcp)
            backup_database
            backup_storage
            backup_config
            upload_to_gcs
            cleanup_old_backups
            ;;
        restore-db)
            restore_database "$2"
            ;;
        restore-storage)
            restore_storage "$2"
            ;;
        restore-config)
            restore_config "$2"
            ;;
        *)
            echo "Usage: $0 {backup|backup-aws|backup-gcp|restore-db <backup-file>|restore-storage <backup-file>|restore-config <backup-file>}"
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"