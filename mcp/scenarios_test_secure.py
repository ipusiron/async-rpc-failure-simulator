#!/usr/bin/env python3
"""Same executable assertions with orphan payload disposal."""
from secure_client import SecureStdioMcpClient
from scenarios_test import run

if __name__ == "__main__":
    run(SecureStdioMcpClient)
    print("Random IDs are not authentication. Timeout warnings do not prevent DoS.")
