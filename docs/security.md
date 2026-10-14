**日本語** | [English](en/security.md)

# 設計ミスとセキュリティ事例

[← READMEに戻る](../README.md)

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
| サーバー側キャンセル機構の欠如 | **リソース浪費** | クライアントがタイムアウトしてもサーバーは処理を続行し、CPU・DBコネクションを無駄に消費 |

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
2. サーバーが処理中、攻撃者Aはタイムアウトを発生させる
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
| **orphanは即座に破棄** | 台帳にないIDのレスポンスは件数だけ記録してペイロードは捨てる |
| **request_idは暗号論的乱数** | UUID v4やCSPRNGで生成し、予測不可能にする |
| **タイムアウトは固定値** | 外部入力でタイムアウト値を変更させない |
| **エラー種別を明確に分離** | プロトコルエラーはリトライ、ツールエラーはユーザーに通知 |
| **キャンセル機構の実装** | クライアントタイムアウト時にサーバーにキャンセル通知を送る |

---

### 脆弱な実装 vs 堅牢な実装（コード比較）

本リポジトリは同じ`client.py`を`discard_orphans`フラグで切り替え、観測・保存ポリシーと破棄ポリシーの両方を試せます。

#### 実行方法

```bash
# 脆弱な実装（失敗モードを観測）
./venv/bin/python mcp/scenarios_test.py

# 堅牢な実装（正しい設計を確認）
./venv/bin/python mcp/scenarios_test_secure.py
```

#### コード差分

| 観点 | 観測・保存（`discard_orphans=False`） | 破棄（`discard_orphans=True`） |
|------|----------------------------------|----------------------------------|
| **request_id生成** | `self._next_id += 1`（連番） | `secrets.token_hex(16)`（暗号論的乱数） |
| **orphan response** | `self.orphan_responses.append(data)`（保存） | `stats["orphans_discarded"] += 1`（破棄） |
| **タイムアウト** | `client.py`が有限・正の値を検証 | `secure_client.py`が範囲外を警告（値は変更しない） |
| **統計情報** | `get_stats()`で取得 | `get_stats()`で取得（`orphans_discarded`が増える） |

#### ID生成の比較

```python
# client.py の _issue_id：フラグ1つで連番/乱数を切り替える
def _issue_id(self):
    if self.discard_orphans:
        return secrets.token_hex(16)  # → "a3f8c9e1..."（予測不可能）
    self._next_id += 1
    return self._next_id              # → 1, 2, 3...（予測可能）
```

#### orphan処理の比較

```python
# client.py の _accept：フラグで保存/破棄を切り替える
if future is None or future.done():
    self.stats["orphans_observed"] += 1
    if self.discard_orphans:
        self.stats["orphans_discarded"] += 1   # ← 件数だけ記録（再利用不可）
    else:
        self.orphan_responses.append(data)      # ← 保存（再利用可能で危険）
```

#### 堅牢な実装の出力例

```
$ ./venv/bin/python mcp/scenarios_test_secure.py
[WARN] Timeout is outside the recommended 0.1-30 s range; not clamped.
...（SCENARIO 1〜4 の [PASS] が続く）
[PASS] orphan payload discarded
[PASS] timed-out request removed from pending
STATS {'requests_sent': 7, 'responses_received': 6, 'orphans_observed': 1, 'orphans_discarded': 1, 'timeouts': 1, 'invalid_messages': 0}
Random IDs are not authentication. Timeout warnings do not prevent DoS.
```
堅牢版では`orphan payload discarded`となり、`orphans_discarded`が1に増えます（脆弱版は`orphan retained only for observation`で0のまま）。

---

### 実際のセキュリティ事例・CVE

本シミュレーターで扱う失敗モードは、実際のプロダクトで深刻な脆弱性として報告されています。

#### 1. HTTP/2 Rapid Reset Attack（CVE-2023-44487）

**関連する失敗モード**: ストリーム多重化（demux）とリソース管理

| 項目 | 内容 |
|------|------|
| **CVSS** | 7.5（High） |
| **影響** | Google, Cloudflare, AWSなど主要クラウドで**史上最大規模のDDoS攻撃**に悪用 |
| **原因** | HTTP/2のストリームリセット機能を悪用。クライアントがリクエストを送信後すぐにキャンセル（RST_STREAM）を送ると、サーバー側では「ストリームはクローズ済み」と判断するが、**バックエンドでは非同期処理が継続**。これを大量に繰り返すことでリソース枯渇 |
| **本シミュレーターとの関連** | SCENARIO 4の「タイムアウト後もサーバーは処理を続ける」現象と同じ構造 |

> 参考: [Cloudflare - HTTP/2 Rapid Reset Attack](https://blog.cloudflare.com/technical-breakdown-http2-rapid-reset-ddos-attack/)

---

#### 2. レスポンスの取り違え（HTTP desync / response queue poisoning）

**関連する失敗モード**: レスポンスの取り違え（demux失敗）

| 項目 | 内容 |
|------|------|
| **影響** | リバースプロキシ経由で**別ユーザーのレスポンスが返される**情報漏洩 |
| **原因** | フロントエンドとバックエンドでリクエスト境界の解釈がずれ（desync）、接続を使い回す際に**次のリクエストに前のレスポンスが紛れ込む** |
| **本シミュレーターとの関連** | SCENARIO 2の「IDによるdemuxが正しく実装されていないとレスポンス取り違え」の実例 |

> 参考: [PortSwigger - HTTP request smuggling](https://portswigger.net/web-security/request-smuggling)

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
| **原因** | JSON-RPCサーバーがlocalhost上で認証なしで起動。ユーザーが悪意あるWebページを開くと、ブラウザ経由でウォレットAPIが呼び出される（DNS Rebinding / CSRF） |
| **本シミュレーターとの関連** | MCPサーバーも「stdioだから安全」と思い込みがちだが、プロセス間通信の経路によっては攻撃対象になりうる |

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
| レスポンスとリクエストの紐づけ（demux）が不完全 | レスポンス取り違え（HTTP desync） |
| 認証・認可チェックの層が曖昧 | Bugzilla JSON-RPC CSRF, CryptoNote |
| 時間差（TOCTOU）を考慮していない | Juniper RPC race condition |
| コンポーネント間のセマンティクス不整合 | Confusion Attacks |

**これらはすべて「設計段階での考慮漏れ」が原因であり、本シミュレーターはそれを事前に体験するためのツールです。**

---
