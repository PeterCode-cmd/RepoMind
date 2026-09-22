"""Module with intentionally insecure patterns used by RepoMind's test-suite."""

import hashlib
import os
import pickle
import subprocess
import tempfile

import yaml

DATABASE_PASSWORD = "super-secret-password"


def run_command(user_input: str) -> str:
    """Run a command with shell expansion (intentionally unsafe)."""
    completed = subprocess.run(f"echo {user_input}", shell=True, check=False)
    return completed.stdout.decode()


def run_system(command: str) -> int:
    """Run a command through os.system (intentionally unsafe)."""
    return os.system(command)


def load_payload(blob: bytes) -> object:
    """Deserialize untrusted data (intentionally unsafe)."""
    return pickle.loads(blob)


def load_config(text: str) -> object:
    """Parse YAML without a safe loader (intentionally unsafe)."""
    return yaml.load(text)


def weak_digest(data: bytes) -> str:
    """Hash with MD5 (intentionally weak)."""
    return hashlib.md5(data).hexdigest()


def temporary_path() -> str:
    """Create a temporary file name insecurely."""
    return tempfile.mktemp()


def evaluate(expression: str) -> object:
    """Evaluate an expression dynamically (intentionally unsafe)."""
    return eval(expression)
