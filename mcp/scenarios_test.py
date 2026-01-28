#!/usr/bin/env python3
import os
import sys
import json
import time
import threading
import subprocess
from concurrent.futures import Future, TimeoutError as FutureTimeoutError

# ============================================================
# 目的:
#  - MCP stdio サーバー（mcp/demo_server.py）を起動し、
#    非同期RPCの失敗モード（timeout / orphan response / demux）を
#    再現可能なシナリオとして実行する。
#
# 前提:
#  - このテストは stdout/stdio の仕様を崩さない（サーバーのstdoutはJSONのみ）
#  - このテストは「観測（ログ）」も成果なので、標準出力に結果を表示する
# ============================================================

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER_PATH = os.path.join(HERE, "demo_server.py")


def header(title: str):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


class StdioMcpClient:
    """
    stdio transport 用の最小クライアント（テスト専用）。

    ポイント:
    - readerスレッドが stdout を読み続ける
    - id -> Future の台帳（pending）でレスポンスを突き合わせる
    - タイムアウトしたリクエストは台帳から外す
      → 後から返ってきたレスポンスは orphan として観測できる
    """

    def __init__(self, python_exe: str, server_script: str):
        # サーバーを子プロセスとして起動（stdio transport）
        self.process = subprocess.Popen(
            [python_exe, server_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # サーバーstderrは捨てる（クライアント出力と混ざらない）
            text=True,
            bufsize=1,           # 行バッファ（読みやすさのため）
        )

        # request_id発行とpending台帳
        self._lock = threading.Lock()
        self._next_id = 0
        self._pending = {}  # id -> Future

        # orphan（タイムアウト後に返ってきた遅延レスポンス等）の観測用
        self.orphan_responses = []  # list[dict]
        self.notifications = []     # list[dict]

        # readerスレッド開始
        self._running = True
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader.start()

    def close(self):
        """
        サーバー停止と後始末
        """
        self._running = False
        try:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=3)
        except Exception:
            pass

    def _send(self, msg: dict):
        """
        1行JSONをサーバーstdinへ送信
        """
        s = json.dumps(msg)
        self.process.stdin.write(s + "\n")
        self.process.stdin.flush()

    def _issue_id(self) -> int:
        with self._lock:
            self._next_id += 1
            return self._next_id

    def _reader_loop(self):
        """
        サーバーstdoutを読み続けて、idで突き合わせる。
        """
        try:
            for line in self.process.stdout:
                line = line.strip()
                if not line:
                    continue

                # サーバーはstdoutにJSONのみ出す前提だが、
                # 万一混ざったときに観測しやすいように扱う
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    print(f"[WARN] JSON以外を受信（stdout汚染の疑い）: {line}")
                    continue

                # 通知（idなし）
                resp_id = data.get("id")
                if resp_id is None:
                    self.notifications.append(data)
                    continue

                # レスポンス（idあり）
                with self._lock:
                    fut = self._pending.get(resp_id)

                if fut is None:
                    # 台帳にない -> orphan（タイムアウト後の遅延レスポンス等）
                    self.orphan_responses.append(data)
                    continue

                if not fut.done():
                    fut.set_result(data)
        except Exception as e:
            print(f"[FATAL] readerスレッドがクラッシュ: {e}")
        finally:
            pass

    def send_request(self, method: str, params: dict) -> tuple[int, Future]:
        """
        request（idあり）を投げ、Futureを返す（待機は呼び出し側）
        """
        request_id = self._issue_id()
        fut = Future()
        with self._lock:
            self._pending[request_id] = fut

        msg = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        self._send(msg)
        return request_id, fut

    def request(self, method: str, params: dict, timeout: float = 5.0) -> dict:
        """
        同期リクエスト（待機してレスポンスdictを返す）
        タイムアウトしたら TimeoutError を投げる。
        """
        request_id, fut = self.send_request(method, params)
        try:
            return fut.result(timeout=timeout)
        finally:
            # 必ず台帳を掃除（ここが orphan 観測の鍵にもなる）
            with self._lock:
                self._pending.pop(request_id, None)

    def notify(self, method: str, params: dict):
        """
        notification（idなし）を送信
        """
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        self._send(msg)


# ============================================================
# シナリオ本体
# ============================================================

