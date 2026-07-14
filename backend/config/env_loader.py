"""
Environment Variable Loader.

Loads environment variables from .env file.
"""

import os
from pathlib import Path
from typing import Optional


def load_environment(env_file: Optional[str] = None):
    """
    Load environment variables from .env file.

    Args:
        env_file: Path to .env file (default: .env in project root)
    """
    if env_file is None:
        # Look for .env in project root
        project_root = Path(__file__).parent.parent.parent
        env_file = project_root / ".env"

    if not os.path.exists(env_file):
        print(f"Warning: .env file not found at {env_file}")
        print("Please create .env file from .env.example")
        return

    # Load .env file
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
        print(f"✓ Environment variables loaded from {env_file}")
    except ImportError:
        print("Warning: python-dotenv not installed. Install with: pip install python-dotenv")
        # Fallback: manual parsing
        _load_env_manual(env_file)


def _load_env_manual(env_file: str):
    """
    Manually load .env file (fallback if python-dotenv not available).

    Args:
        env_file: Path to .env file
    """
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                os.environ[key] = value

    print(f"✓ Environment variables loaded manually from {env_file}")


def validate_required_env_vars() -> bool:
    """
    Validate that all required environment variables are set.

    As per execution_plan.md:
    - If any required variable is missing → abort execution

    Returns:
        True if all required vars present, False otherwise
    """
    required_vars = [
        # Database
        "DATABASE_URL",  # Or individual DB_* vars
        # MCP APIs
        "APIFY_API_KEY",
        "GMAIL_CLIENT_ID",
        "GMAIL_CLIENT_SECRET",
        "GMAIL_REFRESH_TOKEN",
        # Note: OPENROUTER_API_KEY and GROQ_API_KEY are optional
        # Sub-agents cascade: OpenRouter → Groq → rule-based fallback
    ]

    missing = []

    for var in required_vars:
        if var == "DATABASE_URL":
            # DATABASE_URL or individual DB_* vars required
            if not os.getenv("DATABASE_URL"):
                if not all([os.getenv("DB_HOST"), os.getenv("DB_USER"),
                           os.getenv("DB_PASS"), os.getenv("DB_NAME")]):
                    missing.append(var)
        elif not os.getenv(var):
            missing.append(var)

    if missing:
        print("\n❌ MISSING REQUIRED ENVIRONMENT VARIABLES:")
        for var in missing:
            print(f"   - {var}")
        print("\nPlease set these variables in your .env file")
        return False

    print("✓ All required environment variables present")
    return True
