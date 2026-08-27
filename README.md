# ChatGPT Usage Monitor

ChatGPT Plus / Pro のCodex使用率（5時間・週間）をWindowsのシステムトレイに表示します。

Codexが `~/.codex/sessions/**/*.jsonl` に記録する最新の `rate_limits` を読み取ります。さらに、Codex app-serverの `account/rateLimits/read` から `gpt-reserve`（Luna reserve）を取得します。APIキー、Chrome拡張、ブラウザCookieは読み取りません。会話本文も読み取りません。

Luna reserveの取得に失敗した場合は、その行を表示せず、Session・Weeklyだけを表示します。
標準枠が上限に達してLuna reserveへ切り替わった場合は、トレイ数字に紫色の「L」バッジを表示します。

## 必要環境

- Windows 10/11
- CodexデスクトップアプリまたはCodex CLI
- Python 3.10+（開発・ビルド時のみ）

## インストール

1. [Releases](../../releases) から `ChatGPTUsageMonitor.exe` をダウンロード
2. `ChatGPTUsageMonitor.exe` を実行

初回実行時に `%APPDATA%\ChatGPTUsageMonitor\` へコピーし、Windowsログオン時の自動起動を登録します。

## 開発

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
python main.py
python -m unittest -v
```

Codexが一度も使用量を記録していない場合、トレイは「データ待機中」と表示します。

## ビルド

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
# dist/ChatGPTUsageMonitor.exe
```

## ライセンス

MIT
