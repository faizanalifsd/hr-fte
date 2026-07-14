"""
Database Configuration.

As per execution_plan.md:
- Database credentials stored in secure configuration
- Must not be publicly accessible
- Must be excluded from version control
- Production should use environment variables
"""

import os
from typing import Dict, Optional


class DatabaseConfig:
    """
    Database configuration manager.

    Loads database credentials from environment variables.
    """

    def __init__(self):
        """Initialize database configuration from environment."""
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = int(os.getenv("DB_PORT", "3306"))
        self.user = os.getenv("DB_USER")
        self.password = os.getenv("DB_PASS")
        self.database = os.getenv("DB_NAME")

        # Validate required fields
        if not all([self.user, self.password, self.database]):
            raise ValueError(
                "Database configuration incomplete. "
                "Please set DB_USER, DB_PASS, and DB_NAME in environment variables."
            )

    def get_connection_url(self) -> str:
        """
        Get SQLAlchemy connection URL.

        Returns:
            MySQL connection string
        """
        return f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    def get_connection_params(self) -> Dict[str, str]:
        """
        Get connection parameters as dictionary.

        Returns:
            Connection parameters dict
        """
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database
        }

    @staticmethod
    def from_url(url: str) -> 'DatabaseConfig':
        """
        Create config from DATABASE_URL string.

        Alternative initialization method for cloud deployments.

        Args:
            url: Database URL (e.g., from DATABASE_URL env var)

        Returns:
            DatabaseConfig instance
        """
        # For now, just return default config
        # In production, parse the URL
        return DatabaseConfig()


# Example PHP-style configuration format (for reference)
# This would be in /config/database.php if using PHP
DATABASE_PHP_CONFIG_EXAMPLE = """
<?php
return [
    'host' => getenv('DB_HOST') ?: 'localhost',
    'port' => getenv('DB_PORT') ?: 3306,
    'database' => getenv('DB_NAME'),
    'username' => getenv('DB_USER'),
    'password' => getenv('DB_PASS'),
    'charset' => 'utf8mb4',
    'collation' => 'utf8mb4_unicode_ci',
];
?>
"""
