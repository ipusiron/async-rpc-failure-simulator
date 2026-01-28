#!/usr/bin/env python3
"""
堅牢な実装でのテストシナリオ（scenarios_test_secure.py）

脆弱な実装（scenarios_test.py）との比較:

┌─────────────────┬──────────────────────────┬──────────────────────────┐
│ 項目            │ 脆弱な実装               │ 堅牢な実装               │
├─────────────────┼──────────────────────────┼──────────────────────────┤
│ request_id      │ 連番（1, 2, 3...）       │ 暗号論的乱数（予測不可） │
│ orphan response │ リストに保存             │ ログ出力して破棄         │
│ タイムアウト    │ 任意の値を許容           │ 範囲外は警告             │
│ 統計情報        │ なし                     │ orphan数等を記録         │
└─────────────────┴──────────────────────────┴──────────────────────────┘

実行方法:
  ./venv/bin/python mcp/scenarios_test_secure.py

期待される出力:
  - 機能テスト（SCENARIO 1〜3）は脆弱版と同様にPASS
  - SCENARIO 4では orphan が「破棄」されたことを確認
  - 最後に統計情報を表示
"""

import os
import sys
import time
from concurrent.futures import TimeoutError as FutureTimeoutError

# 同じディレクトリの secure_client をインポート
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from secure_client import SecureStdioMcpClient, log_security

SERVER_PATH = os.path.join(HERE, "demo_server.py")


def header(title: str):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def scenario_handshake(client: SecureStdioMcpClient):
    header("SCENARIO 1: Handshake（initialize → initialized通知 → ping）")

    resp = client.request("initialize", {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "secure-client", "version": "0.1.0"}
    })

    if "result" in resp and "serverInfo" in resp["result"]:
        print("[PASS] initialize 応答OK:", resp["result"]["serverInfo"])
    else:
        print("[FAIL] initialize 応答が想定外:", resp)

    client.notify("notifications/initialized", {})
    print("[INFO] notifications/initialized を送信")

    resp = client.request("ping", {})
    if resp.get("result") == {}:
        print("[PASS] ping 応答OK")
    else:
        print("[FAIL] ping 応答が想定外:", resp)


def scenario_demux_async(client: SecureStdioMcpClient):
    header("SCENARIO 2: 非同期demux（2リクエストを投げて逆順で回収）")

    id1, fut1 = client.send_request("tools/call", {
        "name": "add_numbers",
        "arguments": {"a": 1, "b": 2}
    })
    id2, fut2 = client.send_request("tools/call", {
        "name": "add_numbers",
        "arguments": {"a": 40, "b": 2}
    })

    # 【堅牢化の効果】IDが暗号論的乱数なので予測不可能
    print(f"[INFO] dispatched id1={id1[:8]}... id2={id2[:8]}...")
    print("[INFO] ↑ IDが暗号論的乱数（連番ではない）ことを確認")

    resp2 = fut2.result(timeout=5)
    resp1 = fut1.result(timeout=5)

    n2 = int(resp2["result"]["content"][0]["text"])
    n1 = int(resp1["result"]["content"][0]["text"])

    if (n1, n2) == (3, 42):
        print("[PASS] demux 成功: results =", n1, n2)
    else:
        print("[FAIL] demux 失敗（取り違え疑い）:", n1, n2)


def scenario_tool_error(client: SecureStdioMcpClient):
    header("SCENARIO 3: ツールレベルエラー（unknown tool → result.isError）")

    resp = client.request("tools/call", {
        "name": "no_such_tool",
        "arguments": {"a": 1, "b": 1}
    })

    result = resp.get("result")
    if isinstance(result, dict) and result.get("isError") is True:
        print("[PASS] ツールエラーを検出:", result["content"][0]["text"])
    else:
        print("[FAIL] 期待したエラー形式ではない:", resp)


