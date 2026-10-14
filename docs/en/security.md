[日本語](../security.md) | **English**

# Design mistakes and security cases

[← Back to README](../../README.en.md)

## ⚠️ Problems caused by design mistakes

What problems do the failure modes reproduced here cause in real systems? We explain from three angles: performance, operations, and security.

### Performance impact

| Design mistake | Problem | Concrete example |
|---------|------|--------|
| Keeping the pending table after a timeout | **Memory leak** | The pending table grows over long operation and crashes with OOM (Out of Memory) |
| Buffering orphan responses without limit | **Memory exhaustion** | Hoarding late responses instead of discarding them pressures the heap |
| A design that waits synchronously for responses | **Lower throughput** | Waiting per request prevents parallelism |
| Lock contention in demux processing | **Higher latency** | Lock waits when multiple threads access the pending table |

### Operational trouble

| Design mistake | Problem | Concrete example |
|---------|------|--------|
| No logging of orphan responses | **Hard to find the cause of an incident** | For a report of "responses somehow never come back", you cannot tell whether the cause is a timeout or a communication error |
| Confusing error kinds (protocol vs tool layer) | **Wrong retry handling** | A tool error (business-logic failure) is mistaken for a protocol error (transient failure) and retried forever |
| Duplicate/exhausted request_ids | **Response mix-up** | A 32-bit integer id overflows and collides with a past id |
| Lack of a server-side cancellation mechanism | **Resource waste** | Even if the client times out, the server keeps processing and wastes CPU and DB connections |

### Security risks (most important)

| Design mistake | Attack scenario | Severity |
|---------|-------------|--------|
| **Reusing orphan responses** | The attacker tunes timing to tie another user's response to their own request | **Critical** - auth bypass, info leak |
| **Accepting unknown-id responses** | The attacker injects a fake response (arbitrary id) and makes the client return a wrong result | **High** - data tampering, logic manipulation |
| **Predictable request_id** | Guessing a sequential or time-based id and swapping the response in a man-in-the-middle attack | **High** - session hijacking |
| **Excessive information disclosure in error messages** | Including stack traces or internal paths in tool errors | **Medium** - a foothold for reconnaissance |
| **External control of the timeout value** | Letting user input set an extremely long timeout to occupy resources | **Medium** - DoS |

### A real-incident example (fictional scenario)

```
[Situation]
- An MCP-based AI agent implements a tool that calls an external API
- The design reuses post-timeout orphan responses as a "cache"

[Attack]
1. Attacker A sends a request to "get User B's personal data"
2. While the server is processing, attacker A causes a timeout
3. The orphan response (User B's personal data) remains in the cache
4. Attacker A sends the next request
5. The orphan response is returned from the cache, obtaining User B's data

[Root cause]
- A design mistake: reusing orphan responses without discarding them
- Insufficient binding between request_id and the user session
```

### Correct design guidelines

| Principle | How to implement |
|------|----------|
| **Discard orphans immediately** | For a response whose id is not in the table, record only the count and drop the payload |
| **request_id is cryptographic random** | Generate with UUID v4 or a CSPRNG to make it unpredictable |
| **Timeout is a fixed value** | Do not let external input change the timeout value |
| **Separate error kinds clearly** | Retry protocol errors; notify the user of tool errors |
| **Implement a cancellation mechanism** | Send a cancellation notice to the server on client timeout |

---

### Vulnerable vs robust implementation (code comparison)

This repository switches the same `client.py` with the `discard_orphans` flag, so you can try both the retain/observe policy and the discard policy.

#### How to run

```bash
# Vulnerable (observe the failure modes)
./venv/bin/python mcp/scenarios_test.py

# Robust (confirm the correct design)
./venv/bin/python mcp/scenarios_test_secure.py
```

#### Code differences

| Aspect | Retain/observe (`discard_orphans=False`) | Discard (`discard_orphans=True`) |
|------|----------------------------------|----------------------------------|
| **request_id generation** | `self._next_id += 1` (sequential) | `secrets.token_hex(16)` (cryptographic random) |
| **orphan response** | `self.orphan_responses.append(data)` (save) | `stats["orphans_discarded"] += 1` (discard) |
| **Timeout** | `client.py` validates a finite, positive value | `secure_client.py` warns out-of-range (does not change the value) |
| **Statistics** | Obtained via `get_stats()` | Obtained via `get_stats()` (`orphans_discarded` increases) |

#### Id-generation comparison

```python
# client.py _issue_id: one flag switches sequential/random
def _issue_id(self):
    if self.discard_orphans:
        return secrets.token_hex(16)  # → "a3f8c9e1..." (unpredictable)
    self._next_id += 1
    return self._next_id              # → 1, 2, 3... (predictable)
```

#### Orphan-handling comparison

```python
# client.py _accept: the flag switches save/discard
if future is None or future.done():
    self.stats["orphans_observed"] += 1
    if self.discard_orphans:
        self.stats["orphans_discarded"] += 1   # ← record the count only (not reusable)
    else:
        self.orphan_responses.append(data)      # ← save (reusable and dangerous)
```

#### Example output of the robust implementation

