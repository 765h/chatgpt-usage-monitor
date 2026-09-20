# ChatGPT Usage Monitor

ChatGPT Plus / Pro のCodex使用率（5時間・週間）をWindowsのシステムトレイに表示します。

起動後はCodex app-serverの `account/rateLimits/read` を定期的に読み取り、応答の `rateLimits.primary` / `secondary` をSession / Weekly、`gpt-reserve` をLuna reserveとして表示します。APIキー、Chrome拡張、ブラウザCookieは読み取りません。会話本文も読み取りません。

ライブ取得に失敗した場合は古いJSONLへ戻さず、取得できた項目だけを表示します。
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
