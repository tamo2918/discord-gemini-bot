# Discord Gemini AI Bot

A Discord bot that uses Google's Gemini AI to generate responses.

## Features

- Responds to direct mentions with AI-generated content
- Provides a `!ask` command to ask questions to the AI
- Handles long responses by splitting them into multiple messages
- **Maintains conversation history** for context-aware responses
- **Custom knowledge base** that allows users to teach the bot about specific topics

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- A Discord account and a registered Discord application/bot
- A Google AI Studio account with access to the Gemini API

### Step 1: Get API Keys

1. **Discord Bot Token**:
   - Go to the [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application or select an existing one
   - Go to the "Bot" tab and click "Add Bot"
   - Under the "TOKEN" section, click "Copy" to copy your bot token

2. **Gemini API Key**:
   - Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create a new API key or use an existing one

### Step 2: Configure the Bot

1. Copy the `.env.example` file to a new file named `.env`:
   ```
   cp .env.example .env
   ```

2. Edit the `.env` file and replace the placeholder values with your actual API keys:
   ```
   DISCORD_TOKEN=your_discord_token_here
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Invite the Bot to Your Server

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your application
3. Go to the "OAuth2" tab and then "URL Generator"
4. Select the following scopes:
   - `bot`
   - `applications.commands`
5. Select the following bot permissions:
   - "Send Messages"
   - "Read Message History"
   - "Add Reactions"
   - "Use Slash Commands"
6. Copy the generated URL and open it in your browser
7. Select the server you want to add the bot to and follow the prompts

### Step 5: Run the Bot

```bash
python bot.py
```

## Usage

- Mention the bot in a message to get a response:
  ```
  @BotName What is the capital of Japan?
  ```

- Use the `!ask` command:
  ```
  !ask What is the capital of Japan?
  ```

### Learning Features

The bot has a built-in learning system that allows it to remember conversations and learn new information:

#### Conversation Memory

The bot remembers your conversation history to provide more context-aware responses. Commands:

- `!forget` - Makes the bot forget your conversation history

#### Custom Knowledge Base

You can teach the bot about specific topics that it will remember and use in future conversations:

- `!learn <topic> <information>` - Teach the bot about a specific topic
  ```
  !learn Tokyo Tokyo is the capital city of Japan with a population of over 13 million people.
  ```

- `!knowledge` - List all topics the bot knows about
  ```
  !knowledge
  ```

- `!knowledge <topic>` - Get information about a specific topic
  ```
  !knowledge Tokyo
  ```

- `!forget_topic <topic>` - Make the bot forget a specific topic
  ```
  !forget_topic Tokyo
  ```

When you ask a question that mentions a topic the bot has learned about, it will automatically include that knowledge in its response.

## Classiスクレイパー機能

このボットには、ベネッセの学校連絡サービス「Classi」から情報を自動的に取得し、ボットの知識ベースに追加する機能が含まれています。

### セットアップ方法

1. `.env`ファイルにClassiのログイン情報を追加します：
   ```
   CLASSI_USERNAME=あなたのClassiユーザー名
   CLASSI_PASSWORD=あなたのClassiパスワード
   ```

2. 必要なライブラリをインストールします：
   ```
   pip install selenium webdriver-manager schedule beautifulsoup4
   ```

3. Classiスクレイパーを実行します：
   ```
   python classi_scraper.py
   ```

### 機能

- Classiのお知らせを定期的に（デフォルトでは6時間ごとに）取得します
- 新しいお知らせを自動的にボットの知識ベースに追加します
- ボットはこれらの情報を使って質問に回答できるようになります

### 注意事項

- このスクリプトはWebスクレイピングを使用していて、Classiのウェブサイト構造が変更された場合は動作しなくなる可能性があります
- 学校や教育機関のポリシーに従って使用してください
- 個人情報の取り扱いには十分注意してください

## Notes

- The bot uses the Gemini Pro model, which has a knowledge cutoff date and may not have information about very recent events.
- Responses are limited by Discord's message length limits (2000 characters), but the bot will automatically split longer responses into multiple messages.