```
$ ./venv/bin/python mcp/scenarios_test_secure.py
[WARN] Timeout is outside the recommended 0.1-30 s range; not clamped.
...(the [PASS] lines for SCENARIO 1-4 follow)
[PASS] orphan payload discarded
[PASS] timed-out request removed from pending
STATS {'requests_sent': 7, 'responses_received': 6, 'orphans_observed': 1, 'orphans_discarded': 1, 'timeouts': 1, 'invalid_messages': 0}
Random IDs are not authentication. Timeout warnings do not prevent DoS.
```
The robust version shows `orphan payload discarded` and `orphans_discarded` increases to 1 (the vulnerable version stays at `orphan retained only for observation` with 0).

---

### Real-world security cases / CVEs

The failure modes this simulator deals with have been reported as serious vulnerabilities in real products.

#### 1. HTTP/2 Rapid Reset Attack (CVE-2023-44487)

**Related failure mode**: stream multiplexing (demux) and resource management

| Item | Content |
|------|------|
| **CVSS** | 7.5 (High) |
| **Impact** | Abused for the **largest DDoS attacks on record** at major clouds such as Google, Cloudflare, and AWS |
| **Cause** | Abuses HTTP/2's stream reset. When the client sends a cancel (RST_STREAM) right after a request, the server considers "the stream is closed" but **the backend keeps processing asynchronously**. Repeating this at scale exhausts resources |
| **Relevance to this simulator** | The same structure as SCENARIO 4's "the server keeps processing even after the timeout" |

> Reference: [Cloudflare - HTTP/2 Rapid Reset Attack](https://blog.cloudflare.com/technical-breakdown-http2-rapid-reset-ddos-attack/)

---

#### 2. Response mix-up (HTTP desync / response queue poisoning)

**Related failure mode**: response mix-up (demux failure)

| Item | Content |
|------|------|
| **Impact** | An information leak where **another user's response is returned** through a reverse proxy |
| **Cause** | The front end and back end interpret request boundaries differently (desync), and when the connection is reused **the previous response bleeds into the next request** |
| **Relevance to this simulator** | A real-world example of SCENARIO 2's "if demux by id is not implemented correctly, responses get mixed up" |

> Reference: [PortSwigger - HTTP request smuggling](https://portswigger.net/web-security/request-smuggling)

---

#### 3. Bugzilla JSON-RPC CSRF (CVE-2012-0440)

**Related failure mode**: security design of JSON-RPC

| Item | Content |
|------|------|
| **Impact** | **Any JSON-RPC API could be executed** via an authenticated user's browser. Admin privilege takeover and access to security bugs |
| **Cause** | The JSON-RPC endpoint allowed bypassing the CSRF token check. `Content-Type: application/json` was not enforced, so an ordinary form submission could attack it |
| **Relevance to this simulator** | SCENARIO 3's "confusing protocol- and tool-layer errors" — ambiguous authentication/authorization layers get abused |

> Reference: [Bugzilla Bug 718319](https://bugzilla.mozilla.org/show_bug.cgi?id=718319)

---

#### 4. Juniper Junos RPC Race Condition (CVE-2016-1267)

**Related failure mode**: a race condition in asynchronous processing

| Item | Content |
|------|------|
| **Impact** | An authenticated user could **take ownership of an arbitrary file** and escalate to root |
| **Cause** | A "lazy race condition" in RPC — there is a timing gap between the permission check and the actual operation, and the state can be changed in between |
| **Relevance to this simulator** | A time-gap attack similar to the "dangling state" that arises between a timeout and the orphan response |

> Reference: [Juniper Security Bulletin JSA10730](https://kb.juniper.net/InfoCenter/index?page=content&id=JSA10730)

---

#### 5. CryptoNote Wallet JSON-RPC unauthenticated vulnerability

**Related failure mode**: authentication design of JSON-RPC

| Item | Content |
|------|------|
| **Impact** | **Funds could be stolen** from a cryptocurrency wallet |
| **Cause** | The JSON-RPC server ran on localhost without authentication. When the user opened a malicious web page, the wallet API was called via the browser (DNS rebinding / CSRF) |
| **Relevance to this simulator** | It is easy to assume an MCP server is "safe because it is stdio", but depending on the IPC path it can become a target |

> Reference: [CryptoNote Unauthenticated JSON-RPC](https://www.ayrx.me/cryptonote-unauthenticated-json-rpc/)

---

#### 6. Orange Tsai's Confusion Attacks (presented at Black Hat 2024)

**Related failure mode**: confusion of semantics

| Item | Content |
|------|------|
| **Impact** | On Apache HTTP Server, **access-control/auth bypass, access to the whole filesystem, and escalation from XSS to RCE** |
| **Cause** | `r->filename` is interpreted differently by different modules (file path vs URL). This **semantic inconsistency** leads directly to auth bypass |
| **Relevance to this simulator** | SCENARIO 3's "confusing tool-layer and protocol-layer errors" — when semantics per layer are ambiguous, features get invoked via unexpected paths |

> Reference: [Confusion Attacks - Orange Tsai](https://blog.orange.tw/posts/2024-08-confusion-attacks-en/)

---

#### Summary: why these vulnerabilities arise

| Root cause | Relevant CVE/case |
|---------|-------------|
| Insufficient resource lifecycle management in asynchronous processing | HTTP/2 Rapid Reset |
| Incomplete binding (demux) of responses to requests | Response mix-up (HTTP desync) |
| Ambiguous authentication/authorization layers | Bugzilla JSON-RPC CSRF, CryptoNote |
| Not accounting for time gaps (TOCTOU) | Juniper RPC race condition |
| Semantic inconsistency between components | Confusion Attacks |

**All of these stem from "oversights at the design stage", and this simulator is a tool to experience them beforehand.**

---
