"""Dockge backup module - handles backing up Dockge stacks."""

import glob
import logging
import os
from datetime import datetime
from typing import Dict, Tuple

from utils.ssh_client import SSHClient

logger = logging.getLogger(__name__)


class DockgeBackup:
    """Handles Dockge stack backups via SSH."""

    def __init__(self):
        """Initialize DockgeBackup module."""
        self.stacks_dir = "/opt/stacks"
        self.dockge_dir = "/opt/dockge"

    def execute_backup(self, machine_config: Dict) -> Tuple[bool, str]:
        """
        Execute complete backup workflow for a Dockge machine.

        Args:
            machine_config: Machine configuration dictionary from machines.yaml

        Returns:
            Tuple of (success: bool, message: str)
        """
        machine_id = machine_config["id"]
        logger.info(f"Starting Dockge backup for machine: {machine_id}")

        # Initialize SSH client
        ssh_client = SSHClient(
            host=machine_config["host"],
            port=machine_config.get("ssh_port", 22),
            username=machine_config["ssh_user"],
            key_path=machine_config.get("ssh_key_path"),
            password=machine_config.get("ssh_password"),
        )

        try:
            # Connect to remote machine
            if not ssh_client.connect():
                return False, f"Failed to connect to {machine_config['host']}"

            # Create timestamp
            timestamp = datetime.now().strftime("%Y_%j_%H%M%S")

            # Get remote_tmp_dir from machine config or use default
            remote_tmp_dir = machine_config.get("remote_tmp_dir", "/tmp/dockge-backup")

            # Create backup directory on remote machine
            success, message = self._create_remote_backup_dir(ssh_client, remote_tmp_dir)
            if not success:
                return False, message

            # Backup stacks
            success, message = self._backup_stacks(ssh_client, remote_tmp_dir, timestamp)
            if not success:
                return False, message

            # Backup dockge directory
            success, message = self._backup_dockge(ssh_client, remote_tmp_dir, timestamp)
            if not success:
                return False, message

            # Download backups to NAS
            local_backup_dir = machine_config.get("local_backup_dir")
            if not local_backup_dir:
                return False, "local_backup_dir not configured for machine"

            success, message = self._download_backups(
                ssh_client, remote_tmp_dir, local_backup_dir
            )
            if not success:
                return False, message

            # Verify backups
            success, message = self._verify_backups(local_backup_dir)
            if not success:
                return False, message

            # Cleanup remote machine
            success, message = self._cleanup_remote(ssh_client, remote_tmp_dir)
            if not success:
                logger.warning(f"Cleanup warning: {message}")

            # Cleanup old backups on NAS
            retention_count = machine_config.get("retention_count", 30)
            self._cleanup_old_backups(local_backup_dir, keep=retention_count)

            logger.info(f"Dockge backup completed successfully for {machine_id}")
            return True, f"Backup completed successfully for {machine_id}"

        except Exception as e:
            logger.error(f"Backup failed for {machine_id}: {str(e)}")
            return False, f"Backup failed: {str(e)}"

        finally:
            ssh_client.close()

    def _create_remote_backup_dir(
        self, ssh_client: SSHClient, backup_dir: str
    ) -> Tuple[bool, str]:
        """Create backup directory on remote machine."""
        logger.info(f"Creating backup directory: {backup_dir}")
        exit_code, stdout, stderr = ssh_client.exec_command(f'mkdir -p "{backup_dir}"')

        if exit_code == 0:
            return True, "Backup directory created"
        else:
            return False, f"Failed to create backup directory: {stderr}"

    def _backup_stacks(
        self, ssh_client: SSHClient, backup_dir: str, timestamp: str
    ) -> Tuple[bool, str]:
        """Backup each stack in /opt/stacks."""
        logger.info(f"Backing up stacks from {self.stacks_dir}")

        # Get list of stack directories
        exit_code, stdout, stderr = ssh_client.exec_command(
            f'find "{self.stacks_dir}" -maxdepth 1 -type d ! -path "{self.stacks_dir}"'
        )

        if exit_code != 0:
            return False, f"Failed to list stacks: {stderr}"

        stack_dirs = [line.strip() for line in stdout.strip().split("\n") if line.strip()]

        if not stack_dirs:
            logger.info("No stacks found to backup")
            return True, "No stacks found"

        # Backup each stack
        for stack_path in stack_dirs:
            stack_name = os.path.basename(stack_path)
            logger.info(f"Backing up stack: {stack_name}")

            # Create directory for this stack's backups
            stack_backup_dir = f"{backup_dir}/{stack_name}"
            ssh_client.exec_command(f'mkdir -p "{stack_backup_dir}"')

            # Check if this is fireshare (exclude videos folder)
            if stack_name == "fireshare":
                tar_command = (
                    f'tar -czf "{stack_backup_dir}/{stack_name}_{timestamp}.tar.gz" '
                    f'--exclude="videos" -C "{self.stacks_dir}" "{stack_name}"'
                )
            else:
                tar_command = (
                    f'tar -czf "{stack_backup_dir}/{stack_name}_{timestamp}.tar.gz" '
                    f'-C "{self.stacks_dir}" "{stack_name}"'
                )

            exit_code, stdout, stderr = ssh_client.exec_command(tar_command, timeout=600)

            if exit_code != 0:
                logger.error(f"Failed to backup stack {stack_name}: {stderr}")
                return False, f"Failed to backup stack {stack_name}"

            logger.info(f"Successfully backed up stack: {stack_name}")

        return True, f"Backed up {len(stack_dirs)} stacks"

    def _backup_dockge(
        self, ssh_client: SSHClient, backup_dir: str, timestamp: str
    ) -> Tuple[bool, str]:
        """Backup /opt/dockge directory."""
        logger.info(f"Backing up Dockge directory: {self.dockge_dir}")

        # Check if dockge directory exists
        exit_code, stdout, stderr = ssh_client.exec_command(
            f'[ -d "{self.dockge_dir}" ] && echo "exists"'
        )

        if exit_code != 0 or "exists" not in stdout:
            logger.warning(f"Dockge directory {self.dockge_dir} does not exist")
            return True, "Dockge directory not found (skipped)"

        # Create dockge backup directory
        dockge_backup_dir = f"{backup_dir}/dockge"
        ssh_client.exec_command(f'mkdir -p "{dockge_backup_dir}"')

        # Create tar.gz of dockge directory
        tar_command = (
            f'tar -czf "{dockge_backup_dir}/dockge_{timestamp}.tar.gz" '
            f'-C "$(dirname "{self.dockge_dir}")" "$(basename "{self.dockge_dir}")"'
        )

        exit_code, stdout, stderr = ssh_client.exec_command(tar_command, timeout=600)

        if exit_code != 0:
            logger.error(f"Failed to backup Dockge: {stderr}")
            return False, "Failed to backup Dockge directory"

        logger.info("Successfully backed up Dockge directory")
        return True, "Backed up Dockge directory"

    def _download_backups(
        self, ssh_client: SSHClient, remote_backup_dir: str, local_backup_dir: str
    ) -> Tuple[bool, str]:
        """Download backups from remote machine to NAS via SFTP."""
        logger.info(f"Downloading backups from {remote_backup_dir} to {local_backup_dir}")

        # Create local directory if it doesn't exist
        os.makedirs(local_backup_dir, exist_ok=True)

        # Download entire backup directory
        success = ssh_client.download_directory(remote_backup_dir, local_backup_dir)

        if success:
            # Set permissions (770)
            try:
                import subprocess

                subprocess.run(["chmod", "-R", "770", local_backup_dir], check=True)
                logger.info(f"Set permissions on {local_backup_dir}")
            except Exception as e:
                logger.warning(f"Failed to set permissions: {str(e)}")

            return True, "Backups downloaded successfully"
        else:
            return False, "Failed to download backups"

    def _verify_backups(self, local_backup_dir: str) -> Tuple[bool, str]:
        """Verify downloaded backups exist and have reasonable size."""
        logger.info(f"Verifying backups in {local_backup_dir}")

        # Find all .tar.gz files
        backup_files = glob.glob(
            os.path.join(local_backup_dir, "**/*.tar.gz"), recursive=True
        )

        if not backup_files:
            return False, "No backup files found after download"

        # Check each file
        for backup_file in backup_files:
            if not os.path.exists(backup_file):
                return False, f"Backup file missing: {backup_file}"

            size = os.path.getsize(backup_file)
            if size < 100:  # Less than 100 bytes is suspicious
                return False, f"Backup file too small: {backup_file} ({size} bytes)"

            logger.info(f"Verified: {os.path.basename(backup_file)} ({size} bytes)")

        return True, f"Verified {len(backup_files)} backup files"

    def _cleanup_remote(
        self, ssh_client: SSHClient, remote_tmp_dir: str
    ) -> Tuple[bool, str]:
        """Delete backup directory on remote machine."""
        logger.info(f"Cleaning up remote backup directory: {remote_tmp_dir}")

        success = ssh_client.delete_remote_directory(remote_tmp_dir)

        if success:
            return True, "Remote cleanup successful"
        else:
            return False, "Failed to cleanup remote backup directory"

    def _cleanup_old_backups(self, local_backup_dir: str, keep: int = 30):
        """
        Keep only the most recent N backups in each subdirectory.

        Args:
            local_backup_dir: Root directory containing backups
            keep: Number of backups to keep (default 30)
        """
        logger.info(
            f"Cleaning up old backups in {local_backup_dir}, keeping {keep} most recent"
        )

        try:
            # Walk through all subdirectories
            for root, dirs, files in os.walk(local_backup_dir):
                # Find all .tar.gz files in this directory
                backup_files = [f for f in files if f.endswith(".tar.gz")]

                if len(backup_files) <= keep:
                    continue

                # Get full paths and sort by modification time (newest first)
                full_paths = [os.path.join(root, f) for f in backup_files]
                full_paths.sort(key=os.path.getmtime, reverse=True)

                # Delete old backups
                old_backups = full_paths[keep:]
                for old_backup in old_backups:
                    try:
                        os.remove(old_backup)
                        logger.info(f"Deleted old backup: {old_backup}")
                    except Exception as e:
                        logger.error(f"Failed to delete {old_backup}: {str(e)}")

        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
