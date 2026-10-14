#!/usr/bin/env python3
"""Executable assertions for the observation policy (standard library only)."""
import os
import sys
from concurrent.futures import TimeoutError
from client import StdioClient

SERVER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_server.py")


class StdioMcpClient(StdioClient):
    """Observe at most 100 orphan responses; never attach them to another request."""


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("[PASS]", message)


def scenario_handshake(client):
    response = client.request("initialize", {
        "protocolVersion": "2025-11-25", "capabilities": {},
        "clientInfo": {"name": "scenario-client", "version": "1.0"}})
    check(response["result"]["protocolVersion"] == "2025-11-25", "initialize")
    client.notify("notifications/initialized", {})
    check(client.request("ping", {})["result"] == {}, "ping")


def scenario_demux_async(client):
    id1, future1 = client.send_request("tools/call", {
        "name": "add_numbers", "arguments": {"a": 1, "b": 2}})
    id2, future2 = client.send_request("tools/call", {
        "name": "add_numbers", "arguments": {"a": 40, "b": 2}})
    # Reverse the order of waits. This alone does not reorder server responses.
    response2 = future2.result(timeout=5)
    response1 = future1.result(timeout=5)
    check(response1["id"] == id1 and response2["id"] == id2, "request ID correlation")
    check([response1["result"]["content"][0]["text"],
           response2["result"]["content"][0]["text"]] == ["3", "42"], "results: 3, 42")
    check(not client._pending, "completed requests removed from pending")


def scenario_tool_error(client):
    response = client.request("tools/call", {"name": "no_such_tool", "arguments": {}})
    check(response["error"]["code"] == -32602, "unknown tool: protocol error -32602")
    response = client.request("tools/call", {"name": "sleep_ms", "arguments": {"ms": -1}})
    check(response["result"].get("isError") is True, "invalid tool value: result.isError")


def scenario_timeout_orphan(client):
    client.orphan_event.clear()
    before = client.get_stats()
    try:
        client.request("tools/call", {"name": "sleep_ms", "arguments": {"ms": 300}}, timeout=0.05)
    except TimeoutError:
        pass
    else:
        raise AssertionError("Expected timeout")
    check(client.orphan_event.wait(5), "late response arrived")
    after = client.get_stats()
    check(after["timeouts"] == before["timeouts"] + 1, "one timeout")
    check(after["orphans_observed"] == before["orphans_observed"] + 1, "one orphan response")
    if client.discard_orphans:
        check(not client.orphan_responses and after["orphans_discarded"] == 1,
              "orphan payload discarded")
    else:
        check(len(client.orphan_responses) == 1, "orphan retained only for observation")
    check(not client._pending, "timed-out request removed from pending")


def run(client_class=StdioMcpClient):
    with client_class(sys.executable, SERVER_PATH) as client:
        scenario_handshake(client)
        scenario_demux_async(client)
        scenario_tool_error(client)
        scenario_timeout_orphan(client)
        print("STATS", client.get_stats())


if __name__ == "__main__":
    run()
