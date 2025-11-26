"""Configuration manager for machines.yaml."""

import yaml
import os
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages machine configurations from machines.yaml."""

    def __init__(self, config_path: str = "machines.yaml"):
        """
        Initialize config manager.

        Args:
            config_path: Path to machines.yaml file
        """
        self.config_path = config_path
        self._ensure_config_exists()

    def _ensure_config_exists(self):
        """Create machines.yaml if it doesn't exist."""
        if not os.path.exists(self.config_path):
            logger.warning(f"Config file {self.config_path} not found, creating empty config")
            self._save_config({"machines": []})

    def _load_config(self) -> Dict:
        """
        Load configuration from machines.yaml.

        Returns:
            Dict containing configuration data
        """
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
                if 'machines' not in config:
                    config['machines'] = []
                return config
        except Exception as e:
            logger.error(f"Failed to load config: {str(e)}")
            return {"machines": []}

    def _save_config(self, config: Dict):
        """
        Save configuration to machines.yaml.

        Args:
            config: Configuration data to save
        """
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {str(e)}")
            raise

    def get_all_machines(self) -> List[Dict]:
        """
        Get all machine configurations.

        Returns:
            List of machine configuration dictionaries
        """
        config = self._load_config()
        return config.get('machines', [])

    def get_machine(self, machine_id: str) -> Optional[Dict]:
        """
        Get a specific machine configuration by ID.

        Args:
            machine_id: Machine ID to retrieve

        Returns:
            Machine configuration dictionary, or None if not found
        """
        machines = self.get_all_machines()
        for machine in machines:
            if machine.get('id') == machine_id:
                return machine
        return None

    def add_machine(self, machine_data: Dict) -> bool:
        """
        Add a new machine configuration.

        Args:
            machine_data: Machine configuration dictionary

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Validate required fields
            required_fields = ['id', 'name', 'host', 'ssh_user', 'backup_type']
            for field in required_fields:
                if field not in machine_data:
                    logger.error(f"Missing required field: {field}")
                    return False

            # Check if machine ID already exists
            if self.get_machine(machine_data['id']):
                logger.error(f"Machine with ID {machine_data['id']} already exists")
                return False

            # Set defaults
            machine_data.setdefault('ssh_port', 22)
            machine_data.setdefault('retention_days', 30)

            # Add machine to config
            config = self._load_config()
            config['machines'].append(machine_data)
            self._save_config(config)

            logger.info(f"Added machine: {machine_data['id']}")
            return True

        except Exception as e:
            logger.error(f"Failed to add machine: {str(e)}")
            return False

    def update_machine(self, machine_id: str, machine_data: Dict) -> bool:
        """
        Update an existing machine configuration.

        Args:
            machine_id: ID of machine to update
            machine_data: Updated machine configuration

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            config = self._load_config()
            machines = config.get('machines', [])

            for i, machine in enumerate(machines):
                if machine.get('id') == machine_id:
                    # Preserve the ID
                    machine_data['id'] = machine_id
                    machines[i] = machine_data
                    config['machines'] = machines
                    self._save_config(config)
                    logger.info(f"Updated machine: {machine_id}")
                    return True

            logger.error(f"Machine {machine_id} not found")
            return False

        except Exception as e:
            logger.error(f"Failed to update machine: {str(e)}")
            return False

    def delete_machine(self, machine_id: str) -> bool:
        """
        Delete a machine configuration.

        Args:
            machine_id: ID of machine to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            config = self._load_config()
            machines = config.get('machines', [])

            initial_count = len(machines)
            machines = [m for m in machines if m.get('id') != machine_id]

            if len(machines) == initial_count:
                logger.error(f"Machine {machine_id} not found")
                return False

            config['machines'] = machines
            self._save_config(config)
            logger.info(f"Deleted machine: {machine_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete machine: {str(e)}")
            return False

    def machine_exists(self, machine_id: str) -> bool:
        """
        Check if a machine exists.

        Args:
            machine_id: Machine ID to check

        Returns:
            bool: True if machine exists, False otherwise
        """
        return self.get_machine(machine_id) is not None
