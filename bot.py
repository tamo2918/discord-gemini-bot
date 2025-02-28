import os
import discord
from discord.ext import commands
import google.generativeai as genai
from dotenv import load_dotenv
import json
import datetime
from collections import defaultdict
import uuid
import PyPDF2
from langchain.text_splitter import RecursiveCharacterTextSplitter
import textwrap
from googleapiclient.discovery import build
import html
import requests
from bs4 import BeautifulSoup
import re
import base64

# Load environment variables from .env file
load_dotenv()

# Initialize Discord bot with command prefix
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# コマンドのエイリアス設定
COMMAND_ALIASES = {
    "ask": ["a", "質問"],
    "learn": ["l", "教える"],
    "search": ["s", "検索"],
    "forget": ["f", "忘れる"],
    "search_web": ["sw", "web", "ウェブ検索"],
    "learn_url": ["lu", "url", "URL学習"],
    "ask_url": ["au", "urlq", "URL質問"],
    "search_messages": ["sm", "メッセージ検索"],
    "search_history": ["sh", "履歴検索"],
    "search_all": ["sa", "全検索"],
    "learn_file": ["lf", "ファイル学習"],
    "forget_all": ["fa", "全忘却"],
    "forget_topic": ["ft", "トピック忘却"],
    "commands": ["help", "ヘルプ", "h", "cmd"],
    "analyze_image": ["ai", "image", "画像", "画像分析"]
}

# Configure Discord bot
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN not found in environment variables")

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# モデルの設定
# Gemini 1.5 Flashモデル（テキストと画像の両方に対応）
model = genai.GenerativeModel('models/gemini-1.5-flash')
print(f"Using Gemini model: models/gemini-1.5-flash")

# Google Custom Search API Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
ENABLE_WEB_SEARCH = GOOGLE_API_KEY is not None and GOOGLE_CSE_ID is not None
if ENABLE_WEB_SEARCH:
    print("Web search feature is enabled")
else:
    print("Web search feature is disabled. Set GOOGLE_API_KEY and GOOGLE_CSE_ID in .env file to enable.")

# AIの性格設定
AI_PERSONALITY = """あなたは親しみやすく、フレンドリーな会話AIです。
ユーザーからの質問に対して、丁寧かつカジュアルに回答してください。
日本語で話す場合は、「です・ます」調を基本としつつ、時々「だよ・だね」などの表現も使って親しみやすさを出してください。
絵文字は使わず、自然な会話を心がけてください。
あなたは現在の日付と時間を把握しており、日付や時間に関する質問に答えることができます。
あなたは話しかけているユーザーの名前を把握しており、ユーザーに合わせた応答ができます。
"""

# Conversation history storage
# Structure: {user_id: [{"role": "user/bot", "content": "message", "timestamp": "time", "username": "username", "nickname": "nickname"}]}
conversation_history = defaultdict(list)
MAX_HISTORY_LENGTH = 10  # Maximum number of messages to keep in history per user
SAVE_CONVERSATION_HISTORY = True  # 会話履歴を保存するかどうかのフラグ

# チャットセッションを保持する辞書
chat_sessions = {}

# Knowledge base functions
knowledge_base = {}

# File to store conversation history
HISTORY_FILE = "conversation_history.json"

# Load conversation history from file if it exists
def load_conversation_history():
    global conversation_history
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                # Convert from regular dict to defaultdict
                history_data = json.load(f)
                for user_id, messages in history_data.items():
                    conversation_history[user_id] = messages
            print(f"Loaded conversation history for {len(conversation_history)} users")
    except Exception as e:
        print(f"Error loading conversation history: {e}")

# Load knowledge base from file if it exists
def load_knowledge_base():
    global knowledge_base
    try:
        with open('knowledge_base.json', 'r', encoding='utf-8') as f:
            knowledge_base = json.load(f)
    except FileNotFoundError:
        knowledge_base = {}
    except json.JSONDecodeError:
        print("Error decoding knowledge base file. Starting with empty knowledge base.")
        knowledge_base = {}

