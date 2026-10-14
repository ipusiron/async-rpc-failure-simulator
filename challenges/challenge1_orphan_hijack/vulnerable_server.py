#!/usr/bin/env python3
"""
Challenge 1: Orphan Response Hijacking - 脆弱なサーバー

このサーバーには意図的な脆弱性が含まれています：
共有orphan保管庫から別の役のデータを取得できる教材です。
loginは認証ではなく役の選択です。IDの連番自体は脆弱性ではありません。

注意: これは教育目的の脆弱なコードです。本番環境では使用しないでください。
"""

import json
import socket
import threading
import time
import argparse
import math
from typing import Dict, Any, Optional

# サーバー設定
HOST = "127.0.0.1"
PORT = 9999

# ユーザーデータベース（各ユーザーの秘密情報）
USER_SECRETS = {
    "admin": "FLAG{0rph4n_r3sp0ns3_h1j4ck3d_succ3ssfully}",
    "guest": "SECRET{guest_boring_data_nothing_special}",
}

# 脆弱性1: グローバルな orphan_responses リスト（全ユーザー共有）
orphan_responses: list = []
orphan_lock = threading.Lock()
discard_orphans = False


class VulnerableClientHandler:
    """脆弱なクライアントハンドラー"""

    def __init__(self, conn: socket.socket, addr: tuple):
        self.conn = conn
        self.addr = addr
        self.authenticated_user: Optional[str] = None
        self.running = True

    def handle(self):
        """クライアント接続を処理"""
        print(f"[SERVER] クライアント接続: {self.addr}")
        buffer = b""

        try:
            while self.running:
                data = self.conn.recv(4096)
                if not data:
                    break

                buffer += data
                if len(buffer) > 65536:
                    break

                # 改行区切りでJSONを処理
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line.strip():
                        self._process_message(line.decode("utf-8").strip())

        except Exception as e:
            print(f"[SERVER] エラー: {e}")
        finally:
            print(f"[SERVER] クライアント切断: {self.addr}")
            self.conn.close()

    def _process_message(self, message: str):
        """受信メッセージを処理"""
        try:
            data = json.loads(message)
        except json.JSONDecodeError as e:
            self._send_error(None, -32700, f"Parse error: {e}")
            return

        if not isinstance(data, dict) or data.get("jsonrpc") != "2.0":
            self._send_error(None, -32600, "Invalid request")
            return
        if not isinstance(data.get("params", {}), dict):
            if "id" in data:
                self._send_error(data.get("id"), -32602, "Invalid parameters")
            return
        # JSON-RPC 2.0 リクエスト
        if "method" in data:
            self._handle_request(data)
        # JSON-RPC 2.0 レスポンス（通常サーバーは受信しないが、念のため）
        elif "result" in data or "error" in data:
            pass

    def _handle_request(self, request: Dict[str, Any]):
        """リクエストを処理"""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        # 通知（id なし）の場合は応答不要
        if req_id is None:
            return

        # メソッドに応じた処理
        if method == "login":
            self._handle_login(req_id, params)
        elif method == "get_secret":
            self._handle_get_secret(req_id, params)
        elif method == "slow_operation":
            self._handle_slow_operation(req_id, params)
        elif method == "get_orphans":
            # 脆弱性3: orphan リストを返すメソッド
            self._handle_get_orphans(req_id)
        elif method == "ping":
            self._send_result(req_id, {"pong": True})
        else:
            self._send_error(req_id, -32601, f"Unknown method: {method}")

    def _handle_login(self, req_id: Any, params: Dict[str, Any]):
        """ログイン処理"""
        username = params.get("username", "")

        if username in USER_SECRETS:
            self.authenticated_user = username
            self._send_result(req_id, {
                "success": True,
                "message": f"Logged in as {username}"
            })
            print(f"[SERVER] ユーザー認証: {username}")
        else:
            self._send_error(req_id, -32000, f"Unknown user: {username}")

    def _handle_get_secret(self, req_id: Any, params: Dict[str, Any]):
        """秘密情報を取得（認証済みユーザーのみ）"""
        if not self.authenticated_user:
            self._send_error(req_id, -32000, "Not authenticated")
            return

        # 意図的な遅延（脆弱性: タイミング攻撃を可能にする）
        delay_ms = params.get("delay_ms", 0)
        if not self._valid_delay(delay_ms):
            self._send_error(req_id, -32602, "delay_ms must be a finite number in 0..5000")
            return
        if delay_ms > 0:
            print(f"[SERVER] {self.authenticated_user} の get_secret に {delay_ms}ms 遅延")
            time.sleep(delay_ms / 1000.0)

        secret = USER_SECRETS.get(self.authenticated_user, "NO_SECRET")
        response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "user": self.authenticated_user,
                "secret": secret
            }
        }

        # 脆弱性: 送信失敗時に orphan_responses に保存（秘密情報含む！）
        try:
            self._send_raw(response)
        except Exception:
            self._handle_orphan(response)

    def _handle_slow_operation(self, req_id: Any, params: Dict[str, Any]):
        """遅い操作（orphan response を発生させるため）"""
        delay_ms = params.get("delay_ms", 1000)
        if not self._valid_delay(delay_ms):
            self._send_error(req_id, -32602, "delay_ms must be a finite number in 0..5000")
            return

        print(f"[SERVER] slow_operation 開始 ({delay_ms}ms)")
        time.sleep(delay_ms / 1000.0)
        print(f"[SERVER] slow_operation 完了")

        response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"completed": True, "delay_ms": delay_ms}
        }

        # 脆弱性: 送信失敗時に orphan_responses に保存
        try:
            self._send_raw(response)
        except Exception:
            self._handle_orphan(response)

    @staticmethod
    def _valid_delay(value):
        return type(value) in (int, float) and 0 <= value <= 5000 and math.isfinite(value)

    def _handle_orphan(self, response):
        if discard_orphans:
            print("[SERVER] Orphan payload discarded", flush=True)
        else:
            with orphan_lock:
                orphan_responses.append(response)
                del orphan_responses[:-100]
            print("[SERVER] Orphan stored in shared observation list", flush=True)

    def _handle_get_orphans(self, req_id: Any):
        """orphan リストを返す（脆弱性: 他ユーザーのデータが含まれる可能性）"""
        # 実際のシステムでは絶対にこんなメソッドを公開してはいけない
        with orphan_lock:
            snapshot = orphan_responses.copy()
        self._send_result(req_id, {"orphans": snapshot, "count": len(snapshot)})

    def _send_result(self, req_id: Any, result: Any):
        """成功レスポンスを送信"""
        response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        }
        self._send_raw(response)

    def _send_error(self, req_id: Any, code: int, message: str):
        """エラーレスポンスを送信"""
        response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message}
        }
        self._send_raw(response)

    def _is_connected(self) -> bool:
        """接続がまだ有効かチェック"""
        try:
            # getpeername() は切断されていると例外を発生させる
            self.conn.getpeername()
            # さらに確実にするため、ソケットのエラー状態をチェック
            self.conn.setblocking(False)
            try:
                # 0バイトのpeekで接続状態を確認
                data = self.conn.recv(1, socket.MSG_PEEK)
                if data == b'':
                    return False  # 相手が切断
            except BlockingIOError:
                pass  # データがないだけ、接続は有効
            except ConnectionResetError:
                return False
            finally:
                self.conn.setblocking(True)
            return True
        except (OSError, socket.error):
            return False

    def _send_raw(self, data: Dict[str, Any]):
        """生データを送信"""
        # 接続チェック（脆弱性: 切断検出後にorphanに保存する経路がある）
        if not self._is_connected():
            raise ConnectionError("Client disconnected")
        message = json.dumps(data) + "\n"
        self.conn.sendall(message.encode("utf-8"))


