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

# Load environment variables from .env file
load_dotenv()

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

# Use the recommended model with full path
model = genai.GenerativeModel('models/gemini-1.5-flash')
print(f"Using Gemini model: models/gemini-1.5-flash")

# AIの性格設定
AI_PERSONALITY = """あなたは親しみやすく、フレンドリーな会話AIです。
ユーザーからの質問に対して、丁寧かつカジュアルに回答してください。
敬語は使いつつも、堅苦しくならないよう心がけてください。
日本語で話す場合は、「です・ます」調を基本としつつ、時々「だよ・だね」などの表現も使って親しみやすさを出してください。
絵文字は使わず、自然な会話を心がけてください。
あなたは現在の日付と時間を把握しており、日付や時間に関する質問に答えることができます。
あなたは話しかけているユーザーの名前を把握しており、ユーザーに合わせた応答ができます。
"""

# Set up Discord bot with intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

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
    return datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is ready to use!')
    # Load conversation history when bot starts
    load_conversation_history()

@bot.command(name="commands")
async def commands_help(ctx):
    """Show help information about the bot commands"""
    help_text = """
**使用可能なコマンド一覧**

**基本コマンド**
`!ask <質問>` - AIに質問する
`!learn <情報>` - 新しい知識をAIに教える
`!search <キーワード>` - 知識ベースを検索する
`!forget` - 会話履歴を忘れる

**ファイル関連**
`!learn_file` - 添付ファイルから学習する（PDFまたはテキストファイル）

**管理者コマンド**
`!forget_all` - すべての知識を忘れる（管理者のみ）
"""
    await ctx.send(help_text)

@bot.command(name="ask")
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
async def learn(ctx, *, information=None):
    """Teach the bot about a specific topic"""
    if information is None:
        await ctx.send("使用方法: `!learn <情報>`")
        return
        
    user_id = str(ctx.author.id)
    add_knowledge(information, user_id)
    await ctx.send(f"ありがとうございます！新しい知識を学習しました。")

@bot.command(name="search")
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

@bot.command(name="learn_file")
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

@bot.event
async def on_message(message):
    # Don't respond to our own messages
    if message.author == bot.user:
        return
    
    # Process commands first
    await bot.process_commands(message)
    
    # Check if the bot is mentioned or the message starts with the bot's name
    bot_mentioned = bot.user in message.mentions
    bot_name_mentioned = message.content.lower().startswith(bot.user.name.lower())
    
    if bot_mentioned or bot_name_mentioned:
        # Extract the actual message content
        content = message.content
        
        # Remove mentions from the content
        for mention in message.mentions:
            content = content.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
        
        # Remove the bot's name if it starts with it
        if bot_name_mentioned:
            content = content.replace(bot.user.name, '', 1)
        
        content = content.strip()
        
        if content:  # Only process if there's actual content after removing mentions
            try:
                user_id = str(message.author.id)
                
                # Let the user know we're processing their request
                async with message.channel.typing():
                    # Add user message to history
                    add_to_history(user_id, "user", content, message.author.name, getattr(message.author, 'nick', None) or message.author.name)
                    
                    # Search for related knowledge
                    related_knowledge = search_knowledge(content)
                    
                    # Format prompt with related knowledge only if relevant knowledge is found
                    current_datetime = get_current_datetime()
                    user_name = message.author.name
                    user_nickname = getattr(message.author, 'nick', None) or message.author.name
                    
                    if related_knowledge:
                        context = "\n\n".join([f"{item['content']}" for item in related_knowledge])
                        base_prompt = f"{AI_PERSONALITY}\n\n現在の日時: {current_datetime}\n\n話しかけているユーザー: {user_name} (ニックネーム: {user_nickname})\n\n以下は質問に関連する情報です：\n\n{context}\n\n上記の情報を参考にしながら、以下の質問に回答してください。ただし、情報が不足していても、一般的な知識に基づいて回答し、「その情報はありません」などの否定的な言及はしないでください: {content}"
                    else:
                        # No related knowledge found, just use the question directly without mentioning knowledge base
                        base_prompt = f"{AI_PERSONALITY}\n\n現在の日時: {current_datetime}\n\n話しかけているユーザー: {user_name} (ニックネーム: {user_nickname})\n\n{content} この質問に回答してください。"
                    
                    # Add conversation history if available
                    if user_id in conversation_history and len(conversation_history[user_id]) > 0:
                        # Format conversation history for the prompt
                        history_text = format_history_for_gemini(user_id)
                        
                        if history_text:
                            prompt_with_history = f"{base_prompt}\n\n以下は過去の会話履歴です：\n{history_text}"
                        else:
                            prompt_with_history = base_prompt
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
                        print(f"Error getting response text: {e}")
                        response_text = "すみません、回答の生成中にエラーが発生しました。"
                    
                    # Save conversation history
                    if SAVE_CONVERSATION_HISTORY:
                        conversation_history[user_id].append({
                            "role": "user",
                            "content": content,
                            "timestamp": datetime.datetime.now().isoformat(),
                            "username": message.author.name,
                            "nickname": getattr(message.author, 'nick', None) or message.author.name
                        })
                        conversation_history[user_id].append({
                            "role": "bot",
                            "content": response_text,
                            "timestamp": datetime.datetime.now().isoformat(),
                            "username": message.author.name,
                            "nickname": getattr(message.author, 'nick', None) or message.author.name
                        })
                        save_conversation_history()
                    
                    # Split long responses into chunks for Discord's message limit
                    if len(response_text) > 2000:
                        chunks = textwrap.wrap(response_text, width=2000, replace_whitespace=False, drop_whitespace=False)
                        for chunk in chunks:
                            await message.channel.send(chunk)
                    else:
                        await message.channel.send(response_text)
            except Exception as e:
                await message.channel.send(f"エラーが発生しました: {str(e)}")

# Run the bot
if __name__ == "__main__":
    load_knowledge_base()
    bot.run(DISCORD_TOKEN)
