#!/usr/bin/env python3
"""
Web UI サーバー

非同期RPCの失敗モードを視覚的に理解するためのWebインターフェースを提供します。
標準ライブラリのみ使用（外部依存なし）。

使用方法:
    ./venv/bin/python web/server.py

    ブラウザで http://localhost:8080 を開く
"""

import os
import sys
import http.server
import socketserver
import webbrowser
from functools import partial

# デフォルトポート
PORT = 8080

# このスクリプトのディレクトリ
HERE = os.path.dirname(os.path.abspath(__file__))


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """ログを抑制したHTTPハンドラー"""

    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        # リクエストごとのログを抑制（起動時のみ表示）
        pass


def main():
    port = PORT

    # コマンドライン引数でポートを指定可能
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"[ERROR] 無効なポート番号: {sys.argv[1]}")
            sys.exit(1)

    # ハンドラーを作成（web/ディレクトリを提供）
    handler = partial(QuietHandler, directory=HERE)

    try:
        with socketserver.TCPServer(("", port), handler) as httpd:
            url = f"http://localhost:{port}"
            print("=" * 60)
            print("Async RPC Failure Simulator - Web UI")
            print("=" * 60)
            print(f"サーバー起動: {url}")
            print("ブラウザで上記URLを開いてください")
            print("停止するには Ctrl+C を押してください")
            print("=" * 60)

            # 自動でブラウザを開く（オプション）
            try:
                webbrowser.open(url)
            except Exception:
                pass  # ブラウザが開けなくても続行

            httpd.serve_forever()

    except OSError as e:
        if "Address already in use" in str(e) or "既に使用中" in str(e):
            print(f"[ERROR] ポート {port} は既に使用されています")
            print(f"        別のポートを指定してください: python web/server.py 8081")
        else:
            print(f"[ERROR] サーバー起動エラー: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[INFO] サーバーを停止しました")


if __name__ == "__main__":
    main()
