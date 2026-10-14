"""Discard-policy teaching client; no authentication or general DoS protection."""
import sys
from client import StdioClient

DEFAULT_TIMEOUT = 5.0
MIN_TIMEOUT = 0.1
MAX_TIMEOUT = 30.0
ID_BYTES = 16


def log_security(level, message):
    print(f"[{level}] {message}", file=sys.stderr)


class SecureStdioMcpClient(StdioClient):
    """The historical class name denotes the discard comparison, not a security guarantee."""

    def __init__(self, python_exe, server_script):
        super().__init__(python_exe, server_script, discard_orphans=True)

    def request(self, method, params, timeout=None):
        if timeout is None:
            timeout = DEFAULT_TIMEOUT
        if type(timeout) in (int, float) and (timeout < MIN_TIMEOUT or timeout > MAX_TIMEOUT):
            log_security("WARN", "Timeout is outside the recommended 0.1-30 s range; not clamped.")
        return super().request(method, params, timeout)