def scenario_timeout_orphan_secure(client: SecureStdioMcpClient):
    header("SCENARIO 4: タイムアウト → orphan破棄の確認（堅牢版）")

    ms = 300
    timeout_sec = 0.05

    print("[INFO] 脆弱な実装との違い:")
    print("       - 脆弱: orphan_responses リストに保存（再利用可能）")
    print("       - 堅牢: ログ出力して破棄（再利用不可）")
    print()

    orphans_before = client.stats["orphans_discarded"]

    try:
        # 短いタイムアウトには警告が出る（堅牢化ポイント3）
        client.request("tools/call", {
            "name": "sleep_ms",
            "arguments": {"ms": ms}
        }, timeout=timeout_sec)
        print("[FAIL] 期待した TimeoutError が発生しなかった")
        return
    except FutureTimeoutError:
        print(f"[PASS] TimeoutError を観測（timeout={timeout_sec}s, sleep={ms}ms）")

    # orphan が到着するのを待つ
    time.sleep(ms / 1000.0 + 0.1)

    orphans_after = client.stats["orphans_discarded"]

    if orphans_after > orphans_before:
        print(f"[PASS] orphan response を破棄（カウント: {orphans_before} → {orphans_after}）")
        print("[INFO] 堅牢な実装では orphan はリストに保存されず、再利用できない")
    else:
        print("[WARN] orphan response を検出できなかった（タイミング依存）")


def scenario_compare_implementations():
    header("SCENARIO 5: 脆弱な実装との比較サマリー")

    print("""
┌─────────────────────────────────────────────────────────────────────┐
│ 比較項目            │ 脆弱な実装           │ 堅牢な実装            │
├─────────────────────────────────────────────────────────────────────┤
│ request_id生成      │ self._next_id += 1   │ secrets.token_hex()   │
│                     │ → 1, 2, 3...（予測可）│ → ランダム（予測不可）│
├─────────────────────────────────────────────────────────────────────┤
│ orphan response     │ orphan_responses     │ stats["orphans_       │
│                     │   .append(data)      │   discarded"] += 1    │
│                     │ → 再利用可能         │ → 破棄（再利用不可）  │
├─────────────────────────────────────────────────────────────────────┤
│ タイムアウト検証    │ なし                 │ MIN/MAX範囲チェック   │
│                     │                      │ → 範囲外は警告        │
├─────────────────────────────────────────────────────────────────────┤
│ セキュリティログ    │ なし                 │ log_security() で     │
│                     │                      │ stderr に出力         │
└─────────────────────────────────────────────────────────────────────┘

【防止できる攻撃】
1. ID予測攻撃: 連番だと攻撃者が次のIDを予測し、偽レスポンスを注入可能
   → 暗号論的乱数で予測不可能に

2. Orphan再利用攻撃: タイムアウト後のレスポンスを別リクエストに紐づけ
   → 破棄することで再利用を防止

3. タイムアウト操作DoS: 極端に長いタイムアウトでリソース占有
   → 範囲チェックで抑制
""")


def main():
    python_exe = sys.executable
    if not os.path.exists(SERVER_PATH):
        print(f"[FATAL] サーバースクリプトが見つかりません: {SERVER_PATH}")
        sys.exit(1)

    print("=" * 72)
    print("堅牢な実装（SecureStdioMcpClient）でのテスト実行")
    print("=" * 72)

    client = SecureStdioMcpClient(python_exe=python_exe, server_script=SERVER_PATH)

    try:
        scenario_handshake(client)
        scenario_demux_async(client)
        scenario_tool_error(client)
        scenario_timeout_orphan_secure(client)
        scenario_compare_implementations()

    finally:
        header("CLEANUP & STATISTICS")
        stats = client.get_stats()
        print("[INFO] サーバー停止")
        print()
        print("【統計情報】")
        print(f"  - リクエスト送信数:    {stats['requests_sent']}")
        print(f"  - レスポンス受信数:    {stats['responses_received']}")
        print(f"  - タイムアウト発生数:  {stats['timeouts']}")
        print(f"  - orphan破棄数:        {stats['orphans_discarded']}")
        print()
        if stats['orphans_discarded'] > 0:
            print("[INFO] orphan response は保存されず、安全に破棄されました")

        client.close()


if __name__ == "__main__":
    main()