# 知識ベースをファイルに保存する関数
def save_knowledge_base():
    try:
        with open('knowledge_base.json', 'w', encoding='utf-8') as f:
            json.dump(knowledge_base, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving knowledge base: {e}")

# Save conversation history to file
def save_conversation_history():
    if not SAVE_CONVERSATION_HISTORY:
        return  # 会話履歴を保存しない場合は何もしない
        
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(conversation_history, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving conversation history: {e}")

# Add message to conversation history
def add_to_history(user_id, role, content, username, nickname):
    if not SAVE_CONVERSATION_HISTORY:
        return  # 会話履歴を保存しない場合は何もしない
        
    timestamp = datetime.datetime.now().isoformat()
    conversation_history[user_id].append({
        "role": role,
        "content": content,
        "timestamp": timestamp,
        "username": username,
        "nickname": nickname
    })
    
    # Limit history length
    if len(conversation_history[user_id]) > MAX_HISTORY_LENGTH:
        conversation_history[user_id].pop(0)
    
    # Save to file
    save_conversation_history()

# Format conversation history for Gemini API
def format_history_for_gemini(user_id):
    """Format conversation history for Gemini API"""
    if user_id not in conversation_history or len(conversation_history[user_id]) == 0:
        return ""
    
    # 直近の会話を取得（最大10往復）
    recent_history = conversation_history[user_id][-10:]
    history_text_parts = []
    
    for msg in recent_history:
        # 古い形式の会話履歴に対応（username/nicknameフィールドがない場合）
        username = msg.get("username", "ユーザー")
        nickname = msg.get("nickname", username)
        
        if msg["role"] == "user":
            prefix = f"ユーザー ({username} / {nickname})"
        else:
            prefix = "アシスタント"
            
        history_text_parts.append(f"{prefix}: {msg['content']}")
    
    return "\n\n".join(history_text_parts)

# Gemini APIで会話を開始する関数
def start_gemini_chat(user_id):
    """Start a chat with Gemini API using conversation history"""
    # 会話履歴を再現せず、新しいチャットを開始する
    if user_id not in chat_sessions:
        chat_sessions[user_id] = model.start_chat(history=[])
    return chat_sessions[user_id]

# テキストを分割する関数
def split_text(text, chunk_size=1000, overlap=200):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len,
    )
    return text_splitter.split_text(text)

# PDFファイルからテキストを抽出する関数
def extract_text_from_pdf(file_path):
    with open(file_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text

# テキストファイルからテキストを抽出する関数
def extract_text_from_txt(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
        return file.read()

# ファイルから学習する関数
async def learn_from_file(file_path, user_id):
    """ファイルから情報を抽出して知識ベースに追加する"""
    file_extension = os.path.splitext(file_path)[1].lower()
    
    try:
        if file_extension == '.pdf':
            text = extract_text_from_pdf(file_path)
        elif file_extension == '.txt':
            text = extract_text_from_txt(file_path)
        else:
            return f"サポートされていないファイル形式です: {file_extension}"
        
        # テキストを分割
        chunks = split_text(text)
        
        # 各チャンクを知識ベースに追加
        added_count = 0
        for chunk in chunks:
            # 空のチャンクはスキップ
            if not chunk.strip():
                continue
                
            # 知識ベースに追加
            knowledge_id = str(uuid.uuid4())
            knowledge_base[knowledge_id] = {
                "content": chunk,
                "added_by": user_id,
                "timestamp": datetime.datetime.now().isoformat()
            }
            added_count += 1
        
        # 知識ベースを保存
        save_knowledge_base()
        
        return f"ファイルから {added_count} 個のチャンクを学習しました。"
    except Exception as e:
        return f"ファイルの処理中にエラーが発生しました: {str(e)}"

# Add a piece of knowledge to the knowledge base
def add_knowledge(content, user_id):
    knowledge_id = str(uuid.uuid4())
    knowledge_base[knowledge_id] = {
        "content": content,
        "added_by": user_id,
        "timestamp": datetime.datetime.now().isoformat()
    }
    save_knowledge_base()
    return knowledge_id

# Search for knowledge items related to the query
def search_knowledge(query):
    """Search for knowledge items related to the query"""
    query_lower = query.lower()
    
    # 日本語の場合は文字単位で分割、英語の場合は単語単位で分割
    has_japanese = any(ord(c) > 127 for c in query)
    if has_japanese:
        # 日本語の場合は2文字以上の部分文字列を抽出
        query_words = []
        for i in range(len(query_lower)):
            for j in range(i+2, min(i+10, len(query_lower)+1)):
                query_words.append(query_lower[i:j])
    else:
        # 英語の場合は単語単位で分割
        query_words = [word for word in query_lower.split() if len(word) > 1]
    
    results = []
    scores = {}
    
    for knowledge_id, data in knowledge_base.items():
        content_lower = data["content"].lower()
        score = 0
        
        # 完全一致の場合は高いスコア
        if query_lower in content_lower:
            score += 10
            
        # 部分一致の場合
        if has_japanese:
            # 日本語の場合は部分文字列のマッチを確認
            for word in query_words:
                if word in content_lower:
                    score += 2
                    
                    # 出現回数も考慮
                    score += content_lower.count(word) * 0.2
        else:
            # 英語の場合は単語単位でのマッチを確認
            for word in query_words:
                if word in content_lower:
                    score += 3
                    
                    # 単語の出現回数も考慮
                    score += content_lower.count(word) * 0.5
        
        if score > 0:
            scores[knowledge_id] = score
    
    # スコアの高い順にソート（最大5つまで）
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:5]
    
    for knowledge_id in sorted_ids:
        results.append(knowledge_base[knowledge_id])
    
    return results

# 現在の日付と時間を取得する関数
def get_current_datetime():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Google検索を実行する関数
def google_search(query, num_results=5):
    """
    Google Custom Search APIを使用してウェブ検索を実行する
    
    Args:
        query (str): 検索クエリ
        num_results (int): 取得する結果の数（最大10）
        
    Returns:
        list: 検索結果のリスト。各結果は辞書形式で、title, link, snippetを含む
    """
    if not ENABLE_WEB_SEARCH:
        return {"error": "Web search is not enabled. Set GOOGLE_API_KEY and GOOGLE_CSE_ID in .env file."}
    
    try:
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        result = service.cse().list(q=query, cx=GOOGLE_CSE_ID, num=num_results).execute()
        
        search_results = []
        if "items" in result:
            for item in result["items"]:
                # HTMLタグを除去してスニペットをクリーンアップ
                snippet = html.unescape(item.get("snippet", ""))
                
                search_results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": snippet
                })
        
        return search_results
    except Exception as e:
        print(f"Google Search API error: {e}")
        return {"error": f"検索中にエラーが発生しました: {str(e)}"}

