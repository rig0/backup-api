"""Backup API - Pull-based backup system with n8n integration."""

import importlib
import logging
import os
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
from flask import Flask, jsonify, request

from utils.config import ConfigManager

# Load environment variables
load_dotenv()

# Logging Configuration

# Create logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(module)s: %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Rotating file handler
file_handler = RotatingFileHandler(
    "backup-api.log",
    maxBytes=3 * 1024 * 1024,  # 3 MB per file
    backupCount=3,  # Keep 3 backups
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

app = Flask(__name__)

# Initialize configuration manager
config_manager = ConfigManager("machines.yaml")

# Get API token from environment
API_TOKEN = os.getenv("API_TOKEN")

if not API_TOKEN:
    logger.error("API_TOKEN not set in environment variables")
    raise ValueError("API_TOKEN must be set in .env file")


# Bearer token authentication decorator
def require_bearer_token(f):
    """Decorator to require bearer token authentication."""

    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            logger.warning("Missing Authorization header")
            return jsonify({"error": "Missing Authorization header"}), 401

        if not auth_header.startswith("Bearer "):
            logger.warning("Invalid Authorization header format")
            return jsonify({"error": "Invalid Authorization header format"}), 401

        token = auth_header.replace("Bearer ", "")

        if token != API_TOKEN:
            logger.warning(f"Invalid token attempt from {request.remote_addr}")
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__
    return wrapper


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint (no auth required)."""
    # Read version from VERSION file
    version = "unknown"
    try:
        with open("VERSION", "r") as f:
            version = f.read().strip()
    except Exception:
        pass

    return (
        jsonify({"status": "healthy", "service": "backup-api", "version": version}),
        200,
    )


@app.route("/api/backup", methods=["POST"])
@require_bearer_token
def trigger_backup():
    """
    Trigger a backup for a specific machine.

    Request body:
    {
        "machine_id": "cloud-server-1"
    }
    """
    try:
        data = request.get_json()

        if not data or "machine_id" not in data:
            return jsonify({"error": "machine_id is required"}), 400

        machine_id = data["machine_id"]
        logger.info(f"Backup requested for machine: {machine_id}")

        # Get machine configuration
        machine_config = config_manager.get_machine(machine_id)

        if not machine_config:
            logger.error(f"Machine not found: {machine_id}")
            return jsonify({"error": f"Machine {machine_id} not found"}), 404

        # Get backup type
        backup_type = machine_config.get("backup_type")

        if not backup_type:
            logger.error(f"backup_type not configured for machine {machine_id}")
            return jsonify({"error": "backup_type not configured for machine"}), 400

        # Dynamically load backup module
        try:
            module = importlib.import_module(f"modules.{backup_type}")
            backup_class_name = f"{backup_type.capitalize()}Backup"
            backup_class = getattr(module, backup_class_name)
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to load backup module '{backup_type}': {str(e)}")
            return jsonify({"error": f"Invalid backup_type: {backup_type}"}), 400

        # Execute backup
        backup_instance = backup_class()
        success, message = backup_instance.execute_backup(machine_config)

        # To do: Update this to report number of stacks backed up
        if success:
            logger.info(f"Backup successful for {machine_id}: {message}")
            return jsonify({"success": True, "message": message}), 200
        else:
            logger.error(f"Backup failed for {machine_id}: {message}")
            return jsonify({"success": False, "error": message}), 500

    except Exception as e:
        logger.error(f"Unexpected error during backup: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@app.route("/api/machines", methods=["GET"])
@require_bearer_token
def get_machines():
    """Get all machine configurations."""
    try:
        machines = config_manager.get_all_machines()
        logger.info(f"Retrieved {len(machines)} machines")
        return jsonify({"machines": machines}), 200

    except Exception as e:
        logger.error(f"Failed to get machines: {str(e)}")
        return jsonify({"error": "Failed to retrieve machines"}), 500


@app.route("/api/machines/<machine_id>", methods=["GET"])
@require_bearer_token
def get_machine(machine_id):
    """Get a specific machine configuration."""
    try:
        machine = config_manager.get_machine(machine_id)

        if not machine:
            return jsonify({"error": f"Machine {machine_id} not found"}), 404

        return jsonify({"machine": machine}), 200

    except Exception as e:
        logger.error(f"Failed to get machine {machine_id}: {str(e)}")
        return jsonify({"error": "Failed to retrieve machine"}), 500


@app.route("/api/machines", methods=["POST"])
@require_bearer_token
def add_machine():
    """
    Add a new machine configuration.

    Request body:
    {
        "id": "cloud-server-1",
        "name": "Cloud Server 1",
        "host": "203.0.113.45",
        "ssh_port": 22,
        "ssh_user": "root",
        "ssh_key_path": "/root/.ssh/cloud-server-1",
        "backup_type": "dockge",
        "retention_count": 30,
        "remote_tmp_dir": "/home/rambo/dev-stack",
        "local_backup_dir": "/mnt/nasty/Backups/Dockge/cloud-server-1"
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Request body is required"}), 400

        # Validate required fields
        required_fields = [
            "id",
            "name",
            "host",
            "ssh_user",
            "backup_type",
            "local_backup_dir",
        ]
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            return (
                jsonify(
                    {"error": f'Missing required fields: {", ".join(missing_fields)}'}
                ),
                400,
            )

        # Add machine
        success = config_manager.add_machine(data)

        if success:
            logger.info(f"Added machine: {data['id']}")
            return (
                jsonify(
                    {
                        "success": True,
                        "message": f'Machine {data["id"]} added successfully',
                    }
                ),
                201,
            )
        else:
            return jsonify({"error": "Failed to add machine (may already exist)"}), 400

    except Exception as e:
        logger.error(f"Failed to add machine: {str(e)}")
        return jsonify({"error": "Failed to add machine", "details": str(e)}), 500


@app.route("/api/machines/<machine_id>", methods=["PUT"])
@require_bearer_token
def update_machine(machine_id):
    """Update an existing machine configuration."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Request body is required"}), 400

        success = config_manager.update_machine(machine_id, data)

        if success:
            logger.info(f"Updated machine: {machine_id}")
            return (
                jsonify(
                    {
                        "success": True,
                        "message": f"Machine {machine_id} updated successfully",
                    }
                ),
                200,
            )
        else:
            return jsonify({"error": f"Machine {machine_id} not found"}), 404

    except Exception as e:
        logger.error(f"Failed to update machine {machine_id}: {str(e)}")
        return jsonify({"error": "Failed to update machine", "details": str(e)}), 500


@app.route("/api/machines/<machine_id>", methods=["DELETE"])
@require_bearer_token
def delete_machine(machine_id):
    """Delete a machine configuration."""
    try:
        success = config_manager.delete_machine(machine_id)

        if success:
            logger.info(f"Deleted machine: {machine_id}")
            return (
                jsonify(
                    {
                        "success": True,
                        "message": f"Machine {machine_id} deleted successfully",
                    }
                ),
                200,
            )
        else:
            return jsonify({"error": f"Machine {machine_id} not found"}), 404

    except Exception as e:
        logger.error(f"Failed to delete machine {machine_id}: {str(e)}")
        return jsonify({"error": "Failed to delete machine", "details": str(e)}), 500


# Keep legacy /backup endpoint for backward compatibility (if needed)
@app.route("/backup", methods=["POST"])
@require_bearer_token
def legacy_backup():
    """
    Legacy backup endpoint (for backward compatibility).
    This endpoint is deprecated - use /api/backup instead.
    """
    logger.warning("Legacy /backup endpoint called - this is deprecated")
    return (
        jsonify(
            {
                "error": "This endpoint is deprecated",
                "message": "Please use /api/backup with machine_id instead",
            }
        ),
        410,
    )


if __name__ == "__main__":
    logger.info("Starting Backup API...")
    logger.info(f"Loaded {len(config_manager.get_all_machines())} machine configurations")

    # Suppress Flask's default logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)

    app.run(host="0.0.0.0", port=7792, debug=False)
