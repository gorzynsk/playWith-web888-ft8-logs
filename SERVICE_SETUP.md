# FT8 Logs Service Setup

This document describes how to install and manage the FT8 Logs application as a Linux systemd service.

## Installation

### Prerequisites

- Linux system with systemd
- Python 3.6 or later
- Root/sudo access for service installation

### Quick Installation

1. Make the installation script executable:
   ```bash
   chmod +x install-service.sh
   ```

2. Run the installation script as root:
   ```bash
   sudo ./install-service.sh
   ```

The installation script will:
- Create a dedicated system user (`ft8logs`)
- Install the application to `/opt/ft8logs`
- Set up a Python virtual environment
- Install all required dependencies
- Create and enable the systemd service
- Start the service automatically

### Manual Installation Steps

If you prefer to install manually:

1. Create system user:
   ```bash
   sudo useradd --system --home-dir /opt/ft8logs --shell /bin/false ft8logs
   ```

2. Create directories:
   ```bash
   sudo mkdir -p /opt/ft8logs/{logs,uploads,templates}
   ```

3. Copy files:
   ```bash
   sudo cp ft8logs.py /opt/ft8logs/
   sudo cp -r templates/* /opt/ft8logs/templates/
   sudo cp requirements.txt /opt/ft8logs/
   sudo cp adif_set.py /opt/ft8logs/
   ```

4. Set up virtual environment:
   ```bash
   cd /opt/ft8logs
   sudo python3 -m venv .venv
   sudo .venv/bin/pip install --upgrade pip
   sudo .venv/bin/pip install -r requirements.txt
   ```

5. Set ownership and permissions:
   ```bash
   sudo chown -R ft8logs:ft8logs /opt/ft8logs
   sudo chmod -R 775 /opt/ft8logs/logs /opt/ft8logs/uploads
   ```

6. Install service:
   ```bash
   sudo cp ft8logs.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable ft8logs
   sudo systemctl start ft8logs
   ```

## Service Management

### Basic Commands

- **Start service**: `sudo systemctl start ft8logs`
- **Stop service**: `sudo systemctl stop ft8logs`
- **Restart service**: `sudo systemctl restart ft8logs`
- **Enable service** (start on boot): `sudo systemctl enable ft8logs`
- **Disable service**: `sudo systemctl disable ft8logs`
- **Check status**: `sudo systemctl status ft8logs`

### Viewing Logs

- **Real-time logs**: `sudo journalctl -u ft8logs -f`
- **Recent logs**: `sudo journalctl -u ft8logs -n 50`
- **Logs since today**: `sudo journalctl -u ft8logs --since today`

## Configuration

### Environment Variables

The service configuration can be modified by editing `/etc/systemd/system/ft8logs.service`:

```ini
Environment=STATION_CALLSIGN=SQ2WB
Environment=MY_GRIDSQUARE=JO92ES
Environment=LimitTime=1800
Environment=ADIF_LOGS=No
```

After modifying the service file:
```bash
sudo systemctl daemon-reload
sudo systemctl restart ft8logs
```

### Available Environment Variables

- `STATION_CALLSIGN`: Your amateur radio callsign
- `MY_GRIDSQUARE`: Your grid square location
- `LimitTime`: Time in seconds to keep spots visible (default: 1800)
- `ADIF_LOGS`: Whether to create ADIF log files ("Yes" or "No")

## Access

Once installed and running:
- **Web Interface**: http://localhost:5019
- **UDP Port**: The service listens on port 5140 for FT8 log data

## File Locations

- **Installation Directory**: `/opt/ft8logs/`
- **Log Files**: `/opt/ft8logs/logs/`
- **Upload Directory**: `/opt/ft8logs/uploads/`
- **Service File**: `/etc/systemd/system/ft8logs.service`

## Uninstallation

To completely remove the service:

1. Make the uninstall script executable:
   ```bash
   chmod +x uninstall-service.sh
   ```

2. Run the uninstallation script:
   ```bash
   sudo ./uninstall-service.sh
   ```

This will:
- Stop and disable the service
- Remove the service files
- Backup log files to `/tmp/ft8logs-backup-[timestamp]/`
- Remove the installation directory
- Remove the service user

## Troubleshooting

### Service Won't Start

1. Check the service status:
   ```bash
   sudo systemctl status ft8logs
   ```

2. Check the logs:
   ```bash
   sudo journalctl -u ft8logs -n 50
   ```

3. Check file permissions:
   ```bash
   ls -la /opt/ft8logs/
   ```

### Common Issues

- **Permission denied**: Ensure the `ft8logs` user owns all files in `/opt/ft8logs/`
- **Python dependencies**: Ensure all packages from `requirements.txt` are installed in the virtual environment
- **Port conflicts**: Make sure port 5019 (web) and 5140 (UDP) are not used by other services

### Manual Testing

To test the application manually:
```bash
sudo -u ft8logs /opt/ft8logs/.venv/bin/python /opt/ft8logs/ft8logs.py
```

## Security

The service runs with restricted permissions:
- Dedicated system user with no shell access
- Private temporary directory
- Read-only system directories
- Network access limited to required protocols
- No new privileges allowed

## Backup

Important files to backup:
- `/opt/ft8logs/logs/` - Contains log data and cache files
- `/etc/systemd/system/ft8logs.service` - Service configuration

## Updates

To update the application:

1. Stop the service:
   ```bash
   sudo systemctl stop ft8logs
   ```

2. Update the files:
   ```bash
   sudo cp ft8logs.py /opt/ft8logs/
   # Copy other updated files as needed
   ```

3. Update dependencies if needed:
   ```bash
   sudo -u ft8logs /opt/ft8logs/.venv/bin/pip install -r /opt/ft8logs/requirements.txt
   ```

4. Restart the service:
   ```bash
   sudo systemctl start ft8logs
   ```
