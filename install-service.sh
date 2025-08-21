#!/bin/bash

# FT8 Logs Service Installation Script
# This script installs ft8logs.py as a systemd service

set -e

SERVICE_NAME="ft8logs"
SERVICE_USER="ft8logs"
INSTALL_DIR="/opt/ft8logs"
SERVICE_FILE="ft8logs.service"
PYTHON_SCRIPT="ft8logs.py"

echo "=== FT8 Logs Service Installation ==="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)" 
   exit 1
fi

# Check if service is already running
if systemctl is-active --quiet $SERVICE_NAME; then
    echo "Stopping existing $SERVICE_NAME service..."
    systemctl stop $SERVICE_NAME
fi

# Create service user if it doesn't exist
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "Creating service user: $SERVICE_USER"
    useradd --system --home-dir $INSTALL_DIR --shell /bin/false $SERVICE_USER
else
    echo "Service user $SERVICE_USER already exists"
fi

# Create installation directory
echo "Creating installation directory: $INSTALL_DIR"
mkdir -p $INSTALL_DIR
mkdir -p $INSTALL_DIR/logs
mkdir -p $INSTALL_DIR/uploads
mkdir -p $INSTALL_DIR/templates

# Copy application files
echo "Copying application files..."
cp $PYTHON_SCRIPT $INSTALL_DIR/
cp -r templates/* $INSTALL_DIR/templates/
cp requirements.txt $INSTALL_DIR/
cp adif_set.py $INSTALL_DIR/
cp ft8logs.service $INSTALL_DIR/

# Create logs directory if it has existing log files
if [ -d "logs" ]; then
    echo "Copying existing logs..."
    cp -r logs/* $INSTALL_DIR/logs/
fi

# Set up Python virtual environment
echo "Setting up Python virtual environment..."
cd $INSTALL_DIR
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# Set ownership
echo "Setting file ownership..."
chown -R $SERVICE_USER:$SERVICE_USER $INSTALL_DIR

# Set permissions
echo "Setting file permissions..."
chmod 755 $INSTALL_DIR
chmod 755 $INSTALL_DIR/$PYTHON_SCRIPT
chmod -R 755 $INSTALL_DIR/templates
chmod -R 755 $INSTALL_DIR/.venv
chmod -R 775 $INSTALL_DIR/logs
chmod -R 775 $INSTALL_DIR/uploads

# Install systemd service
echo "Installing systemd service..."
cp $SERVICE_FILE /etc/systemd/system/
systemctl daemon-reload

# Enable and start service
echo "Enabling and starting $SERVICE_NAME service..."
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

# Check service status
echo "Checking service status..."
sleep 2
if systemctl is-active --quiet $SERVICE_NAME; then
    echo "✓ $SERVICE_NAME service is running successfully!"
    echo "✓ Web interface available at: http://localhost:5019"
    echo "✓ Service logs: journalctl -u $SERVICE_NAME -f"
    echo "✓ Service status: systemctl status $SERVICE_NAME"
else
    echo "✗ Failed to start $SERVICE_NAME service"
    echo "Check logs with: journalctl -u $SERVICE_NAME"
    exit 1
fi

echo ""
echo "=== Installation Complete ==="
echo "Service is installed and running at: $INSTALL_DIR"
echo "Web interface: http://localhost:5019"
echo ""
echo "Useful commands:"
echo "  Start service:   systemctl start $SERVICE_NAME"
echo "  Stop service:    systemctl stop $SERVICE_NAME"
echo "  Restart service: systemctl restart $SERVICE_NAME"
echo "  Service status:  systemctl status $SERVICE_NAME"
echo "  View logs:       journalctl -u $SERVICE_NAME -f"
echo "  Disable service: systemctl disable $SERVICE_NAME"
echo ""
