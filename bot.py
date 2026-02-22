import discord
from discord import app_commands
import os
import time
from collections import defaultdict
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

ROLE_NAME = "俺のあなる"
ALLOWED_USER_ID = int(os.environ.get('ALLOWED_USER_ID'))

# welcomeチャンネルのIDを保存する変数
welcome_channel_id = None

# 監視対象ユーザーのセット
suspicious_users = set()

# 最近入ってきたユーザーの記録 (時刻)
recent_joins = []

# メッセージ送信履歴 {user_id: [timestamp, ...]}
message_history = defaultdict(list)

def is_random_id(name: str) -> bool:
    """名前が乱雑なIDっぽいか判定（数字や記号が多い）"""
    digit_count = sum(c.isdigit() for c in name)
    return len(name) >= 6 and digit_count >= 4

class AuthView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ 認証する / Verify", style=discord.ButtonStyle.green, custom_id="auth_button")
    async def auth_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        role = discord.utils.get(guild.roles, name=ROLE_NAME)

        if role is None:
            await interaction.response.send_message("❌ ロールが見つかりません / Role not found. Please contact the server admin.", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("✅ すでに認証済みです！ / You are already verified!", ephemeral=True)
            return

        await interaction.user.add_roles(role)
        await interaction.response.send_message("🎉 認証完了！ようこそ！ / Verification complete! Welcome!", ephemeral=True)

        # 乱雑なIDかチェックして監視対象に追加
        if is_random_id(interaction.user.name):
            suspicious_users.add(interaction.user.id)
            print(f"👀 監視対象に追加: {interaction.user.name} ({interaction.user.id})")

@tree.command(name="role", description="認証パネルを設置します")
async def slash_role(interaction: discord.Interaction):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message("❌ このコマンドは使用できません / You do not have permission to use this command.", ephemeral=True)
        return

    embed = discord.Embed(
        title="👋 認証 / Verification",
        description="下のボタンを押して認証を完了してください。\nPlease press the button below to complete verification.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, view=AuthView())

@tree.command(name="welcome", description="このチャンネルに入退出メッセージを送るように設定します")
async def slash_welcome(interaction: discord.Interaction):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message("❌ このコマンドは使用できません / You do not have permission to use this command.", ephemeral=True)
        return

    global welcome_channel_id
    welcome_channel_id = interaction.channel_id
    await interaction.response.send_message("✅ このチャンネルをwelcomeチャンネルに設定しました！", ephemeral=True)

@client.event
async def on_member_join(member):
    global recent_joins

    # 乱雑なIDなら監視対象に追加
    if is_random_id(member.name):
        suspicious_users.add(member.id)
        print(f"👀 監視対象に追加(参加時): {member.name} ({member.id})")

    # 最近の参加記録に追加
    now = time.time()
    recent_joins.append((now, member))
    # 10秒以内の参加のみ残す
    recent_joins = [(t, m) for t, m in recent_joins if now - t <= 10]

    # 3〜5人が一気に入ってきたらタイムアウト
    if 3 <= len(recent_joins) <= 5:
        for join_time, join_member in recent_joins:
            try:
                await join_member.timeout(discord.utils.utcnow() + discord.timedelta(minutes=5))
                print(f"⏱️ 5分タイムアウト: {join_member.name}")
            except Exception as e:
                print(f"タイムアウト失敗: {e}")
        recent_joins = []

    # welcomeチャンネルに通知
    if welcome_channel_id is None:
        return
    channel = client.get_channel(welcome_channel_id)
    if channel is None:
        return
    member_count = member.guild.member_count
    embed = discord.Embed(
        title="🎉 メンバー参加 / Member Joined",
        description=f"{member.mention} が参加しました！\n{member.mention} has joined the server!",
        color=discord.Color.green()
    )
    embed.add_field(name="👥 現在のサーバー人数 / Member Count", value=f"{member_count}人")
    embed.set_thumbnail(url=member.display_avatar.url)
    await channel.send(embed=embed)

@client.event
async def on_member_remove(member):
    if welcome_channel_id is None:
        return
    channel = client.get_channel(welcome_channel_id)
    if channel is None:
        return
    member_count = member.guild.member_count
    embed = discord.Embed(
        title="👋 メンバー退出 / Member Left",
        description=f"{member.name} が退出しました。\n{member.name} has left the server.",
        color=discord.Color.red()
    )
    embed.add_field(name="👥 現在のサーバー人数 / Member Count", value=f"{member_count}人")
    embed.set_thumbnail(url=member.display_avatar.url)
    await channel.send(embed=embed)

@client.event
async def on_message(message):
    if message.author.bot:
        return
    if message.author.id not in suspicious_users:
        return

    user_id = message.author.id
    now = time.time()

    # 5秒以内のメッセージ履歴だけ残す
    message_history[user_id] = [t for t in message_history[user_id] if now - t <= 5]
    message_history[user_id].append(now)

    # 長い文字（20文字以上）が5秒間に8回以上送信されたら12時間タイムアウト
    if len(message_history[user_id]) >= 8 and len(message.content) >= 20:
        try:
            await message.author.timeout(discord.utils.utcnow() + discord.timedelta(hours=12))
            message_history[user_id] = []
            print(f"🚫 12時間タイムアウト: {message.author.name}")
            await message.channel.send(f"🚫 {message.author.mention} がスパムのため12時間タイムアウトされました。", delete_after=10)
        except Exception as e:
            print(f"タイムアウト失敗: {e}")

@client.event
async def on_ready():
    print(f"{client.user} としてログインしました")
    client.add_view(AuthView())
    await tree.sync()
    print("スラッシュコマンド同期完了")

# =============================================
# Render用ダミーHTTPサーバー
# =============================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Discord Bot is running!')

    def log_message(self, format, *args):
        return

def run_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f'HTTPサーバー起動: ポート {port}')
    server.serve_forever()

Thread(target=run_server, daemon=True).start()

TOKEN = os.environ.get('DISCORD_TOKEN')
if not TOKEN:
    print("エラー: DISCORD_TOKEN 環境変数が設定されていません。")
    exit(1)

client.run(TOKEN)