def run_server(port=PORT):
    """サーバーを起動"""
    print("=" * 60)
    print("[SERVER] Local JSON-RPC teaching server (not MCP)")
    print("=" * 60)
    print(f"[SERVER] Port: {port}; discard_orphans={discard_orphans}")
    print(f"[SERVER] 登録ユーザー: {', '.join(USER_SECRETS.keys())}")
    print()
    print("[SERVER] 脆弱性:")
    print("  1. login selects a simulated role; it does not authenticate")
    print("  2. orphan response をグローバルリストに保存")
    print("  3. get_orphans メソッドで他ユーザーのデータにアクセス可能")
    print()
    print("[SERVER] 停止するには Ctrl+C を押してください")
    print("=" * 60)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, port))
    server.listen(5)
    print(f"READY {server.getsockname()[1]}", flush=True)

    try:
        while True:
            conn, addr = server.accept()
            handler = VulnerableClientHandler(conn, addr)
            thread = threading.Thread(target=handler.handle)
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        print("\n[SERVER] シャットダウン")
    finally:
        server.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Loopback-only orphan storage demonstration")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--discard-orphans", action="store_true")
    options = parser.parse_args()
    if not 0 <= options.port <= 65535:
        parser.error("port must be in 0..65535")
    discard_orphans = options.discard_orphans
    run_server(options.port)