# URLからコンテンツを取得する関数
def extract_content_from_url(url, max_length=8000):
    """
    指定されたURLからコンテンツを取得し、テキストとして返す
    
    Args:
        url (str): コンテンツを取得するURL
        max_length (int): 取得するテキストの最大長
        
    Returns:
        dict: 取得結果。成功した場合は title, content, url を含む。失敗した場合は error を含む。
    """
    try:
        # URLが有効かチェック
        if not url.startswith(('http://', 'https://')):
            return {"error": "無効なURLです。URLはhttp://またはhttps://で始まる必要があります。"}
        
        # リクエストを送信
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # エラーがあれば例外を発生
        
        # コンテンツタイプをチェック
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' not in content_type and 'application/xhtml+xml' not in content_type:
            return {"error": "このURLはHTMLページではありません。現在はHTMLページのみサポートしています。"}
        
        # BeautifulSoupでHTMLをパース
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # タイトルを取得
        title = soup.title.string if soup.title else "タイトルなし"
        
        # 不要なタグを削除
        for tag in soup(['script', 'style', 'head', 'header', 'footer', 'nav', 'aside']):
            tag.decompose()
        
        # テキストを取得
        text = soup.get_text(separator=' ', strip=True)
        
        # 余分な空白を削除
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 最大長に制限
        if len(text) > max_length:
            text = text[:max_length] + "...(省略)"
        
        return {
            "title": title,
            "content": text,
            "url": url
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"URLからのコンテンツ取得中にエラーが発生しました: {str(e)}"}
    except Exception as e:
        return {"error": f"予期しないエラーが発生しました: {str(e)}"}

# エイリアスを適用するデコレータ関数
def add_aliases(command_name):
    """コマンドにエイリアスを追加するデコレータ"""
    def decorator(func):
        # 元のコマンド名を保持
        func.command_name = command_name
        # エイリアスのリストを取得（存在しない場合は空リスト）
        aliases = COMMAND_ALIASES.get(command_name, [])
        # 元の関数を返す（デコレータチェーンで使用するため）
        return func
    return decorator

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is ready to use!')
    # Load conversation history when bot starts
    load_conversation_history()
    
    # エイリアス情報をログに出力
    print("\nコマンドエイリアス一覧:")
    for cmd, aliases in COMMAND_ALIASES.items():
        print(f"  !{cmd} -> {', '.join(['!' + alias for alias in aliases])}")
    print("\n")

@bot.command(name="commands")
@add_aliases("commands")
async def commands_help(ctx):
    """Show help information about the bot commands"""
    help_text = """
    **使用可能なコマンド一覧**
    
    **基本コマンド**
    `!ask <質問>` - AIに質問する (エイリアス: `!a`, `!質問`)
    `!learn <情報>` - 新しい知識をAIに教える (エイリアス: `!l`, `!教える`)
    `!search <キーワード>` - 知識ベースを検索する (エイリアス: `!s`, `!検索`)
    `!forget` - 会話履歴を忘れる (エイリアス: `!f`, `!忘れる`)
    
    **ウェブ検索と URL 関連**
    `!search_web <検索クエリ>` - ウェブ検索を実行し、結果に基づいて回答する (エイリアス: `!sw`, `!web`, `!ウェブ検索`)
    `!learn_url <URL>` - 指定したURLの内容を学習する (エイリアス: `!lu`, `!url`, `!URL学習`)
    `!ask_url <URL> <質問>` - 指定したURLの内容について質問する (エイリアス: `!au`, `!urlq`, `!URL質問`)
    
    **検索コマンド**
    `!search_messages <検索キーワード>` - チャンネル内のメッセージを検索する (エイリアス: `!sm`, `!メッセージ検索`)
    `!search_history <検索キーワード>` - あなたの会話履歴を検索する (エイリアス: `!sh`, `!履歴検索`)
    `!search_all <検索キーワード>` - チャンネルと会話履歴の両方を検索する (エイリアス: `!sa`, `!全検索`)
    
    **ファイルと画像関連**
    `!learn_file` - 添付ファイルから学習する（PDFまたはテキストファイル） (エイリアス: `!lf`, `!ファイル学習`)
    `!analyze_image [URL] [プロンプト]` - 画像を分析する。URLの代わりに画像を直接添付することも可能 (エイリアス: `!ai`, `!image`, `!画像`, `!画像分析`)
    
    **管理者コマンド**
    `!forget_all` - すべての知識を忘れる（管理者のみ） (エイリアス: `!fa`, `!全忘却`)
    `!forget_topic <トピック>` - 特定のトピックを忘れる (エイリアス: `!ft`, `!トピック忘却`)
    """
    await ctx.send(help_text)