def scenario_handshake(client: StdioMcpClient):
    header("SCENARIO 1: Handshake（initialize → initialized通知 → ping）")

    # initialize
    resp = client.request("initialize", {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "scenario-client", "version": "0.1.0"}
    }, timeout=5)

    if "result" in resp and "serverInfo" in resp["result"]:
        print("[PASS] initialize 応答OK:", resp["result"]["serverInfo"])
    else:
        print("[FAIL] initialize 応答が想定外:", resp)

    # notifications/initialized（通知なので待たない）
    client.notify("notifications/initialized", {})
    print("[INFO] notifications/initialized を送信")

    # ping
    resp = client.request("ping", {}, timeout=5)
    if resp.get("result") == {}:
        print("[PASS] ping 応答OK")
    else:
        print("[FAIL] ping 応答が想定外:", resp)


def scenario_demux_async(client: StdioMcpClient):
    header("SCENARIO 2: 非同期demux（2リクエストを投げて逆順で回収）")

    # 2つの tools/call を「待たずに」投げる
    id1, fut1 = client.send_request("tools/call", {
        "name": "add_numbers",
        "arguments": {"a": 1, "b": 2}
    })
    id2, fut2 = client.send_request("tools/call", {
        "name": "add_numbers",
        "arguments": {"a": 40, "b": 2}
    })

    print(f"[INFO] dispatched id1={id1}, id2={id2}")

    # わざと逆順で待つ（順不同でも取り違えないことが本質）
    resp2 = fut2.result(timeout=5)
    resp1 = fut1.result(timeout=5)

    n2 = int(resp2["result"]["content"][0]["text"])
    n1 = int(resp1["result"]["content"][0]["text"])

    if (n1, n2) == (3, 42):
        print("[PASS] demux 成功: results =", n1, n2)
    else:
        print("[FAIL] demux 失敗（取り違え疑い）:", n1, n2)


def scenario_tool_error(client: StdioMcpClient):
    header("SCENARIO 3: ツールレベルエラー（unknown tool → result.isError）")

    resp = client.request("tools/call", {
        "name": "no_such_tool",
        "arguments": {"a": 1, "b": 1}
    }, timeout=5)

    # このデモサーバーは JSON-RPC error フィールドではなく
    # result.isError でツールエラーを表現する仕様
    result = resp.get("result")
    if isinstance(result, dict) and result.get("isError") is True:
        print("[PASS] ツールエラーを検出:", result["content"][0]["text"])
    else:
        print("[FAIL] 期待したエラー形式ではない:", resp)


def scenario_timeout_orphan(client: StdioMcpClient):
    header("SCENARIO 4: タイムアウト → 遅延レスポンス（orphan）観測")

    # ここでは「sleep_ms」を使って確実に遅延させる
    # ms=300 で 0.3秒待つが、timeout=0.05 で先に諦める
    ms = 300
    timeout_sec = 0.05

    try:
        client.request("tools/call", {
            "name": "sleep_ms",
            "arguments": {"ms": ms}
        }, timeout=timeout_sec)
        print("[FAIL] 期待した TimeoutError が発生しなかった（環境が異常に速い？）")
        return
    except FutureTimeoutError:
        print(f"[PASS] TimeoutError を観測（timeout={timeout_sec}s, sleep={ms}ms）")

    # 重要：サーバーはこの後、遅れてレスポンスを返してくる
    # 台帳は掃除済みなので、そのレスポンスは orphan として観測されるはず
    # 少し待って reader が受信する猶予を与える
    time.sleep(ms / 1000.0 + 0.1)

    if client.orphan_responses:
        # 直近の orphan を表示
        last = client.orphan_responses[-1]
        print("[PASS] orphan response を観測:", last)
    else:
        print("[WARN] orphan response を観測できなかった（受信タイミング次第で起こり得る）")


def main():
    # このスクリプト自体は venv の python で実行する想定。
    # sys.executable を使えば、その python で demo_server.py が起動される。
    python_exe = sys.executable
    if not os.path.exists(SERVER_PATH):
        print(f"[FATAL] サーバースクリプトが見つかりません: {SERVER_PATH}")
        sys.exit(1)

    client = StdioMcpClient(python_exe=python_exe, server_script=SERVER_PATH)

    try:
        # 方針A：タイムアウトは最後に回す（遅延レスポンスが後続ログを汚すため）
        scenario_handshake(client)
        scenario_demux_async(client)
        scenario_tool_error(client)
        scenario_timeout_orphan(client)

    finally:
        header("CLEANUP")
        client.close()
        print("[INFO] サーバー停止")


if __name__ == "__main__":
    main()
