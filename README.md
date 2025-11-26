# Backup-API

A pull-based backup system that runs on your NAS and initiates SSH connections to remote machines to perform backups. Designed for integration with n8n for centralized scheduling and monitoring.

## Architecture

The backup-api initiates connections to remote machines to perform backups:

```
n8n (local) → backup-api (local) → SSH to remote → run backup → download → cleanup
```

**Benefits:**
- No API exposure needed - stays internal
- Centralized scheduling via n8n
- Centralized monitoring and error handling
- Same mechanism for local and cloud machines

## Prerequisites

```bash
sudo apt install python3-full python3-venv python3-pip git
```

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/rig0/backup-api
cd backup-api
```

### 2. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
nano .env
```

Generate a secure API token:
```bash
openssl rand -hex 32
```

Update `.env`:
```bash
API_TOKEN=your_generated_token_here
```

### 4. Configure SSH Keys

For each remote machine, generate and copy SSH key:

```bash
# Generate key
ssh-keygen -t ed25519 -f ~/.ssh/cloud-server-1 -C "backup-api"

# Copy to remote machine
ssh-copy-id -i ~/.ssh/cloud-server-1.pub root@remote-host
```

### 5. Configure Machines

Edit `machines.yaml` to add your backup sources:

```yaml
machines:
  - id: "cloud-server-1"
    name: "Cloud Server 1"
    host: "203.0.113.45"
    ssh_port: 22
    ssh_user: "root"
    ssh_key_path: "/home/user/.ssh/cloud-server-1"
    backup_type: "dockge"
    retention_days: 90
    backup_dir: "/tmp/stack-backup"
    nas_directory: "/mnt/drive_0/backups/dockge/cloud-server-1""
```

Or add machines via API:

```bash
curl -X POST http://localhost:7792/api/machines \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "cloud-server-1",
    "name": "Cloud Server 1",
    "host": "203.0.113.45",
    "ssh_port": 22,
    "ssh_user": "root",
    "ssh_key_path": "/home/user/.ssh/cloud-server-1",
    "backup_type": "dockge",
    "retention_days": 90,
    "backup_dir": "/tmp/stack-backup"",
    "nas_directory": "/mnt/drive_0/backups/dockge/cloud-server-1""
  }'
```

## Starting the API

### Manual Start

```bash
chmod +x ./start-api.sh
./start-api.sh
```

### System Service (Auto-start)

Create `/etc/systemd/system/backup-api.service`:

```ini
[Unit]
Description=Backup API
After=network.target

[Service]
User=user
Group=user
WorkingDirectory=/home/user/backup-api
ExecStart=/home/user/backup-api/venv/bin/python api.py
Restart=always
Environment="PATH=/home/user/backup-api/venv/bin:/usr/bin"

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable backup-api
sudo systemctl start backup-api
sudo systemctl status backup-api
```

## API Endpoints

All endpoints require `Authorization: Bearer <API_TOKEN>` header.

### Health Check

```bash
curl http://localhost:7792/health
```

### Trigger Backup

```bash
curl -X POST http://localhost:7792/api/backup \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"machine_id": "cloud-server-1"}'
```

### Machine Management

**List all machines:**
```bash
curl http://localhost:7792/api/machines \
  -H "Authorization: Bearer ${API_TOKEN}"
```

**Get specific machine:**
```bash
curl http://localhost:7792/api/machines/cloud-server-1 \
  -H "Authorization: Bearer ${API_TOKEN}"
```

**Update machine:**
```bash
curl -X PUT http://localhost:7792/api/machines/cloud-server-1 \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated Name", "retention_days": 60}'
```

**Delete machine:**
```bash
curl -X DELETE http://localhost:7792/api/machines/cloud-server-1 \
  -H "Authorization: Bearer ${API_TOKEN}"
```

## n8n Integration

### n8n Environment Variables

Add to n8n environment:
```
API_TOKEN=your_generated_token_here
BACKUP_API_URL=http://backup-api-host:7792
```

### Example n8n Workflow

**Schedule Node** (Cron: `0 2 * * *` - Daily at 2 AM)
  ↓
**HTTP Request Node** (Trigger Backup)
```json
{
  "method": "POST",
  "url": "{{$env.BACKUP_API_URL}}/api/backup",
  "headers": {
    "Authorization": "Bearer {{$env.API_TOKEN}}",
    "Content-Type": "application/json"
  },
  "body": {
    "machine_id": "cloud-server-1"
  }
}
```
  ↓
**IF Node** (Check success)
  ↓
**Pushover Notification Node** (On success/failure)

## Project Structure

```
backup-api/
├── api.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── machines.yaml          # Machine configurations
├── .env                   # Environment variables (API_TOKEN)
├── modules/
│   ├── __init__.py
│   └── dockge.py         # Dockge backup module
└── utils/
    ├── __init__.py
    ├── ssh_client.py     # SSH client wrapper
    └── config.py         # Configuration manager
```

## Adding New Backup Types

Create a new module in `modules/` directory:

```python
# modules/postgres.py
class PostgresBackup:
    def execute_backup(self, machine_config):
        # Implementation
        return (success, message)
```

Configure machine with `backup_type: "postgres"`.

## Logs

View logs:
```bash
tail -f backup-api.log
```

Or with systemd:
```bash
sudo journalctl -u backup-api -f
```

## Troubleshooting

### SSH Connection Issues

Test SSH connectivity manually:
```bash
ssh -i /home/user/.ssh/cloud-server-1 root@remote-host
```

### Permission Issues

Ensure SSH key has correct permissions:
```bash
chmod 600 /home/user/.ssh/cloud-server-1
```

### API Not Starting

Check if port 7792 is available:
```bash
sudo netstat -tulpn | grep 7792
```