@bot.command(name="ask")
@add_aliases("ask")
async def ask(ctx, *, question=None):
    """Ask a question to Gemini AI"""
    if question is None:
        await ctx.send("使用方法: `!ask <質問>`")
        return
    
    async with ctx.typing():
        try:
            user_id = str(ctx.author.id)
            
            # Add user message to history
            add_to_history(user_id, "user", question, ctx.author.name, getattr(ctx.author, 'nick', None) or ctx.author.name)
            
            # Search for related knowledge
            related_knowledge = search_knowledge(question)
            
            # Format prompt with related knowledge only if relevant knowledge is found
            current_datetime = get_current_datetime()
            user_name = ctx.author.name
            user_nickname = getattr(ctx.author, 'nick', None) or ctx.author.name
            
            if related_knowledge:
                context = "\n\n".join([f"{item['content']}" for item in related_knowledge])
                base_prompt = f"{AI_PERSONALITY}\n\n現在の日時: {current_datetime}\n\n話しかけているユーザー: {user_name} (ニックネーム: {user_nickname})\n\n以下は質問に関連する情報です：\n\n{context}\n\n上記の情報を参考にしながら、以下の質問に回答してください。ただし、情報が不足していても、一般的な知識に基づいて回答し、「その情報はありません」などの否定的な言及はしないでください: {question}"
            else:
                # No related knowledge found, just use the question directly without mentioning knowledge base
                base_prompt = f"{AI_PERSONALITY}\n\n現在の日時: {current_datetime}\n\n話しかけているユーザー: {user_name} (ニックネーム: {user_nickname})\n\n{question} この質問に回答してください。"
            
            # 会話履歴を含めたプロンプトを作成
            if user_id in conversation_history and len(conversation_history[user_id]) > 2:
                # 直近の会話を取得（最大10往復）
                recent_history = conversation_history[user_id][-10:-1]  # 最新のユーザーメッセージを除く
                history_text_parts = []
                
                for msg in recent_history:
                    # 古い形式の会話履歴に対応（username/nicknameフィールドがない場合）
                    username = msg.get("username", "ユーザー")
                    nickname = msg.get("nickname", username)
                    
                    if msg["role"] == "user":
                        prefix = f"ユーザー ({username} / {nickname})"
                    else:
                        prefix = "アシスタント"
                        
                    history_text_parts.append(f"{prefix}: {msg['content']}")
                
                history_text = "\n\n".join(history_text_parts)
                prompt_with_history = f"{base_prompt}\n\n以下は最近の会話履歴です。これを参考にして回答してください：\n\n{history_text}"
            else:
                prompt_with_history = base_prompt
            
            # Generate response using the model directly
            chat = start_gemini_chat(user_id)
            response = chat.send_message(prompt_with_history)
            
            # Get response text safely
            response_text = ""
            try:
                response_text = response.text
            except Exception as e:
                response_text = f"エラーが発生しました: {str(e)}"
            
            # Add bot response to history
            add_to_history(user_id, "bot", response_text, ctx.author.name, getattr(ctx.author, 'nick', None) or ctx.author.name)
            
            # Send response
            if len(response_text) > 2000:
                # Split into chunks of 2000 characters
                chunks = [response_text[i:i+2000] for i in range(0, len(response_text), 2000)]
                for chunk in chunks:
                    await ctx.send(chunk)
            else:
                await ctx.send(response_text)
        except Exception as e:
            await ctx.send(f"エラーが発生しました: {str(e)}")

@bot.command(name="learn")
@add_aliases("learn")
async def learn(ctx, *, information=None):
    """Teach the bot about a specific topic"""
    if information is None:
        await ctx.send("使用方法: `!learn <情報>`")
        return
        
    user_id = str(ctx.author.id)
    add_knowledge(information, user_id)
    await ctx.send(f"ありがとうございます！新しい知識を学習しました。")

@bot.command(name="search")
@add_aliases("search")
async def search(ctx, *, query=None):
    """Search for knowledge items related to the query"""
    if query is None:
        await ctx.send("使用方法: `!search <キーワード>`")
        return
    
    results = search_knowledge(query)
    
    if results:
        response = f"「{query}」に関連する情報が見つかりました:\n\n"
        
        for i, item in enumerate(results, 1):
            response += f"{i}. {item['content']}\n"
        
        await ctx.send(response)
    else:
        await ctx.send(f"「{query}」に関連する情報は見つかりませんでした。")

