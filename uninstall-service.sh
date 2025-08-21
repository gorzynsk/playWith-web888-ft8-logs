#!/bin/bash

# FT8 Logs Service Uninstallation Script
# This script removes the ft8logs systemd service

set -e

SERVICE_NAME="ft8logs"
SERVICE_USER="ft8logs"
INSTALL_DIR="/opt/ft8logs"

echo "=== FT8 Logs Service Uninstallation ==="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)" 
   exit 1
fi

# Stop service if running
if systemctl is-active --quiet $SERVICE_NAME; then
    echo "Stopping $SERVICE_NAME service..."
    systemctl stop $SERVICE_NAME
fi

# Disable service
if systemctl is-enabled --quiet $SERVICE_NAME; then
    echo "Disabling $SERVICE_NAME service..."
    systemctl disable $SERVICE_NAME
fi

# Remove systemd service file
if [ -f "/etc/systemd/system/$SERVICE_NAME.service" ]; then
    echo "Removing systemd service file..."
    rm /etc/systemd/system/$SERVICE_NAME.service
    systemctl daemon-reload
fi

# Backup data before removal
if [ -d "$INSTALL_DIR/logs" ] && [ "$(ls -A $INSTALL_DIR/logs)" ]; then
    BACKUP_DIR="/tmp/ft8logs-backup-$(date +%Y%m%d-%H%M%S)"
    echo "Backing up logs to: $BACKUP_DIR"
    mkdir -p $BACKUP_DIR
    cp -r $INSTALL_DIR/logs/* $BACKUP_DIR/
    echo "Backup created at: $BACKUP_DIR"
fi

# Remove installation directory
if [ -d "$INSTALL_DIR" ]; then
    echo "Removing installation directory: $INSTALL_DIR"
    rm -rf $INSTALL_DIR
fi

# Remove service user
if id "$SERVICE_USER" &>/dev/null; then
    echo "Removing service user: $SERVICE_USER"
    userdel $SERVICE_USER
fi

echo ""
echo "=== Uninstallation Complete ==="
echo "✓ $SERVICE_NAME service has been removed"
if [ -n "$BACKUP_DIR" ]; then
    echo "✓ Log files backed up to: $BACKUP_DIR"
fi
echo ""
