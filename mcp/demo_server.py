#!/usr/bin/env python3
import sys
import json
import time
import math

# ============================================================
# stdioユーティリティ
# ============================================================

def send_message(obj: dict):
    """
    stdout に JSON メッセージを 1 行で送信する。
    stdio transport の仕様上、stdout には JSON 以外を出してはいけない。
    """
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def log(msg: str):
    """
    デバッグ・ログ出力用。
    stdout ではなく stderr に出力すること。
    """
    print(msg, file=sys.stderr, flush=True)


# ============================================================
# ツール実装
# ============================================================

def tool_add_numbers(args: dict):
    """
    a と b を足し算するデモ用ツール（正常系確認用）
    """
    a = args.get("a")
    b = args.get("b")

    if not finite_number(a) or not finite_number(b):
        return {
            "isError": True,
            "content": [
                {"type": "text", "text": "Invalid arguments"}
            ],
        }

    if not finite_number(a + b):
        return {"isError": True, "content": [{"type": "text", "text": "Result out of range"}]}
    return {
        "content": [
            {"type": "text", "text": str(a + b)}
        ]
    }


def tool_sleep_ms(args: dict):
    """
    指定したミリ秒だけ sleep するツール。
    タイムアウトや遅延レスポンス（orphan response）を
    確実に再現するために使用する。
    """
    ms = args.get("ms")

    if not finite_number(ms) or not 0 <= ms <= 5000:
        return {
            "isError": True,
            "content": [
                {"type": "text", "text": "Invalid arguments"}
            ],
        }

    time.sleep(ms / 1000.0)

    return {
        "content": [
            {"type": "text", "text": f"slept {ms} ms"}
        ]
    }


# ============================================================
# ツール登録
# ============================================================

TOOLS = {
    "add_numbers": tool_add_numbers,
    "sleep_ms": tool_sleep_ms,
}


def list_tools():
    """
    tools/list 用のレスポンスを生成する。
    Inspector の Tools タブで表示される。
    """
    return [
        {
            "name": "add_numbers",
            "description": "2つの数値を足し算する",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
        },
        {
            "name": "sleep_ms",
            "description": "指定したミリ秒だけ待機する（タイムアウト実験用）",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "ms": {"type": "number", "minimum": 0, "maximum": 5000},
                },
                "required": ["ms"],
            },
        },
    ]


# ============================================================
# リクエスト処理
# ============================================================

def finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def protocol_error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle_request(msg: dict):
    """
    1 件の MCP / JSON-RPC メッセージを処理する。
    """
    if (not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0"
            or not isinstance(msg.get("method"), str)):
        return protocol_error(None, -32600, "Invalid request")
    # All valid notifications are response-free, including unknown methods.
    if "id" not in msg:
        return None
    if msg["id"] is not None and type(msg["id"]) not in (int, str):
        return protocol_error(None, -32600, "Invalid request ID")
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params", {})
    if not isinstance(params, dict):
        return protocol_error(req_id, -32602, "Named parameters must be an object")

    # --- initialize ---
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2025-11-25",
                "capabilities": {
                    "resources": {},
                    "tools": {},
                },
                "serverInfo": {
                    "name": "async-rpc-failure-simulator",
                    "version": "0.1.0",
                },
            },
        }

    # --- notifications/initialized ---
    # --- ping ---
    if method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {},
        }
    
    # --- resources/list ---
    if method == "resources/list":
        # このデモサーバーは resources を提供しない（Inspector互換のため空配列を返す）
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "resources": []
            },
        }

    # --- resources/templates/list ---
    if method == "resources/templates/list":
        # このデモサーバーは resource template を提供しない
        # Inspector 互換のため、空配列を返す
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "resourceTemplates": []
            },
        }

    # --- tools/list ---
    if method == "tools/list":
        # Inspector 互換のため、配列そのものではなくオブジェクト内の tools 配列で返す
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": list_tools()
            },
        }

    # --- tools/call ---
    if method == "tools/call":
        params = msg.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not isinstance(tool_name, str) or not isinstance(arguments, dict):
            return protocol_error(req_id, -32602, "Invalid tools/call parameters")

        tool = TOOLS.get(tool_name)
        if tool is None:
            return protocol_error(req_id, -32602, "Unknown tool")

        result = tool(arguments)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result,
        }

    # --- 未知のメソッド ---
    return protocol_error(req_id, -32601, "Method not found")


# ============================================================
# メインループ（stdio）
# ============================================================

def main():
    # 起動ログ（stderr のみ）
    log("MCP デモサーバー起動（stdio transport）")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            send_message(protocol_error(None, -32700, "Parse error"))
            continue

        response = handle_request(msg)
        if response is not None:
            send_message(response)


if __name__ == "__main__":
    main()
