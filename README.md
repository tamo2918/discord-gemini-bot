# Discord Gemini AI Bot

Discordで動作するGoogle Gemini AIを活用したチャットボットです。

## 主な機能

- AIによる自然な会話応答
- ウェブ検索機能による最新情報の提供
- URLからの情報取得と学習
- 会話履歴の保存と検索
- カスタム知識ベースによる学習機能
- PDFやテキストファイルからの学習機能
- 短縮コマンド（エイリアス）対応
- 画像分析機能

## セットアップ手順

### 必要条件

- Python 3.8以上
- Discordアカウントと登録済みのDiscordアプリケーション/ボット
- Google AI Studioアカウント（Gemini APIへのアクセス権付き）
- （オプション）Google Custom Search APIのアクセス権

### ステップ1: APIキーの取得

1. **Discord Bot Token**:
   - [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
   - 新しいアプリケーションを作成または既存のものを選択
   - 「Bot」タブで「Add Bot」をクリック
   - 「TOKEN」セクションの「Copy」をクリックしてボットトークンをコピー

2. **Gemini API Key**:
   - [Google AI Studio](https://makersuite.google.com/app/apikey)にアクセス
   - 新しいAPIキーを作成または既存のものを使用

3. **Google Custom Search API Key** (ウェブ検索機能用):
   - [Google Cloud Console](https://console.cloud.google.com/)で「Custom Search JSON API」を有効化
   - APIキーを作成
   - [Programmable Search Engine](https://programmablesearchengine.google.com/about/)でカスタム検索エンジンを作成し、検索エンジンIDを取得

### ステップ2: ボットの設定

1. `.env.example`ファイルを`.env`という名前の新しいファイルにコピー:
   ```
   cp .env.example .env
   ```

2. `.env`ファイルを編集し、プレースホルダーの値を実際のAPIキーに置き換え:
   ```
   DISCORD_TOKEN=あなたのDiscordトークン
   GEMINI_API_KEY=あなたのGemini APIキー
   GOOGLE_API_KEY=あなたのGoogle APIキー
   GOOGLE_CSE_ID=あなたの検索エンジンID
   ```

### ステップ3: 依存関係のインストール

```bash
pip install -r requirements.txt
```

### ステップ4: ボットをサーバーに招待

1. [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
2. アプリケーションを選択
3. 「OAuth2」タブ→「URL Generator」へ
4. 以下のスコープを選択:
   - `bot`
   - `applications.commands`
5. 以下のボット権限を選択:
   - 「メッセージを送信」
   - 「メッセージ履歴を読む」
   - 「リアクションを追加」
   - 「スラッシュコマンドを使用」
6. 生成されたURLをコピーしてブラウザで開く
7. ボットを追加したいサーバーを選択し、指示に従う

### ステップ5: ボットの実行

```bash
python bot.py
```

## 使用方法

### 基本コマンド

- `!ask <質問>` または `!a <質問>` - AIに質問する
- `!learn <情報>` または `!l <情報>` - 新しい知識をAIに教える
- `!search <キーワード>` または `!s <キーワード>` - 知識ベースを検索する
- `!forget` または `!f` - 会話履歴を忘れる
- `!commands` または `!help` - 使用可能なコマンド一覧を表示

### ウェブ検索と URL 関連

- `!search_web <検索クエリ>` または `!sw <検索クエリ>` - ウェブ検索を実行し、結果に基づいて回答する
- `!learn_url <URL>` または `!lu <URL>` - 指定したURLの内容を学習する
- `!ask_url <URL> <質問>` または `!au <URL> <質問>` - 指定したURLの内容について質問する

### 検索コマンド

- `!search_messages <検索キーワード>` または `!sm <検索キーワード>` - チャンネル内のメッセージを検索する
- `!search_history <検索キーワード>` または `!sh <検索キーワード>` - あなたの会話履歴を検索する
- `!search_all <検索キーワード>` または `!sa <検索キーワード>` - チャンネルと会話履歴の両方を検索する

### ファイル関連

- `!learn_file` または `!lf` - 添付ファイルから学習する（PDFまたはテキストファイル）

### 画像分析

- `!analyze_image [URL] [プロンプト]` または `!ai [URL] [プロンプト]` - Gemini 1.5 Flashモデルを使用して画像を分析する
  - URLの代わりに画像を直接添付することも可能
  - プロンプトを指定すると、特定の観点から画像を分析できます（例：「この画像に写っている建物の特徴を教えて」）

### 管理者コマンド

- `!forget_all` または `!fa` - すべての知識を忘れる（管理者のみ）
- `!forget_topic <トピック>` または `!ft <トピック>` - 特定のトピックを忘れる

## 学習機能

このボットには会話を記憶し、新しい情報を学習するシステムが組み込まれています：

### 会話メモリ

ボットはより文脈に沿った応答を提供するために会話履歴を記憶します。

### カスタム知識ベース

特定のトピックについてボットに教えることができ、ボットはそれを記憶して将来の会話で使用します：

```
!learn 東京 東京は日本の首都で、世界最大の都市圏の一つです。
```

### URLからの学習

ウェブページの内容を取得して知識ベースに追加できます：

```
!learn_url https://example.com/about-tokyo
```

### ファイルからの学習

PDFやテキストファイルをアップロードして、その内容をボットに学習させることができます：

```
!learn_file (ファイルを添付)
```

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細については[LICENSE](LICENSE)ファイルを参照してください。
