#!/usr/bin/env python3
"""Integration test for the bundled orphan-hijack lab.

The exploit must succeed against the vulnerable loopback server (exit 0, FLAG)
and must fail against the discard policy (non-zero exit, no FLAG). This is the
behavior the challenge teaches, so it is pinned here to catch regressions.
"""
import os
import subprocess
import sys
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "vulnerable_server.py")
SOLUTION = os.path.join(HERE, "solution.py")
READY_TIMEOUT = 10
SOLUTION_TIMEOUT = 30


def _child_env():
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _start_server(extra_args):
    """Launch the server on an ephemeral port and return (proc, port)."""
    proc = subprocess.Popen(
        [sys.executable, SERVER, "--port", "0", *extra_args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=_child_env(),
    )
    port = None
    deadline = time.monotonic() + READY_TIMEOUT
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            continue
        if line.startswith("READY "):
            port = int(line.split()[1])
            break
    if port is None:
        proc.kill()
        proc.wait(timeout=5)
        raise RuntimeError("server did not report READY")
    # Keep draining stdout so the server never blocks on a full pipe.
    threading.Thread(target=lambda: proc.stdout.read(), daemon=True).start()
    return proc, port


def _run_solution(port):
    result = subprocess.run(
        [sys.executable, SOLUTION, "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=SOLUTION_TIMEOUT,
        env=_child_env(),
    )
    return result.returncode, result.stdout


class ExploitIntegration(unittest.TestCase):
    def _exercise(self, extra_args):
        proc, port = _start_server(extra_args)
        try:
            return _run_solution(port)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            if proc.stdout is not None:
                proc.stdout.close()

    def test_vulnerable_server_leaks_flag(self):
        code, output = self._exercise([])
        self.assertEqual(code, 0, output)
        self.assertIn("FLAG{", output)

    def test_discard_policy_denies_flag(self):
        code, output = self._exercise(["--discard-orphans"])
        self.assertNotEqual(code, 0, output)
        self.assertNotIn("FLAG{", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
