import discord
from discord import app_commands
import os
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

ROLE_NAME = "俺のあなる"
ALLOWED_USER_ID = int(os.environ.get('ALLOWED_USER_ID'))

# welcomeチャンネルのIDを保存する変数
welcome_channel_id = None

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
