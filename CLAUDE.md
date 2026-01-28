# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Async RPC Failure Simulator** is an educational tool demonstrating failure modes in asynchronous RPC systems using MCP (Model Context Protocol) as a case study. It reproduces timeouts, orphan responses, ID mismatches, and request/response ordering issues. This is a learning tool for understanding dangerous design patterns, not an attack tool.

## Commands

### Setup
```bash
python3 -m venv venv
./venv/bin/python --version
```

### Run MCP Server (standalone)
```bash
./venv/bin/python ./mcp/demo_server.py
```

### Run Failure Scenario Tests (Vulnerable Implementation)
```bash
./venv/bin/python ./mcp/scenarios_test.py
```

### Run Secure Implementation Tests
```bash
./venv/bin/python ./mcp/scenarios_test_secure.py
```

### Manual Protocol Test (ping)
```bash
printf '{"jsonrpc":"2.0","id":1,"method":"ping"}' | ./venv/bin/python mcp/demo_server.py 2>/dev/null
```

### Launch MCP Inspector (requires Node.js)
```bash
npx -y @modelcontextprotocol/inspector@0.19.0 -- ./venv/bin/python ./mcp/demo_server.py
```

## Architecture

### Two-Component Design

1. **`mcp/demo_server.py`** - MCP stdio transport server
   - JSON-RPC 2.0 over stdio (stdin/stdout)
   - **Critical rule**: stdout contains ONLY JSON; all logs go to stderr
   - Implements: `initialize`, `ping`, `resources/list`, `tools/list`, `tools/call`
   - Tools: `add_numbers` (arithmetic), `sleep_ms` (deliberate delay for timeout testing)
   - Tool errors use `result.isError` flag, NOT JSON-RPC error protocol

2. **`mcp/scenarios_test.py`** - Test client reproducing failure modes (VULNERABLE)
   - Spawns demo_server.py as subprocess
   - `StdioMcpClient` class with multi-threaded design (main + reader thread)
   - `_pending` dict maps request IDs to Futures
   - `orphan_responses` collects responses that arrive after timeout cleanup
   - **Vulnerable**: Sequential IDs, orphans stored for reuse

3. **`mcp/secure_client.py`** + **`mcp/scenarios_test_secure.py`** - Secure implementation
   - `SecureStdioMcpClient` with hardened design
   - **Secure**: Cryptographic random IDs (`secrets.token_hex`), orphans discarded
   - Timeout range validation with warnings
   - Statistics tracking for monitoring

### Key Failure Mode: Orphan Response Pattern
```
1. Client sends request with id=N
2. Client waits with short timeout
3. Server sleeps longer than timeout
4. Client timeout fires, removes id=N from pending tracking
5. Server returns response with id=N
6. Response has no matching pending Future → becomes "orphan"
```

### Data Flow
```
Client                      Server
  │                           │
  ├─ send_request() ─────────→ stdin
  │                           │
  │                           ├─ handle_request()
  │                           │
  │  ← stdout ←───────────────┤ send_message()
  │                           │
  └─ reader thread matches id → Future.set_result()
```

## Protocol Notes

- JSON-RPC 2.0 with stdio transport
- Notifications (no `id` field) expect no response
- Tool-level errors return `{"result": {"isError": true, "content": [...]}}`, not `{"error": {...}}`
- Server handles unknown methods gracefully with isError response

## Dependencies

- Python 3.9+ (standard library only, no pip install needed)
- Node.js/npx only for MCP Inspector GUI (optional)
