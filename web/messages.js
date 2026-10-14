(function (root) {
  'use strict';
  const messages = {
    ja: {
      subtitle: 'タイムアウト後の応答を、保存・破棄の2つの方針で比べる',
      language: 'English', languageLabel: 'Switch to English',
      skip: '本文へ移動', runObserve: '観測用に保存を再生', runDiscard: '破棄を再生',
      clear: '停止してクリア', vulnerable: '観測用に保存', secure: '破棄',
      modelNote: '固定教材の再生です。Pythonサーバーやネットワークには接続しません。時刻・ID・件数はモデル値で、実測値ではありません。',
      boundaryNote: '保存するだけで情報漏洩が起こるとは限りません。別の利用者へ公開したり、別のリクエストに再利用したりする設計が問題になります。',
      client: 'クライアント', server: 'サーバー', request: '要求 →', response: '← 対応する応答',
      timeout: '待機期限切れ', orphan: '← 遅延応答を保存', discarded: '← 遅延応答を破棄',
      empty: '上の再生ボタンで、要求と応答の流れを確認できます。',
      statistics: 'モデルの件数', requests: '要求送信', responses: '要求に対応した応答',
      timeouts: 'タイムアウト', stored: '遅延応答の保存', disposed: '遅延応答の破棄',
      timeoutLabel: '50 msで待機を終了・台帳から削除',
      orphanLabel: '対応する待機要求なし（orphan）',
      comparison: '方針と限界', item: '項目', id: '要求ID',
      sequential: '連番。IDの一致で対応づける', random: 'ランダムIDの表記例。認証にはならない',
      orphanPolicy: '対応のない応答', retained: '観測用に最大100件保存。再割当てしない',
      dropped: '内容を保持せず件数を記録',
      timeoutPolicy: 'Pythonの待機時間', positive: '有限の正数を指定',
      warned: '0.1〜30秒の範囲外は警告。値は変更しない',
      guarantees: 'この教材が保証しないこと',
      limits: '送信元の認証、アクセス制御、サーバー側の処理中止、一般的なDoS対策は提供しません。IDの乱数化・stderrへのログ分離だけで攻撃を防げるわけではありません。',
      schedule: '時刻は要求送信からの経過を表す固定スケジュールです。sleep_ms(300)は700 msで送信され、1000 msで応答します。',
      countersNote: '遅延応答は「要求に対応した応答」に含めません。破棄してもタイムアウトの発生数は減りません。',
      running: '再生中：', finished: '再生完了：', cleared: '停止して表示をクリアしました。',
      ready: '再生する方針を選んでください。', readme: '使い方とPython実験', repository: 'GitHubリポジトリー'
    },
    en: {
      subtitle: 'Compare retaining and discarding responses that arrive after a timeout',
      language: '日本語', languageLabel: '日本語に切り替える',
      skip: 'Skip to content', runObserve: 'Play: retain for observation', runDiscard: 'Play: discard',
      clear: 'Stop and clear', vulnerable: 'Retain for observation', secure: 'Discard',
      modelNote: 'This plays a fixed teaching scenario. It does not connect to Python or a network. Times, IDs and counts are model values, not measurements.',
      boundaryNote: 'Retention alone does not necessarily leak information. Exposing stored responses to other users or reusing them for unrelated requests creates the problem.',
      client: 'Client', server: 'Server', request: 'Request →', response: '← Matched response',
      timeout: 'Wait expired', orphan: '← Retain late response', discarded: '← Discard late response',
      empty: 'Use a play button above to inspect the request and response flow.',
      statistics: 'Model counts', requests: 'Requests sent', responses: 'Responses matched to requests',
      timeouts: 'Timeouts', stored: 'Late responses retained', disposed: 'Late responses discarded',
      timeoutLabel: 'Stop waiting after 50 ms; remove pending entry',
      orphanLabel: 'No matching pending request (orphan)',
      comparison: 'Policies and limits', item: 'Item', id: 'Request ID',
      sequential: 'Sequential; correlate by matching ID', random: 'Illustrative random ID notation; not authentication',
      orphanPolicy: 'Unmatched responses', retained: 'Retain up to 100 for observation; never reassign',
      dropped: 'Count without retaining the payload',
      timeoutPolicy: 'Python wait timeout', positive: 'A finite positive number',
      warned: 'Warn outside 0.1–30 s; do not change the value',
      guarantees: 'What this teaching example does not guarantee',
      limits: 'It provides no sender authentication, access control, server-side cancellation, or general DoS protection. Random IDs and stderr logging alone do not prevent attacks.',
      schedule: 'Times form a fixed event schedule. sleep_ms(300) is sent at 700 ms and responds at 1000 ms.',
      countersNote: 'Late responses are not counted as matched responses. Discarding does not reduce the number of timeouts.',
      running: 'Playing: ', finished: 'Finished: ', cleared: 'Stopped and cleared the display.',
      ready: 'Choose a policy to play.', readme: 'Instructions and Python experiments', repository: 'GitHub repository'
    }
  };
  if (typeof module === 'object' && module.exports) module.exports = messages;
  else root.RpcMessages = messages;
})(typeof globalThis === 'object' ? globalThis : this);