@bot.command(name="forget")
@add_aliases("forget")
async def forget(ctx):
    """Forget conversation history with this user"""
    user_id = str(ctx.author.id)
    if user_id in conversation_history:
        del conversation_history[user_id]
        save_conversation_history()
        
        # チャットセッションもリセット
        if user_id in chat_sessions:
            del chat_sessions[user_id]
            
        await ctx.send("会話履歴を忘れました。")
    else:
        await ctx.send("あなたとの会話履歴はありません。")

@bot.command(name="forget_all")
@add_aliases("forget_all")
async def forget_all(ctx):
    """Forget all knowledge (admin only)"""
    # 管理者権限を持つユーザーのみ実行可能
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("この操作は管理者のみ実行できます。")
        return
        
    global knowledge_base
    knowledge_base = {}
    save_knowledge_base()
    await ctx.send("すべての知識を忘れました。")

@bot.command(name="forget_topic")
@add_aliases("forget_topic")
async def forget_topic(ctx, *, topic=None):
    """Make the bot forget a specific topic"""
    if topic is None:
        await ctx.send("使用方法: `!forget_topic <トピック>`")
        return
        
    global knowledge_base
    
    if topic in knowledge_base:
        del knowledge_base[topic]
        save_knowledge_base()
        await ctx.send(f"「{topic}」に関する知識を忘れました。")
    else:
        await ctx.send(f"「{topic}」に関する知識は見つかりませんでした。")

