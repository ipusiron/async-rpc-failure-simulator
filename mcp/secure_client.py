#!/usr/bin/env python3
"""
堅牢なMCPクライアント実装（secure_client.py）

脆弱な実装（scenarios_test.py の StdioMcpClient）との主な違い:

1. request_id: 連番 → 暗号論的乱数（予測不可能）
2. orphan response: リストに保存 → ログ出力して即座に破棄
3. タイムアウト: 呼び出し側で自由に設定 → デフォルト値を強制（上書き可能だが警告）
4. unknown-id: 黙って保存 → 警告ログを出力

これにより以下の攻撃を防止:
- request_id予測によるレスポンス差し替え
- orphan response再利用による情報漏洩
- タイムアウト操作によるDoS
"""

import os
import sys
import json
import secrets
import threading
import subprocess
from concurrent.futures import Future, TimeoutError as FutureTimeoutError

# ============================================================
# 設定値（堅牢化のためのデフォルト）
# ============================================================

DEFAULT_TIMEOUT = 5.0  # デフォルトタイムアウト（秒）
MIN_TIMEOUT = 0.1      # 最小タイムアウト（これ以下は警告）
MAX_TIMEOUT = 30.0     # 最大タイムアウト（これ以上は警告）
ID_BYTES = 16          # request_idのバイト長（16バイト = 128ビット）


def log_security(level: str, msg: str):
    """セキュリティ関連のログ出力"""
    print(f"[{level}] [SECURITY] {msg}", file=sys.stderr)


class SecureStdioMcpClient:
    """
    堅牢化されたstdio transport用MCPクライアント。

    脆弱な実装との違い:
    - _issue_id(): 連番ではなく secrets.token_hex() を使用
    - _reader_loop(): orphan responseは保存せず警告ログのみ
    - request(): タイムアウト値の範囲チェック
    """

    def __init__(self, python_exe: str, server_script: str):
        self.process = subprocess.Popen(
            [python_exe, server_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

        self._lock = threading.Lock()
        self._pending = {}  # id -> Future

        # 統計情報（監視・アラート用）
        self.stats = {
            "requests_sent": 0,
            "responses_received": 0,
            "orphans_discarded": 0,  # 保存ではなくカウントのみ
            "timeouts": 0,
        }

        self.notifications = []

        self._running = True
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader.start()

    def close(self):
        self._running = False
        try:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=3)
        except Exception:
            pass

    def _send(self, msg: dict):
        s = json.dumps(msg)
        self.process.stdin.write(s + "\n")
        self.process.stdin.flush()

    def _issue_id(self) -> str:
        """
        【堅牢化ポイント1】暗号論的乱数でIDを生成

        脆弱な実装: self._next_id += 1（連番、予測可能）
        堅牢な実装: secrets.token_hex()（予測不可能）

        これにより:
        - 攻撃者がIDを推測してレスポンスを差し替える攻撃を防止
        - IDの衝突確率は 2^-128 で実質ゼロ
        """
        return secrets.token_hex(ID_BYTES)

    def _reader_loop(self):
        try:
            for line in self.process.stdout:
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    log_security("WARN", f"JSON以外を受信（stdout汚染の疑い）: {line[:100]}")
                    continue

                resp_id = data.get("id")
                if resp_id is None:
                    self.notifications.append(data)
                    continue

                with self._lock:
                    fut = self._pending.get(resp_id)

                if fut is None:
                    # 【堅牢化ポイント2】orphan responseは保存せず破棄
                    #
                    # 脆弱な実装: self.orphan_responses.append(data)
                    # 堅牢な実装: ログ出力して破棄（再利用させない）
                    #
                    # これにより:
                    # - orphan responseを再利用した情報漏洩を防止
                    # - タイミング攻撃によるレスポンス横取りを防止
                    self.stats["orphans_discarded"] += 1
                    log_security("WARN", f"Orphan response を破棄: id={resp_id}")
                    continue  # ← 保存しない

                self.stats["responses_received"] += 1
                if not fut.done():
                    fut.set_result(data)

        except Exception as e:
            log_security("FATAL", f"readerスレッドがクラッシュ: {e}")

    def send_request(self, method: str, params: dict) -> tuple[str, Future]:
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
        self.stats["requests_sent"] += 1
        return request_id, fut

    def request(self, method: str, params: dict, timeout: float = None) -> dict:
        """
        【堅牢化ポイント3】タイムアウト値の検証

        脆弱な実装: timeout引数をそのまま使用
        堅牢な実装: 範囲外の値には警告を出し、デフォルト値を推奨

        これにより:
        - 極端に長いタイムアウトによるリソース占有（DoS）を抑制
        - 極端に短いタイムアウトによる意図しないorphan大量発生を抑制
        """
        if timeout is None:
            timeout = DEFAULT_TIMEOUT
        elif timeout < MIN_TIMEOUT:
            log_security("WARN", f"タイムアウトが短すぎます: {timeout}s < {MIN_TIMEOUT}s")
        elif timeout > MAX_TIMEOUT:
            log_security("WARN", f"タイムアウトが長すぎます: {timeout}s > {MAX_TIMEOUT}s")

        request_id, fut = self.send_request(method, params)
        try:
            return fut.result(timeout=timeout)
        except FutureTimeoutError:
            self.stats["timeouts"] += 1
            raise
        finally:
            with self._lock:
                self._pending.pop(request_id, None)

    def notify(self, method: str, params: dict):
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        self._send(msg)

    def get_stats(self) -> dict:
        """統計情報を取得（監視・デバッグ用）"""
        return dict(self.stats)
