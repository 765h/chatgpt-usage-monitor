# Claude Usage Monitor

Claude Pro プランの使用率（5時間ウィンドウ・週間）を Windows システムトレイにリアルタイム表示する常駐アプリ。

![screenshot](https://github.com/user-attachments/assets/placeholder)

## 動作イメージ

- トレイアイコンに使用率（%）を数値で表示
- 50% 未満: 緑、80% 未満: 黄、80% 以上: 赤、100%: ×
- クリックでポップアップ表示（セッション・週間の詳細）

## アーキテクチャ

```
claude.ai (Chrome)
    └─ Chrome 拡張 (MV3 Service Worker)
           │  30秒ごとに /api/organizations/{id}/usage を取得
           ▼
   localhost:9876/usage  ← HTTP POST (JSON)
           │
    Python トレイアプリ
           └─ システムトレイアイコンを更新
```

Chrome 拡張がブリッジとして動作するため、Cookie 直接読み取りや外部 API キーは不要。

## 必要環境

- Windows 10/11
- Google Chrome
- Python 3.9+（開発・ビルド時のみ）

## インストール（exe を使う場合）

1. [Releases](../../releases) から `ClaudeMonitor.exe` をダウンロード
2. 実行する（UAC ダイアログが出るので「はい」）
3. Chrome を完全に再起動する
4. `claude.ai` にログインする

初回実行で以下が自動セットアップされます：

- Chrome 拡張を `%APPDATA%\ClaudeMonitor\` にコピー・ポリシー登録
- ログオン時自動起動タスクの登録
- トレイアプリの起動

## 開発セットアップ

```powershell
# 依存ライブラリのインストールと Chrome 拡張のパック
powershell -ExecutionPolicy Bypass -File setup.ps1

# 直接起動（開発時）
python main.py
```

## ビルド（exe 生成）

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
# -> dist/ClaudeMonitor.exe が生成される
```

`setup.ps1` で生成した `extension.pem` と `chrome_extension.crx` が必要です。

## ファイル構成

```
├── main.py                  # エントリーポイント・インストーラー
├── server.py                # localhost:9876 HTTP サーバー
├── tray.py                  # システムトレイ・ポップアップ UI
├── chrome_extension/
│   ├── manifest.json        # Chrome 拡張マニフェスト (MV3)
│   └── background.js        # Service Worker（使用量の取得・送信）
├── requirements.txt
├── setup.ps1                # 開発環境セットアップ
└── build.ps1                # PyInstaller ビルド
```

## 注意事項

- `claude.ai` の内部 API を使用しているため、Anthropic の仕様変更により動作しなくなる可能性があります
- Chrome の拡張機能ポリシー (`HKLM\SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist`) を変更するため、管理者権限が必要です

## ライセンス

MIT