@bot.command(name="search_web")
@add_aliases("search_web")
async def search_web(ctx, *, query=None):
    """ウェブ検索を実行してその結果を表示する"""
    if query is None:
        await ctx.send("使用方法: `!search_web <検索クエリ>`")
        return
    
    if not ENABLE_WEB_SEARCH:
        await ctx.send("ウェブ検索機能は現在無効です。管理者に連絡して、APIキーを設定してもらってください。")
        return
    
    async with ctx.typing():
        try:
            # 検索実行中のメッセージを送信
            processing_msg = await ctx.send("ウェブ検索を実行中です...")
            
            # Google検索を実行
            search_results = google_search(query)
            
            if isinstance(search_results, dict) and "error" in search_results:
                await processing_msg.edit(content=f"エラー: {search_results['error']}")
                return
            
            if not search_results:
                await processing_msg.edit(content=f"「{query}」に関する検索結果は見つかりませんでした。")
                return
            
            # 検索結果をフォーマット
            embed = discord.Embed(
                title=f"「{query}」の検索結果",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            
            for i, result in enumerate(search_results, 1):
                embed.add_field(
                    name=f"{i}. {result['title']}",
                    value=f"{result['snippet']}\n[リンク]({result['link']})",
                    inline=False
                )
            
            embed.set_footer(text="Powered by Google Custom Search")
            
            # 結果を送信
            await processing_msg.edit(content=None, embed=embed)
            
            # 検索結果をAIに送信して回答を生成
            result_text = "\n\n".join([f"タイトル: {r['title']}\n内容: {r['snippet']}\nURL: {r['link']}" for r in search_results])
            
            prompt = f"{AI_PERSONALITY}\n\n現在の日時: {get_current_datetime()}\n\n話しかけているユーザー: {ctx.author.name}\n\n以下はウェブ検索の結果です：\n\n{result_text}\n\n上記の検索結果を参考にして、次の質問に回答してください: {query}"
            
            # Geminiで回答を生成
            user_id = str(ctx.author.id)
            chat = start_gemini_chat(user_id)
            response = chat.send_message(prompt)
            
            # 回答を送信
            response_text = response.text
            
            # 回答が長い場合は分割して送信
            if len(response_text) > 2000:
                # Split into chunks of 2000 characters
                chunks = textwrap.wrap(response_text, width=2000, replace_whitespace=False, drop_whitespace=False)
                for chunk in chunks:
                    await ctx.send(chunk)
            else:
                await ctx.send(response_text)
            
            # 会話履歴に追加
            add_to_history(user_id, "user", f"ウェブ検索: {query}", ctx.author.name, getattr(ctx.author, 'nick', None) or ctx.author.name)
            add_to_history(user_id, "bot", response_text, ctx.author.name, getattr(ctx.author, 'nick', None) or ctx.author.name)
            
        except Exception as e:
            await ctx.send(f"エラーが発生しました: {str(e)}")

@bot.command(name="learn_url")
@add_aliases("learn_url")
async def learn_url(ctx, *, url=None):
    """指定されたURLからコンテンツを取得して学習する"""
    if url is None:
        await ctx.send("使用方法: `!learn_url <URL>`")
        return
    
    async with ctx.typing():
        try:
            # 処理中のメッセージを送信
            processing_msg = await ctx.send("URLからコンテンツを取得中です...")
            
            # URLからコンテンツを取得
            result = extract_content_from_url(url)
            
            if "error" in result:
                await processing_msg.edit(content=f"エラー: {result['error']}")
                return
            
            # コンテンツを知識ベースに追加
            title = result["title"]
            content = result["content"]
            
            # 知識ベースに追加する内容を整形
            knowledge_content = f"タイトル: {title}\nURL: {url}\n\n内容: {content}"
            
            # 知識ベースに追加
            user_id = str(ctx.author.id)
            add_knowledge(knowledge_content, user_id)
            
            # 成功メッセージを送信
            await processing_msg.edit(content=f"「{title}」のコンテンツを学習しました。このURLの内容について質問できるようになりました。")
            
        except Exception as e:
            await ctx.send(f"エラーが発生しました: {str(e)}")

@bot.command(name="ask_url")
@add_aliases("ask_url")
async def ask_url(ctx, url=None, *, question=None):
    """指定されたURLの内容について質問する"""
    if url is None or question is None:
        await ctx.send("使用方法: `!ask_url <URL> <質問>`")
        return
    
    async with ctx.typing():
        try:
            # 処理中のメッセージを送信
            processing_msg = await ctx.send("URLからコンテンツを取得中です...")
            
            # URLからコンテンツを取得
            result = extract_content_from_url(url)
            
            if "error" in result:
                await processing_msg.edit(content=f"エラー: {result['error']}")
                return
            
            # コンテンツを取得
            title = result["title"]
            content = result["content"]
            
            # 処理中メッセージを更新
            await processing_msg.edit(content=f"「{title}」の内容を分析中です...")
            
            # AIに質問を送信
            user_id = str(ctx.author.id)
            prompt = f"{AI_PERSONALITY}\n\n現在の日時: {get_current_datetime()}\n\n話しかけているユーザー: {ctx.author.name}\n\n以下はウェブページの内容です：\n\nタイトル: {title}\nURL: {url}\n\n内容: {content}\n\n上記のウェブページの内容に基づいて、次の質問に回答してください: {question}"
            
            # Geminiで回答を生成
            chat = start_gemini_chat(user_id)
            response = chat.send_message(prompt)
            
            # 回答を送信
            response_text = response.text
            
            # 処理中メッセージを削除
            await processing_msg.delete()
            
            # 回答が長い場合は分割して送信
            if len(response_text) > 2000:
                chunks = textwrap.wrap(response_text, width=2000, replace_whitespace=False, drop_whitespace=False)
                for chunk in chunks:
                    await ctx.send(chunk)
            else:
                await ctx.send(response_text)
            
            # 会話履歴に追加
            add_to_history(user_id, "user", f"URL「{title}」について質問: {question}", ctx.author.name, getattr(ctx.author, 'nick', None) or ctx.author.name)
            add_to_history(user_id, "bot", response_text, ctx.author.name, getattr(ctx.author, 'nick', None) or ctx.author.name)
            
        except Exception as e:
            await ctx.send(f"エラーが発生しました: {str(e)}")

@bot.command(name="learn_file")
@add_aliases("learn_file")
async def learn_file(ctx):
    """ファイルから学習する"""
    if not ctx.message.attachments:
        await ctx.send("ファイルを添付してください。サポートされている形式: PDF, TXT")
        return
    
    # 処理中のメッセージを送信
    processing_msg = await ctx.send("ファイルを処理中です...")
    
    results = []
    
    # 全ての添付ファイルを処理
    for attachment in ctx.message.attachments:
        file_extension = os.path.splitext(attachment.filename)[1].lower()
        
        if file_extension not in ['.pdf', '.txt']:
            results.append(f"{attachment.filename}: サポートされていないファイル形式です。PDFまたはTXTファイルを添付してください。")
            continue
        
        # 一時ファイルとして保存
        temp_file_path = f"temp_{attachment.filename}"
        await attachment.save(temp_file_path)
        
        # ファイルから学習
        result = await learn_from_file(temp_file_path, str(ctx.author.id))
        results.append(f"{attachment.filename}: {result}")
        
        # 一時ファイルを削除
        os.remove(temp_file_path)
    
    # 結果を送信
    await processing_msg.edit(content="\n\n".join(results))

@bot.command(name="search_messages")
@add_aliases("search_messages")
async def search_messages(ctx, *, query=None):
    """チャンネル内のメッセージを検索する"""
    if query is None:
        await ctx.send("使用方法: `!search_messages <検索キーワード>`")
        return
    
    try:
        # 処理中のメッセージを送信
        processing_msg = await ctx.send(f"「{query}」を含むメッセージを検索中...")
        
        # メッセージを検索（デフォルトで100件まで）
        messages = []
        async for msg in ctx.channel.history(limit=100):
            messages.append(msg)
        
        results = [msg for msg in messages if query.lower() in msg.content.lower()]
        
        if not results:
            await processing_msg.edit(content=f"「{query}」を含むメッセージは見つかりませんでした。")
            return
        
        # 検索結果を埋め込みメッセージとして表示
        embed = discord.Embed(
            title=f"「{query}」の検索結果 ({len(results)}件)",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        
        # 最大10件まで表示
        display_count = min(10, len(results))
        for i, msg in enumerate(results[:display_count], 1):
            # メッセージの内容を短く切り詰める（最大100文字）
            content = msg.content
            if len(content) > 100:
                content = content[:97] + "..."
            
            # 送信日時をフォーマット
            timestamp = msg.created_at.strftime("%Y/%m/%d %H:%M")
            
            embed.add_field(
                name=f"{i}. {msg.author.name} ({timestamp})",
                value=content,
                inline=False
            )
        
        if len(results) > 10:
            embed.set_footer(text=f"他 {len(results) - 10} 件の結果があります。より詳細な検索には !search_history コマンドをお使いください。")
        
        await processing_msg.edit(content=None, embed=embed)
        
    except Exception as e:
        await ctx.send(f"検索中にエラーが発生しました: {str(e)}")

@bot.command(name="search_history")
@add_aliases("search_history")
async def search_history(ctx, *, query=None):
    """会話履歴から検索する"""
    if query is None:
        await ctx.send("使用方法: `!search_history <検索キーワード>`")
        return
    
    user_id = str(ctx.author.id)
    
    try:
        # 処理中のメッセージを送信
        processing_msg = await ctx.send(f"会話履歴から「{query}」を検索中...")
        
        # 会話履歴を読み込む
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                conversation_history = json.load(f)
        else:
            conversation_history = {}
        
        user_history = conversation_history.get(user_id, [])
        query_lower = query.lower()
        results = [entry for entry in user_history if query_lower in entry.get("content", "").lower()]
        
        if not results:
            await processing_msg.edit(content=f"会話履歴から「{query}」は見つかりませんでした。")
            return
        
        # 検索結果を埋め込みメッセージとして表示
        embed = discord.Embed(
            title=f"会話履歴の検索結果: 「{query}」({len(results)}件)",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        # 最大10件まで表示
        display_count = min(10, len(results))
        for i, entry in enumerate(results[-display_count:], 1):  # 新しいものから表示
            # メッセージの内容を短く切り詰める（最大100文字）
            content = entry.get("content", "")
            if len(content) > 100:
                content = content[:97] + "..."
            
            # 送信者と日時を取得
            role = "あなた" if entry.get("role") == "user" else "ボット"
            timestamp = entry.get("timestamp", "不明")
            
            embed.add_field(
                name=f"{i}. {role} ({timestamp})",
                value=content,
                inline=False
            )
        
        if len(results) > 10:
            embed.set_footer(text=f"他 {len(results) - 10} 件の結果があります。")
        
        await processing_msg.edit(content=None, embed=embed)
        
    except Exception as e:
        await ctx.send(f"検索中にエラーが発生しました: {str(e)}")

@bot.command(name="search_all")
@add_aliases("search_all")
async def search_all(ctx, *, query=None):
    """チャンネル内のメッセージと会話履歴の両方を検索する"""
    if query is None:
        await ctx.send("使用方法: `!search_all <検索キーワード>`")
        return
    
    try:
        # 処理中のメッセージを送信
        processing_msg = await ctx.send(f"「{query}」を検索中...")
        
        # チャンネル内のメッセージを検索
        channel_results = []
        async for msg in ctx.channel.history(limit=50):
            if query.lower() in msg.content.lower():
                channel_results.append(msg)
        
        # 会話履歴を検索
        user_id = str(ctx.author.id)
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                conversation_history = json.load(f)
        else:
            conversation_history = {}
        
        user_history = conversation_history.get(user_id, [])
        query_lower = query.lower()
        history_results = [entry for entry in user_history if query_lower in entry.get("content", "").lower()]
        
        if not channel_results and not history_results:
            await processing_msg.edit(content=f"「{query}」を含む結果は見つかりませんでした。")
            return
        
        # 検索結果を埋め込みメッセージとして表示
        embed = discord.Embed(
            title=f"「{query}」の検索結果",
            description=f"チャンネル: {len(channel_results)}件, 会話履歴: {len(history_results)}件",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.now()
        )
        
        # チャンネルの検索結果（最大5件）
        if channel_results:
            channel_display = min(5, len(channel_results))
            channel_text = ""
            for i, msg in enumerate(channel_results[:channel_display], 1):
                content = msg.content
                if len(content) > 80:
                    content = content[:77] + "..."
                timestamp = msg.created_at.strftime("%m/%d %H:%M")
                channel_text += f"{i}. {msg.author.name} ({timestamp}): {content}\n\n"
            
            embed.add_field(
                name="チャンネルのメッセージ",
                value=channel_text or "なし",
                inline=False
            )
        
        # 会話履歴の検索結果（最大5件）
        if history_results:
            history_display = min(5, len(history_results))
            history_text = ""
            for i, entry in enumerate(history_results[-history_display:], 1):  # 新しいものから表示
                content = entry.get("content", "")
                if len(content) > 80:
                    content = content[:77] + "..."
                role = "あなた" if entry.get("role") == "user" else "ボット"
                timestamp = entry.get("timestamp", "不明")
                if len(timestamp) > 10:  # 日付部分だけ表示
                    timestamp = timestamp[:10]
                history_text += f"{i}. {role} ({timestamp}): {content}\n\n"
            
            embed.add_field(
                name="会話履歴",
                value=history_text or "なし",
                inline=False
            )
        
        # より詳細な検索のためのヒント
        embed.set_footer(text="より詳細な結果を見るには !search_messages または !search_history コマンドをお使いください。")
        
        await processing_msg.edit(content=None, embed=embed)
        
    except Exception as e:
        await ctx.send(f"検索中にエラーが発生しました: {str(e)}")

@bot.event
async def on_message(message):
    # Don't respond to our own messages
    if message.author == bot.user:
        return
    
    # Check if the message starts with the command prefix
    if message.content.startswith(bot.command_prefix):
        # Extract the command name without the prefix
        parts = message.content[len(bot.command_prefix):].strip().split(' ', 1)
        command_name = parts[0].lower()
        
        # Check if it's an alias
        original_command = None
        for cmd, aliases in COMMAND_ALIASES.items():
            if command_name in aliases:
                original_command = cmd
                break
        
        # If it's an alias, replace it with the original command
        if original_command:
            if len(parts) > 1:
                # Command with arguments
                new_content = f"{bot.command_prefix}{original_command} {parts[1]}"
            else:
                # Command without arguments
                new_content = f"{bot.command_prefix}{original_command}"
            
            # Update the message content
            message.content = new_content
    
    # Process commands
    await bot.process_commands(message)
    
    # If the message is a direct mention to the bot, treat it as !ask
    if bot.user.mentioned_in(message) and not message.mention_everyone:
        # Remove the mention from the message
        content = message.content
        for mention in message.mentions:
            content = content.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
        
        content = content.strip()
        if content:
            ctx = await bot.get_context(message)
            await ask(ctx, question=content)

# 画像を分析する関数
async def analyze_image_with_gemini(image_url, prompt=None):
    """
    Gemini 1.5 Flash APIを使用して画像を分析する
    
    Args:
        image_url (str): 分析する画像のURL
        prompt (str, optional): 画像分析のためのプロンプト。指定がない場合はデフォルトのプロンプトを使用
        
    Returns:
        str: 分析結果のテキスト
    """
    try:
        # 画像をダウンロード
        response = requests.get(image_url)
        if response.status_code != 200:
            return f"画像のダウンロードに失敗しました。ステータスコード: {response.status_code}"
        
        # 画像データの取得
        image_data = response.content
        
        # デフォルトのプロンプト
        if not prompt:
            prompt = "この画像について詳しく説明してください。何が写っているか、特徴的な要素、色合い、雰囲気などを教えてください。"
        
        # Gemini APIに送信するコンテンツの準備
        contents = [
            {
                "parts": [
                    {"text": f"{AI_PERSONALITY}\n\n{prompt}"},
                    {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(image_data).decode('utf-8')}}
                ]
            }
        ]
        
        # 画像分析を実行
        response = model.generate_content(contents)
        
        return response.text
    except Exception as e:
        return f"画像分析中にエラーが発生しました: {str(e)}"

@bot.command(name="analyze_image")
@add_aliases("analyze_image")
async def analyze_image(ctx, url=None, *, prompt=None):
    """画像を分析する"""
    # 画像URLが指定されていない場合、添付ファイルを確認
    if url is None:
        if not ctx.message.attachments:
            await ctx.send("画像を添付するか、画像のURLを指定してください。使用方法: `!analyze_image [URL] [プロンプト(省略可)]`")
            return
        # 最初の添付ファイルを使用
        url = ctx.message.attachments[0].url
    
    # 処理中メッセージを送信
    processing_msg = await ctx.send("画像を分析しています...")
    
    try:
        # 画像分析を実行
        result = await analyze_image_with_gemini(url, prompt)
        
        # 結果を送信
        if len(result) > 2000:
            # 長い結果は分割して送信
            chunks = textwrap.wrap(result, width=2000, replace_whitespace=False, drop_whitespace=False)
            await processing_msg.edit(content=chunks[0])
            for chunk in chunks[1:]:
                await ctx.send(chunk)
        else:
            await processing_msg.edit(content=result)
    except Exception as e:
        await processing_msg.edit(content=f"エラーが発生しました: {str(e)}")

# Run the bot
if __name__ == "__main__":
    load_knowledge_base()
    bot.run(DISCORD_TOKEN)
