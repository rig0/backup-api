"""SSH client wrapper for remote command execution and file transfers."""

import paramiko
import os
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class SSHClient:
    """Wrapper for paramiko SSH client with simplified interface."""

    def __init__(self, host: str, port: int = 22, username: str = "root",
                 key_path: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize SSH client.

        Args:
            host: Remote host address
            port: SSH port (default 22)
            username: SSH username (default root)
            key_path: Path to SSH private key file
            password: SSH password (used if key_path not provided)
        """
        self.host = host
        self.port = port
        self.username = username
        self.key_path = key_path
        self.password = password
        self.client = None
        self.sftp = None

    def connect(self) -> bool:
        """
        Establish SSH connection.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Prepare connection parameters
            connect_params = {
                'hostname': self.host,
                'port': self.port,
                'username': self.username,
                'timeout': 30
            }

            # Use SSH key if provided, otherwise use password
            if self.key_path and os.path.exists(self.key_path):
                connect_params['key_filename'] = self.key_path
                logger.info(f"Connecting to {self.host}:{self.port} with SSH key")
            elif self.password:
                connect_params['password'] = self.password
                logger.info(f"Connecting to {self.host}:{self.port} with password")
            else:
                logger.error("No authentication method provided (key or password)")
                return False

            self.client.connect(**connect_params)
            logger.info(f"Successfully connected to {self.host}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to {self.host}:{self.port}: {str(e)}")
            return False

    def exec_command(self, command: str, timeout: int = 300) -> Tuple[int, str, str]:
        """
        Execute command on remote host.

        Args:
            command: Command to execute
            timeout: Command timeout in seconds (default 300)

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        if not self.client:
            logger.error("Not connected to remote host")
            return (-1, "", "Not connected")

        try:
            logger.info(f"Executing command: {command}")
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)

            exit_code = stdout.channel.recv_exit_status()
            stdout_str = stdout.read().decode('utf-8')
            stderr_str = stderr.read().decode('utf-8')

            if exit_code == 0:
                logger.info(f"Command succeeded")
            else:
                logger.error(f"Command failed with exit code {exit_code}: {stderr_str}")

            return (exit_code, stdout_str, stderr_str)

        except Exception as e:
            logger.error(f"Failed to execute command: {str(e)}")
            return (-1, "", str(e))

    def download_file(self, remote_path: str, local_path: str) -> bool:
        """
        Download a file from remote host via SFTP.

        Args:
            remote_path: Path to file on remote host
            local_path: Local destination path

        Returns:
            bool: True if download successful, False otherwise
        """
        try:
            if not self.sftp:
                self.sftp = self.client.open_sftp()

            logger.info(f"Downloading {remote_path} to {local_path}")

            # Create local directory if it doesn't exist
            local_dir = os.path.dirname(local_path)
            if local_dir:
                os.makedirs(local_dir, exist_ok=True)

            self.sftp.get(remote_path, local_path)
            logger.info(f"Successfully downloaded {remote_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to download {remote_path}: {str(e)}")
            return False

    def download_directory(self, remote_dir: str, local_dir: str) -> bool:
        """
        Recursively download a directory from remote host via SFTP.

        Args:
            remote_dir: Path to directory on remote host
            local_dir: Local destination directory

        Returns:
            bool: True if download successful, False otherwise
        """
        try:
            if not self.sftp:
                self.sftp = self.client.open_sftp()

            logger.info(f"Downloading directory {remote_dir} to {local_dir}")
            os.makedirs(local_dir, exist_ok=True)

            # List remote directory
            for item in self.sftp.listdir_attr(remote_dir):
                remote_path = os.path.join(remote_dir, item.filename)
                local_path = os.path.join(local_dir, item.filename)

                if self._is_directory(item):
                    # Recursively download subdirectory
                    self.download_directory(remote_path, local_path)
                else:
                    # Download file
                    self.sftp.get(remote_path, local_path)
                    logger.info(f"Downloaded {remote_path}")

            logger.info(f"Successfully downloaded directory {remote_dir}")
            return True

        except Exception as e:
            logger.error(f"Failed to download directory {remote_dir}: {str(e)}")
            return False

    def delete_remote_file(self, remote_path: str) -> bool:
        """
        Delete a file on remote host.

        Args:
            remote_path: Path to file on remote host

        Returns:
            bool: True if deletion successful, False otherwise
        """
        try:
            if not self.sftp:
                self.sftp = self.client.open_sftp()

            logger.info(f"Deleting remote file {remote_path}")
            self.sftp.remove(remote_path)
            logger.info(f"Successfully deleted {remote_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete {remote_path}: {str(e)}")
            return False

    def delete_remote_directory(self, remote_dir: str) -> bool:
        """
        Recursively delete a directory on remote host.

        Args:
            remote_dir: Path to directory on remote host

        Returns:
            bool: True if deletion successful, False otherwise
        """
        exit_code, stdout, stderr = self.exec_command(f'rm -rf "{remote_dir}"')
        return exit_code == 0

    def _is_directory(self, attr) -> bool:
        """Check if paramiko file attribute represents a directory."""
        import stat
        return stat.S_ISDIR(attr.st_mode)

    def close(self):
        """Close SSH connection and SFTP session."""
        if self.sftp:
            self.sftp.close()
            self.sftp = None

        if self.client:
            self.client.close()
            self.client = None
            logger.info(f"Closed connection to {self.host}:{self.port}")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
