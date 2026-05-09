"""VALIDATE-phase executors.

Two backends:
- ``DockerValidator`` (default): runs the stack's validate_commands inside a
  fresh container based on ``profile.container_image``. Free, local, no
  external dependency beyond a working ``docker`` CLI.
- ``E2BValidator`` (used when ``VINEYARD_E2B_API_KEY`` is set): spins up an
  E2B Firecracker microVM, uploads the build directory, and runs the
  commands there. No local Docker needed.

Selection happens in :func:`get_validator`:
- ``settings.validate_executor == "auto"`` → E2B if key is set, else Docker
- explicit ``"docker"`` / ``"e2b"`` / ``"none"`` overrides
"""

from vineyard.validate.executor import (
    ValidatorContext,
    Validator,
    get_validator,
)

__all__ = ["Validator", "ValidatorContext", "get_validator"]
