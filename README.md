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

**日本語** | [English](README.en.md)

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
- unknown toolによる **プロトコル層エラー（`-32602`）** と、不正な引数による **ツール層エラー（`result.isError`）** の違い
- プロトコル層エラーとアプリ層エラーの区別

※ 攻撃ツールではありません。**設計ミスがセキュリティ事故につながる境界**を学ぶための教材です。

---

## 📸 スクリーンショット

> ![テストプログラムである"scenarios_test.py"ファイルの実行結果](assets/screenshot.png)
>
> *テストプログラムである"scenarios_test.py"ファイルの実行結果*

> ![Web UIで「観測用に保存 vs 破棄」を比較](assets/screenshot2.png)
>
> *Web UIで「観測用に保存 vs 破棄」を比較*

---

## 想定読者

- 非同期処理に不慣れなエンジニア
- MCP/Agent/Tool callingを扱う開発者
- セキュリティ初学者〜中級者
- 「攻撃ではないが危険な設計」に関心のある人

---

## クイックスタート

- Python 3.9以上（標準ライブラリのみ・追加インストール不要）
- 詳しいセットアップ（venv/uv）・単体テスト・Inspector接続は [docs/tutorial.md](docs/tutorial.md) を参照

```bash
# 失敗モードの再現テスト
./venv/bin/python mcp/scenarios_test.py
# 堅牢版（破棄ポリシー）のテスト
./venv/bin/python mcp/scenarios_test_secure.py
# Web UI（ブラウザーで http://localhost:8080）
./venv/bin/python web/server.py
```

## 📚 ドキュメント

| ドキュメント | 内容 |
|------|------|
| [tutorial.md](docs/tutorial.md) | 学習ガイド・セットアップ・単体テスト・Inspector接続 |
| [scenarios.md](docs/scenarios.md) | 失敗モード再現（SCENARIO 1-4）・攻撃シナリオ・堅牢版の実験 |
| [security.md](docs/security.md) | 設計ミスが引き起こす問題・コード比較・実際のCVE事例 |
| [web-ui.md](docs/web-ui.md) | Web UIの使い方・CTFチャレンジ |

## 📁 ディレクトリ構造

```
async-rpc-failure-simulator/
├── README.md                      # 本ドキュメント（日本語）
├── CLAUDE.md                      # Claude Code向けガイド
├── LICENSE                        # MITライセンス
├── .gitignore
├── .nojekyll                      # GitHub Pages用（Jekyll無効化）
│
├── .github/
│   └── workflows/
│       └── test.yml               # CI（3テストをubuntu/Python3.11で実行）
│
├── mcp/                           # MCP実装（本体）
│   ├── demo_server.py             #   MCPサーバー（stdio transport、Inspector互換）
│   ├── client.py                  #   共有クライアント（discard_orphansフラグで保存/破棄を切替）
│   ├── scenarios_test.py          #   観測・保存ポリシーでのシナリオテスト
│   ├── secure_client.py           #   破棄ポリシーの薄いラッパー＋タイムアウト警告
│   └── scenarios_test_secure.py   #   破棄ポリシーでのシナリオテスト
│
├── web/                           # Web UI（視覚化ツール）
│   ├── index.html                 #   メインページ（マークアップ）
│   ├── style.css                  #   スタイル
│   ├── core.js                    #   シナリオ再生のロジック
│   ├── messages.js                #   日英の文言辞書
│   ├── app.js                     #   画面描画と日英切り替え
│   └── server.py                  #   Webサーバー（標準ライブラリのみ）
│
├── challenges/                    # CTF形式の攻撃体験チャレンジ
│   └── challenge1_orphan_hijack/  #   Challenge 1: Orphan Response Hijacking
│       ├── README.md              #     詳細な説明書
│       ├── vulnerable_server.py   #     攻撃対象の脆弱なサーバー
│       ├── exploit_template.py    #     穴埋め式の攻撃スクリプト（Easyモード）
│       ├── solution.py            #     模範解答
│       ├── integration_test.py    #     脆弱版success/安全版failを固定する統合テスト
│       ├── hint1.txt              #     ヒント1：攻撃の方向性
│       ├── hint2.txt              #     ヒント2：具体的なテクニック
│       └── hint_blackbox.txt      #     ブラックボックス攻撃の手法
│
├── docs/                          # 詳細ドキュメント（日本語）＋資料
│   ├── tutorial.md                #   学習ガイド・セットアップ・テスト
│   ├── scenarios.md               #   失敗モード再現・攻撃シナリオ・堅牢版の実験
│   ├── security.md                #   設計ミスの問題・コード比較・CVE事例
│   ├── web-ui.md                  #   Web UI・CTFチャレンジ
│   ├── en/                        #   同内容の英語版（tutorial/scenarios/security/web-ui）
│   └── Async_Failure_Simulator.pdf #   解説スライド
│
└── assets/                        # ドキュメント用画像
    ├── screenshot.png             #   テスト実行結果
    ├── screenshot2.png            #   Web UI（観測用に保存 vs 破棄）日本語
    ├── screenshot2.en.png         #   Web UI（英語）
    ├── screenshot_mobile.png      #   Web UI（モバイル幅）
    ├── inspector_demo_server.png  #   InspectorのResourcesタブ
    └── inspector_demo_server2.png #   InspectorのToolsタブ
```

---

## 📄 ライセンス

- ソースコードのライセンスは `LICENSE` ファイルを参照してください。

---

## 🛠️ このツールについて

本ツールは、「生成AIで作るセキュリティツール200」プロジェクトの一環として開発されました。
このプロジェクトでは、AIの支援を活用しながら、セキュリティに関連するさまざまなツールを200日間にわたり制作・公開していく取り組みを行っています。

プロジェクトの詳細や他のツールについては、以下のページをご覧ください。

🔗 [https://akademeia.info/?page_id=44607](https://akademeia.info/?page_id=44607)
