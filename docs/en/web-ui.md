[日本語](../web-ui.md) | **English**

# Web UI and CTF challenge

[← Back to README](../../README.en.md)

## 🌐 Understand it visually in the Web UI

A Web UI lets you compare the two policies, "retain for observation" and "discard", side by side in the browser. You can switch between Japanese and English.

> **Note**: This Web UI is a **replay of fixed teaching material**. It does not connect to a Python server or a network. Times, ids, and counts are model values, not measurements. To see real communication, run `scenarios_test.py` or `scenarios_test_secure.py` from the CLI.

### How to start

```bash
./venv/bin/python web/server.py
```

The browser opens `http://localhost:8080`. You can change the port with an argument (e.g. `web/server.py 8081`).

### Layout

- **Top**: the title and, at the top right, the language toggle (English / 日本語)
- **Buttons**: "Play: retain for observation", "Play: discard", "Stop and clear"
- **Left/right panels**: "retain for observation" and "discard" side by side. Each panel has two columns, Client and Server, and draws the exchange from 0ms to 1000ms as a timeline
- **Model counts**: below each panel, the counts of requests sent, responses matched to requests, timeouts, and late responses retained/discarded
- **Policies and limits**: a table of the two policies' differences (request id, unmatched response, Python wait timeout) and "What this teaching example does not guarantee"

> ![Web UI comparing "retain for observation vs discard"](../../assets/screenshot2.en.png)

### Difference between the two policies

| Observation point | Retain for observation | Discard |
|-------------|------------|------|
| Request id | Sequential; correlate by matching id | Illustrative random id notation; not authentication |
| Unmatched response (orphan) | Retain up to 100 for observation; never reassign | Count without retaining the payload |
| Python wait timeout | A finite positive number | Warn outside 0.1–30 s (does not change the value) |

In the 1000ms row, retain shows "retain late response" and discard shows "discard late response". Both share the point "no matching pending request (orphan)".

### What this teaching example does not guarantee

As the Web UI also states, this material provides no sender authentication, access control, server-side cancellation, or general DoS protection. Random ids and separating logs to stderr alone do not prevent attacks. Retention alone does not necessarily leak information; exposing stored responses to other users, or reusing them for unrelated requests, is what creates the problem.

### Learning steps with the Web UI

1. Run "Play: retain for observation" and "Play: discard" and compare the left/right panels
2. Follow the flow where 0ms–700ms is identical for both, a timeout happens at 750ms, and the late response (orphan) arrives at 1000ms
3. In the 1000ms row, confirm that retain keeps the late response for observation while discard records only the count and drops the content
4. In "Policies and limits", confirm the difference between sequential and random ids, and that the wait timeout is warned only and not forced

### FAQ

**Q: Is it communicating with a real MCP server?**

A: **No, it is not.** The Web UI is a replay of fixed teaching material.

| Item | Web UI | CLI test |
|------|--------|----------|
| Start MCP server | No | Yes |
| Real communication | No | Yes |
| Data source | Fixed model values | Real requests/responses |
| Purpose | Visual understanding of concepts | Confirming real behavior |

To see real communication:
```bash
./venv/bin/python mcp/scenarios_test.py
./venv/bin/python mcp/scenarios_test_secure.py
```

**Q: What if port 8080 is unavailable?**

A: You can specify another port.

```bash
./venv/bin/python web/server.py 8081
```

**Q: Can I switch the display to English?**

A: Use the "English" button at the top right to switch between Japanese and English. Your chosen language is remembered in the browser.

---

## 🎯 CTF-style hands-on attack challenge

This tool includes a CTF (Capture The Flag) style challenge to put what you learned into practice.

### Challenge 1: Orphan Response Hijacking

**Difficulty**: ★★☆☆☆ (beginner to intermediate)

**Scenario**:
You are a security researcher. You received a report that an MCP server used in a company's internal system has a vulnerability. Multiple users access this server, and it manages each user's secret information. You can access as the "guest" user, and your goal is to obtain the "admin" user's secret (the FLAG).

**Goal**:
```
Obtain the admin user's secret (FLAG{...})
```

**Difficulty modes**:
| Mode | Description |
|--------|------|
| 🟢 Easy | Source reference OK; use a fill-in-the-blank template |
| 🟡 Normal | Do not look at the source; build the attack from behavior (practical) |
| 🔴 Hard | No hints; recon → analyze → attack entirely on your own |

**What you can learn**:
- What an orphan response is
- Why saving orphans is dangerous
- The basics of timing attacks
- Countermeasures (discard orphans, cryptographic-random ids)
- Vulnerability-finding techniques in black-box testing (Normal/Hard modes)

**File layout**:
```
challenges/challenge1_orphan_hijack/
├── README.md              # detailed instructions
├── vulnerable_server.py   # the vulnerable target server
├── exploit_template.py    # fill-in-the-blank exploit script (Easy mode)
├── hint1.txt              # hint 1: the direction of the attack
├── hint2.txt              # hint 2: concrete technique
├── hint_blackbox.txt      # black-box attack technique (Normal/Hard modes)
└── solution.py            # the model answer (last resort)
```

**How to run**:

```bash
# Terminal 1: start the vulnerable server
cd challenges/challenge1_orphan_hijack
../../venv/bin/python vulnerable_server.py

# Terminal 2: edit and run the exploit script
cd challenges/challenge1_orphan_hijack
# edit exploit_template.py to complete the attack
../../venv/bin/python exploit_template.py
```

**Example output on a successful attack** (from the model answer):
```
[*] Step 1: log in as guest
[+] login succeeded

[*] Step 2: trigger admin activity

[*] Step 3: waiting for an orphan to occur...

[*] Step 4: fetch the orphan response

[*] Step 5: extract the FLAG

[PASS] FLAG retrieved: FLAG{0rph4n_r3sp0ns3_h1j4ck3d_succ3ssfully}
```

You can pin this behavior with the integration test, which asserts that the exploit succeeds against the vulnerable server (exit 0 + FLAG) and fails against the discard policy (`--discard-orphans`, non-zero exit):

```bash
./venv/bin/python challenges/challenge1_orphan_hijack/integration_test.py
```

---
