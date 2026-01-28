<!--
---
id: day112
slug: async-rpc-failure-simulator

title: "Async RPC Failure Simulator"

subtitle_ja: "非同期RPCにおける設計誤りの再現シミュレーター"
subtitle_en: "Failure Mode Simulator for Asynchronous RPC Designs"

description_ja: "非同期RPCにおけるタイムアウト・遅延レスポンス（orphan）・ID取り違えといった設計上の失敗モードを再現・観測する教育用シミュレーター。"
description_en: "An educational simulator that reproduces and observes failure modes in asynchronous RPC designs, including timeouts, orphan responses, and request/response mismatches."

category_ja:
  - 設計ミス可視化
  - 非同期セキュリティ
category_en:
  - Design Failure Visualization
  - Asynchronous Security

difficulty: 4

tags:
  - async
  - rpc
  - mcp
  - timeout
  - orphan-response
  - demultiplex
  - security-design

repo_url: "https://github.com/ipusiron/async-rpc-failure-simulator"

hub: true
---
-->

# Async RPC Failure Simulator – 非同期RPCにおける設計誤りの再現シミュレーター

[![GitHub Repo](https://img.shields.io/badge/GitHub-async--rpc--failure--simulator-black?logo=github)](https://github.com/ipusiron/async-rpc-failure-simulator)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)
![MCP](https://img.shields.io/badge/MCP-stdio%20transport-orange)
![Status](https://img.shields.io/badge/Status-Experimental-yellow)

**Day112 - 生成AIで作るセキュリティツール200**

**Async RPC Failure Simulator** は、非同期RPCクライアントにおいて発生しがちな**タイムアウト・遅延レスポンス（orphan response）・ID取り違え**といった設計上の失敗モードを、**再現可能な実験**として観測するためのシミュレーターです。

本リポジトリではMCP（Model Context Protocol）のstdio transportを題材にしていますが、扱っている失敗モード自体は **非同期RPC全般に共通**するものです。

---

## 何ができるか

このツールで次の現象を再現・観測できます。

- 非同期RPCにおける **request / response の順不同**
- タイムアウト後に返ってくる **遅延レスポンス（orphan response）**
- タイムアウトによるpending台帳掃除と、その副作用
- unknown toolによる **ツール層エラー（`result.isError`）**
- プロトコル層エラーとアプリ層エラーの違い

※ 攻撃ツールではありません。**設計ミスがセキュリティ事故につながる境界**を学ぶための教材です。

---

## 📸 スクリーンショット

> ![テストプログラムである"scenarios_test.py"ファイルの実行結果](assets/screenshot.png)
>
> *テストプログラムである"scenarios_test.py"ファイルの実行結果*

---

## 想定読者

- 非同期処理に不慣れなエンジニア
- MCP/Agent/Tool callingを扱う開発者
- セキュリティ初学者〜中級者
- 「攻撃ではないが危険な設計」に関心のある人

---

## 前提条件

- Python 3.9以上
- 標準ライブラリのみ使用（追加ライブラリ不要）
- MCP Inspectorを使う場合はNode.js / npx

---

## セットアップ（venv）

今回はvenvを有効化せずに、絶対パスでvenvのPythonを使います。

```
ipusiron@MHL:~/async-rpc-failure-simulator$ pwd
/home/ipusiron/async-rpc-failure-simulator
ipusiron@MHL:~/async-rpc-failure-simulator$ python3 -m venv venv
ipusiron@MHL:~/async-rpc-failure-simulator$ ls -l ./venv/bin/python
lrwxrwxrwx 1 ipusiron ipusiron 7 Jan 29 02:46 ./venv/bin/python -> python3
ipusiron@MHL:~/async-rpc-failure-simulator$ ./venv/bin/python --version
Python 3.10.12
```

venvの環境構築ではまった場合は以下の記事を参考にしてください。

-[WSL2とvenvで分離するPython開発・実験環境設計【Windows編】](https://akademeia.info/?p=48605)

---

## MCPサーバーの単体テスト

MCPサーバーは以下の仕様とします。

- stdout：何も出ない（JSON専用）
- stderr：起動ログが出る
- [Ctrl]＋[C]キーで停止

```
ipusiron@MHL:~/async-rpc-failure-simulator$ ./venv/bin/python ./mcp/demo_server.py
MCP デモサーバー起動（stdio transport）
```
MCPサーバーを実行すると起動ログ「MCP デモサーバー起動（stdio transport）」が出力します。

問題は、この出力がstdout（標準出力）ではなくstderr（標準エラー出力）に出ているかどうかでです。
stdio transportではstdoutはJSONのみが絶対ルールだからです。

これがクリアすれば、Inspector互換の第一関門クリアです。

### テスト1　＜stdoutが汚れていないかチェック＞

そこで、以下のようにstdoutを"/tmp/mcp_stdout.txt"ファイルに出力するようにします。

```
ipusiron@MHL:~/async-rpc-failure-simulator$ ./venv/bin/python ./mcp/demo_server.py > /tmp/mcp_stdout.txt
MCP デモサーバー起動（stdio transport）
^C
Traceback (most recent call last):
  File "/home/ipusiron/async-rpc-failure-simulator/./mcp/demo_server.py", line 236, in <module>
    main()
  File "/home/ipusiron/async-rpc-failure-simulator/./mcp/demo_server.py", line 218, in main
    for line in sys.stdin:
KeyboardInterrupt

ipusiron@MHL:~/async-rpc-failure-simulator$ ls -l /tmp/mcp_stdout.txt
-rw-r--r-- 1 ipusiron ipusiron 0 Jan 29 02:55 /tmp/mcp_stdout.txt
ipusiron@MHL:~/async-rpc-failure-simulator$ wc -c /tmp/mcp_stdout.txt
0 /tmp/mcp_stdout.txt
```

サーバーを止めて（あるいは別Terminalから）、"/tmp/mcp_stdout.txt"ファイルのファイル容量をチェックします。
0バイトであれば空なので、確かに起動ログは標準エラー出力に出ていると判断できます。

### テスト2　＜手動で1発疎通（ping）＞

stdioは同一プロセスのstdinに送る必要があるので、簡単にやるなら1コマンドでまとめてこうします。

stdoutだけ確認してみます。

```
ipusiron@MHL:~/async-rpc-failure-simulator$ printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"ping"}' | ./venv/bin/python mcp/demo_server.py 2>/dev/null
{"jsonrpc": "2.0", "id": 1, "result": {}}
```

stderrだけ確認してみます。

```
ipusiron@MHL:~/async-rpc-failure-simulator$ printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"ping"}' | ./venv/bin/python mcp/demo_server.py 1>/dev/null
MCP デモサーバー起動（stdio transport）
```

---

## InspectorでMCPサーバーに接続する

以下のコマンドでInspector（疑似MCPクライアント＋UI）からMCPサーバーに接続してみます。

```
ipusiron@MHL:~/async-rpc-failure-simulator$ npx -y @modelcontextprotocol/inspector@0.19.0 --   ./venv/bin/python ./mcp/demo_server.py
```

InspectorのResources/Toolsタブを確認します。

> ![InspectorのResourcesタブ](inspector_demo_server.png)
>
> *InspectorのResourcesタブ*

> ![InspectorのToolsタブ](inspector_demo_server2.png)
>
> *InspectorのToolsタブ*

Inspector上で以下が確認できます。

- initialize
- resources/list（空配列）
- resources/templates/list（空配列）
- tools/list
- tools/call(add_numbers)
- tools/call(sleep_ms)

Inspectorの環境構築ではまった場合は以下の記事を参考にしてください。

-[「ホストOS上のMCP Inspector操作UIページ」から「WSL上のMCPサーバー」にConnectできない問題を解決した記録](https://akademeia.info/?p=48678)

---

## 失敗モード再現テスト（本体）

"mcp/scenarios_test.py"ファイルは、失敗ケースを再現するテスト用のMCPクライアントです。

```
ipusiron@MHL:~/async-rpc-failure-simulator$ ./venv/bin/python mcp/scenarios_test.py

========================================================================
SCENARIO 1: Handshake（initialize → initialized通知 → ping）
========================================================================
[PASS] initialize 応答OK: {'name': 'async-rpc-failure-simulator', 'version': '0.1.0'}
[INFO] notifications/initialized を送信
[PASS] ping 応答OK

========================================================================
SCENARIO 2: 非同期demux（2リクエストを投げて逆順で回収）
========================================================================
[INFO] dispatched id1=3, id2=4
[PASS] demux 成功: results = 3 42

========================================================================
SCENARIO 3: ツールレベルエラー（unknown tool → result.isError）
========================================================================
[PASS] ツールエラーを検出: Error: Unknown tool no_such_tool

========================================================================
SCENARIO 4: タイムアウト → 遅延レスポンス（orphan）観測
========================================================================
[PASS] TimeoutError を観測（timeout=0.05s, sleep=300ms）
[PASS] orphan response を観測: {'jsonrpc': '2.0', 'id': 6, 'result': {'content': [{'type': 'text', 'text': 'slept 300 ms'}]}}

========================================================================
CLEANUP
========================================================================
[INFO] サーバ停止
```

### 各シナリオの詳細解説

---

#### SCENARIO 1: Handshake（MCPプロトコルの初期化シーケンス）

```
Client                              Server
  │                                    │
  ├─ initialize (id=1) ───────────────→│  ← リクエスト（idあり、応答必須）
  │                                    │
  │←─────────────── serverInfo 応答 ───┤  ← 応答（同じid=1で返る）
  │                                    │
  ├─ notifications/initialized ───────→│  ← 通知（idなし、応答不要）
  │                                    │
  ├─ ping (id=2) ─────────────────────→│  ← リクエスト
  │                                    │
  │←─────────────────────── {} 応答 ───┤  ← 応答（id=2）
  │                                    │
```

**何が起きているか:**
1. `initialize`：クライアントがサーバに接続を開始。サーバは`serverInfo`（名前・バージョン）を返す
2. `notifications/initialized`：クライアントが初期化完了を通知。**通知には`id`がないため、サーバは応答しない**
3. `ping`：生存確認。空オブジェクト`{}`が返れば疎通OK

**学習ポイント:**
- JSON-RPCでは`id`があるメッセージは「リクエスト」、ないメッセージは「通知」
- 通知に応答を返すと、クライアント側で「orphan response」になる危険がある

---

#### SCENARIO 2: 非同期demux（多重化と順不同応答）

```
Client                              Server
  │                                    │
  ├─ add_numbers(1+2) [id=3] ─────────→│
  ├─ add_numbers(40+2) [id=4] ────────→│  ← 2つのリクエストを連続送信
  │                                    │
  │  （サーバは順番に処理するが、      │
  │    ネットワーク遅延で逆転する      │
  │    可能性がある）                  │
  │                                    │
  │←─────────────────── id=3, "3" ─────┤
  │←─────────────────── id=4, "42" ────┤
  │                                    │
```

**何が起きているか:**
1. クライアントは2つのリクエストを**待たずに**連続送信（fire-and-forget）
2. サーバは順番に処理して応答を返す
3. クライアントは**逆順（id=4を先に、id=3を後に）で結果を取得**
4. それでも`id`で突き合わせるので、結果を取り違えない

**テストコードの該当箇所:**
```python
# わざと逆順で待つ（順不同でも取り違えないことが本質）
resp2 = fut2.result(timeout=5)  # id=4 を先に待つ
resp1 = fut1.result(timeout=5)  # id=3 を後に待つ
```

**学習ポイント:**
- 非同期RPCでは応答順序は保証されない（ネットワーク遅延、サーバ内並列処理などで逆転しうる）
- **`id`による多重分離（demultiplex）が正しく実装されていないと、レスポンスの取り違え事故が起きる**
- このテストは「正しい実装なら取り違えない」ことを確認している

---

#### SCENARIO 3: ツールレベルエラー（result.isError）

```
Client                              Server
  │                                    │
  ├─ tools/call("no_such_tool") ──────→│
  │                                    │
  │←── result: {isError: true, ...} ───┤  ← JSON-RPC errorではない！
  │                                    │
```

**何が起きているか:**
1. 存在しないツール`no_such_tool`を呼び出す
2. サーバは**JSON-RPCのerrorフィールドではなく**、`result.isError`でエラーを返す

**応答の形式:**
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "isError": true,
    "content": [{"type": "text", "text": "Error: Unknown tool no_such_tool"}]
  }
}
```

**学習ポイント:**
- MCPでは「ツール層エラー」と「プロトコル層エラー」を区別している
- **プロトコル層エラー**（JSON-RPCレベル）: `{"error": {"code": -32601, "message": "..."}}` の形式
- **ツール層エラー**（MCP/アプリレベル）: `{"result": {"isError": true, ...}}` の形式
- この区別を誤ると、エラーハンドリングが破綻する（例：ツールエラーをプロトコルエラーとして処理してしまう）

---

#### SCENARIO 4: タイムアウト → 遅延レスポンス（orphan）観測

これが本シミュレーターの**核心シナリオ**です。

```
時間軸 →

Client                              Server
  │                                    │
  ├─ sleep_ms(300) [id=6] ────────────→│  t=0ms: リクエスト送信
  │                                    │
  │  [pending台帳]                     │
  │  id=6 → Future(waiting)            │
  │                                    │
  │  ... 50ms経過 ...                  │
  │                                    │
  ├─ TimeoutError発生! ─────────────── │  t=50ms: クライアント側タイムアウト
  │                                    │
  │  [pending台帳からid=6を削除]        │  ← ★ここが重要
  │  id=6 → (削除済み)                 │
  │                                    │
  │                                    │  ... サーバはまだ sleep 中 ...
  │                                    │
  │                                    │  t=300ms: サーバ処理完了
  │←──────────── id=6, "slept 300 ms" ─┤  ← レスポンスが返ってくる
  │                                    │
  │  [pending台帳を検索]                │
  │  id=6 → 見つからない！             │
  │                                    │
  │  → orphan_responses に追加         │  ← ★ orphan response の誕生
  │                                    │
```

**何が起きているか（ステップバイステップ）:**

1. **t=0ms**: クライアントが`sleep_ms(300)`を送信。`id=6`でpending台帳に登録
2. **t=0〜50ms**: クライアントは`timeout=0.05s`で応答を待機
3. **t=50ms**: タイムアウト発生。`TimeoutError`を投げ、**pending台帳からid=6を削除**
4. **t=50〜300ms**: サーバはまだ`sleep(300ms)`の最中。クライアントのタイムアウトを知らない
5. **t=300ms**: サーバが処理完了。`id=6`で応答を返す
6. **t=300ms+α**: クライアントのreaderスレッドが応答を受信。しかしpending台帳に`id=6`がない
7. **結果**: この応答は**orphan（孤児）response**として`orphan_responses`リストに格納

**テストコードの該当箇所:**
```python
# readerスレッドでの処理
if fut is None:
    # 台帳にない -> orphan（タイムアウト後の遅延レスポンス等）
    self.orphan_responses.append(data)
```

**なぜこれが問題になりうるか:**
- orphan responseを**再利用・キャッシュ**すると、後続リクエストと取り違える可能性がある
- 例：id=6のorphanを、次に発行したid=7のリクエストの応答として誤認識してしまう
- これは「設計ミス」であり、正しい実装では**orphanは破棄するか、明示的にログに記録する**

---

### これは異常ではない

上記のorphan response現象は**バグではなく、非同期RPCでは設計上必ず起こり得る現象**です。

- サーバはクライアントのタイムアウト設定を知らない
- クライアントが諦めても、サーバは処理を続ける（キャンセル機構がない限り）
- 遅延したレスポンスは必ず返ってくる

**重要なのは、この現象を想定した設計になっているかどうか**です。

---

### セキュリティ的な示唆

| 問題パターン | リスク | 対策 |
|-------------|--------|------|
| orphan responseを再利用 | レスポンスの取り違え（認証バイパス等の可能性） | orphanは即座に破棄、または厳格なログ記録 |
| unknown-idの応答を無視しない | 攻撃者が偽のレスポンスを注入可能 | unknown-idは警告ログ＋破棄 |
| ツール層エラーをプロトコル層エラーと混同 | 適切なリトライ・フォールバック処理の失敗 | エラー種別を明確に分離 |
| タイムアウト後もリソースを保持 | DoS（リソース枯渇） | タイムアウト時に台帳から確実に削除 |

---

## ⚠️ 設計ミスが引き起こす問題

本シミュレーターで再現した失敗モードは、実際のシステムでどのような問題を引き起こすのでしょうか。性能・運用・セキュリティの3つの観点から解説します。

### 性能への影響

| 設計ミス | 問題 | 具体例 |
|---------|------|--------|
| タイムアウト後もpending台帳を保持 | **メモリーリーク** | 長時間運用でpending台帳が肥大化し、OOM（Out of Memory）でクラッシュ |
| orphan responseを無限にバッファリング | **メモリー枯渇** | 遅延レスポンスを捨てずに溜め込み続けてヒープ領域を圧迫 |
| 同期的にレスポンスを待つ設計 | **スループット低下** | 1リクエストごとに待機するため、並列性が活かせない |
| demux処理のロック競合 | **レイテンシ増大** | 複数スレッドがpending台帳にアクセスする際のロック待ち |

### 運用トラブル

| 設計ミス | 問題 | 具体例 |
|---------|------|--------|
| orphan responseのログ出力がない | **障害原因の特定困難** | 「なぜかレスポンスが返ってこない」という報告に対し、原因がタイムアウトなのか通信エラーなのか判別できない |
| エラー種別（プロトコル層/ツール層）の混同 | **誤ったリトライ処理** | ツールエラー（業務ロジック失敗）をプロトコルエラー（一時的な障害）と誤認してリトライし続ける |
| request_idの重複・枯渇 | **レスポンス取り違え** | 32bit整数のIDがオーバーフローして過去のIDと衝突 |
| サーバ側キャンセル機構の欠如 | **リソース浪費** | クライアントがタイムアウトしてもサーバは処理を続行し、CPU・DBコネクションを無駄に消費 |

### セキュリティリスク（最重要）

| 設計ミス | 攻撃シナリオ | 影響度 |
|---------|-------------|--------|
| **orphan responseの再利用** | 攻撃者がタイミングを調整し、別ユーザーのレスポンスを自分のリクエストに紐づける | **Critical** - 認証バイパス、情報漏洩 |
| **unknown-idレスポンスの受け入れ** | 攻撃者が偽のレスポンス（任意のid）を注入し、クライアントに誤った結果を返させる | **High** - データ改ざん、ロジック操作 |
| **予測可能なrequest_id** | 連番や時刻ベースのIDを推測し、中間者攻撃でレスポンスを差し替え | **High** - セッションハイジャック |
| **エラーメッセージの過剰な情報開示** | ツールエラーにスタックトレースや内部パスを含めてしまう | **Medium** - 情報収集の足がかり |
| **タイムアウト値の外部制御** | ユーザー入力でタイムアウトを極端に長く設定させ、リソースを占有 | **Medium** - DoS |

### 実際のインシデント例（架空シナリオ）

```
【状況】
- MCPベースのAIエージェントが、外部APIを呼び出すツールを実装
- タイムアウト後のorphan responseを「キャッシュ」として再利用する設計

【攻撃】
1. 攻撃者Aが「ユーザーBの個人情報を取得」リクエストを送信
2. サーバが処理中、攻撃者Aはタイムアウトを発生させる
3. orphan response（ユーザーBの個人情報）がキャッシュに残る
4. 攻撃者Aが次のリクエストを送信
5. キャッシュからorphan responseが返され、ユーザーBの情報を取得

【根本原因】
- orphan responseを破棄せず再利用した設計ミス
- request_idとユーザーセッションの紐づけが不十分
```

### 正しい設計指針

| 原則 | 実装方法 |
|------|----------|
| **orphanは即座に破棄** | 台帳にないIDのレスポンスはログ出力後に捨てる |
| **request_idは暗号論的乱数** | UUID v4やCSPRNGで生成し、予測不可能にする |
| **タイムアウトは固定値** | 外部入力でタイムアウト値を変更させない |
| **エラー種別を明確に分離** | プロトコルエラーはリトライ、ツールエラーはユーザーに通知 |
| **キャンセル機構の実装** | クライアントタイムアウト時にサーバにキャンセル通知を送る |

---

### 実際のセキュリティ事例・CVE

本シミュレーターで扱う失敗モードは、実際のプロダクトで深刻な脆弱性として報告されています。

#### 1. HTTP/2 Rapid Reset Attack（CVE-2023-44487）

**関連する失敗モード**: ストリーム多重化（demux）とリソース管理

| 項目 | 内容 |
|------|------|
| **CVSS** | 7.5（High） |
| **影響** | Google, Cloudflare, AWSなど主要クラウドで**史上最大規模のDDoS攻撃**に悪用 |
| **原因** | HTTP/2のストリームリセット機能を悪用。クライアントがリクエストを送信後すぐにキャンセル（RST_STREAM）を送ると、サーバ側では「ストリームはクローズ済み」と判断するが、**バックエンドでは非同期処理が継続**。これを大量に繰り返すことでリソース枯渇 |
| **本シミュレーターとの関連** | SCENARIO 4の「タイムアウト後もサーバは処理を続ける」現象と同じ構造 |

> 参考: [Cloudflare - HTTP/2 Rapid Reset Attack](https://blog.cloudflare.com/technical-breakdown-http2-rapid-reset-ddos-attack/)

---

#### 2. Apache mod_proxy レスポンス混同（CVE-2020-11984等）

**関連する失敗モード**: レスポンスの取り違え（demux失敗）

| 項目 | 内容 |
|------|------|
| **影響** | Apacheリバースプロキシ経由で**別ユーザーのレスポンスが返される**情報漏洩 |
| **原因** | `mod_proxy_ajp`および`mod_proxy_http`がエラー処理時にバックエンド接続を適切にクローズせず、**次のリクエストに前のレスポンスが紛れ込む** |
| **本シミュレーターとの関連** | SCENARIO 2の「IDによるdemuxが正しく実装されていないとレスポンス取り違え」の実例 |

> 参考: [Apache HTTP Server 2.4 vulnerabilities](https://httpd.apache.org/security/vulnerabilities_24.html)

---

#### 3. Bugzilla JSON-RPC CSRF（CVE-2012-0440）

**関連する失敗モード**: JSON-RPCのセキュリティ設計

| 項目 | 内容 |
|------|------|
| **影響** | 認証済みユーザーのブラウザ経由で**任意のJSON-RPC APIを実行可能**。管理者権限奪取やセキュリティバグへのアクセス |
| **原因** | JSON-RPCエンドポイントがCSRFトークンチェックをバイパス可能だった。`Content-Type: application/json`の強制がなく、通常のフォーム送信で攻撃可能 |
| **本シミュレーターとの関連** | SCENARIO 3の「プロトコル層とツール層のエラー混同」—認証・認可チェックの層が曖昧だと悪用される |

> 参考: [Bugzilla Bug 718319](https://bugzilla.mozilla.org/show_bug.cgi?id=718319)

---

#### 4. Juniper Junos RPC Race Condition（CVE-2016-1267）

**関連する失敗モード**: 非同期処理のレースコンディション

| 項目 | 内容 |
|------|------|
| **影響** | 認証済みユーザーが**任意のファイルの所有権を奪取**し、root権限昇格 |
| **原因** | RPCにおける「lazy race condition」—権限チェックと実際の操作の間にタイミングギャップがあり、その間に状態を変更可能 |
| **本シミュレーターとの関連** | タイムアウトとorphan responseの間に「宙に浮いた状態」が生まれる問題と同様の時間差攻撃 |

> 参考: [Juniper Security Bulletin JSA10730](https://kb.juniper.net/InfoCenter/index?page=content&id=JSA10730)

---

#### 5. CryptoNote Wallet JSON-RPC 認証なし脆弱性

**関連する失敗モード**: JSON-RPCの認証設計

| 項目 | 内容 |
|------|------|
| **影響** | 暗号通貨ウォレットから**資金を窃取**可能 |
| **原因** | JSON-RPCサーバがlocalhost上で認証なしで起動。ユーザーが悪意あるWebページを開くと、ブラウザ経由でウォレットAPIが呼び出される（DNS Rebinding / CSRF） |
| **本シミュレーターとの関連** | MCPサーバも「stdioだから安全」と思い込みがちだが、プロセス間通信の経路によっては攻撃対象になりうる |

> 参考: [CryptoNote Unauthenticated JSON-RPC](https://www.ayrx.me/cryptonote-unauthenticated-json-rpc/)

---

#### 6. Orange Tsai's Confusion Attacks（2024年Black Hat発表）

**関連する失敗モード**: セマンティクスの混同

| 項目 | 内容 |
|------|------|
| **影響** | Apache HTTP Serverで**アクセス制御・認証バイパス、ファイルシステム全体へのアクセス、XSSからRCEへの昇格** |
| **原因** | `r->filename`の解釈がモジュールによって異なる（ファイルパス vs URL）。この**セマンティクスの不整合**が認証バイパスに直結 |
| **本シミュレーターとの関連** | SCENARIO 3の「ツール層エラーとプロトコル層エラーの混同」—層ごとのセマンティクスが曖昧だと、想定外の経路で機能が呼び出される |

> 参考: [Confusion Attacks - Orange Tsai](https://blog.orange.tw/posts/2024-08-confusion-attacks-en/)

---

#### まとめ：なぜこれらの脆弱性は生まれたか

| 根本原因 | 該当CVE/事例 |
|---------|-------------|
| 非同期処理でリソースのライフサイクル管理が不十分 | HTTP/2 Rapid Reset |
| レスポンスとリクエストの紐づけ（demux）が不完全 | Apache mod_proxy mixup |
| 認証・認可チェックの層が曖昧 | Bugzilla JSON-RPC CSRF, CryptoNote |
| 時間差（TOCTOU）を考慮していない | Juniper RPC race condition |
| コンポーネント間のセマンティクス不整合 | Confusion Attacks |

**これらはすべて「設計段階での考慮漏れ」が原因であり、本シミュレーターはそれを事前に体験するためのツールです。**

---

## 📁 ディレクトリ構造

```
async-rpc-failure-simulator/
├── README.md                 # 本ドキュメント
├── CLAUDE.md                 # Claude Code向けガイド
├── LICENSE                   # MITライセンス
├── .gitignore
├── .nojekyll                 # GitHub Pages用（Jekyll無効化）
│
├── mcp/                      # MCP実装（本体）
│   ├── demo_server.py        #   MCPサーバ（stdio transport、Inspector互換）
│   └── scenarios_test.py     #   失敗モード再現テストクライアント
│
└── assets/                   # ドキュメント用画像
    ├── screenshot.png        #   テスト実行結果
    ├── inspector_demo_server.png
    └── inspector_demo_server2.png
```

---

## 🔗 関連サイト

- [MCP uses JSON-RPC to encode messages.](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)


---

## 📄 ライセンス

- ソースコードのライセンスは `LICENSE` ファイルを参照してください。

---

## 🛠️ このツールについて

本ツールは、「生成AIで作るセキュリティツール200」プロジェクトの一環として開発されました。
このプロジェクトでは、AIの支援を活用しながら、セキュリティに関連するさまざまなツールを200日間にわたり制作・公開していく取り組みを行っています。

プロジェクトの詳細や他のツールについては、以下のページをご覧ください。

🔗 [https://akademeia.info/?page_id=44607](https://akademeia.info/?page_id=44607)