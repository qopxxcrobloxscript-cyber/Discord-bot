import discord
from discord.ext import commands
from discord.ui import Button, View
import os
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# 環境変数を読み込む（Renderの環境変数を使用）
TOKEN = os.getenv('DISCORD_TOKEN')
ROLE_ID = int(os.getenv('ROLE_ID', '0'))
OWNER_ID = int(os.getenv('OWNER_ID', '0'))  # あなたのユーザーID

# Intentsの設定
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# botの初期化
bot = commands.Bot(command_prefix='!', intents=intents)

# 認証ボタン用のView
class AuthenticationView(View):
    def __init__(self):
        super().__init__(timeout=None)  # タイムアウトなし

    @discord.ui.button(
        label="認証する",
        style=discord.ButtonStyle.green,
        custom_id="auth_button"
    )
    async def auth_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """ボタンが押されたときの処理"""
        try:
            # ユーザーにロールを付与
            role = interaction.guild.get_role(ROLE_ID)
            if role is None:
                await interaction.response.send_message(
                    "❌ ロールが見つかりません。サーバー管理者に連絡してください。",
                    ephemeral=True
                )
                return

            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                f"✅ 認証完了！{role.mention} ロールが付与されました。",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ロール付与に失敗しました。botの権限を確認してください。",
                ephemeral=True
            )
        except Exception as e:
            print(f"エラー: {e}")
            await interaction.response.send_message(
                "❌ エラーが発生しました。",
                ephemeral=True
            )


@bot.event
async def on_command_error(ctx, error):
    """コマンドエラーの処理"""
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ このコマンドを実行する権限がありません。", ephemeral=True)
    else:
        print(f"エラー: {error}")


# オーナーのみコマンド実行可能にするチェック
def is_owner():
    def predicate(ctx):
        return ctx.author.id == OWNER_ID
    return commands.check(predicate)


@bot.event
async def on_ready():
    """botが起動したときの処理"""
    print(f'{bot.user} がログインしました')
    print(f'botのID: {bot.user.id}')


@bot.command(name='auth_setup')
@is_owner()
async def auth_setup(ctx):
    """認証ボタンを表示するコマンド（オーナーのみ）"""
    embed = discord.Embed(
        title="🔐 認証",
        description="下のボタンをクリックして認証を完了してください。",
        color=discord.Color.blue()
    )
    
    view = AuthenticationView()
    await ctx.send(embed=embed, view=view)
    await ctx.send("✅ 認証ボタンが設置されました。")


@bot.command(name='ping')
@is_owner()
async def ping(ctx):
    """botの応答確認（オーナーのみ）"""
    await ctx.send(f'🏓 Pong! {round(bot.latency * 1000)}ms')


# =============================================
# HTTPサーバー（24時間稼働用）
# =============================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Discord Bot is running!')
    
    def log_message(self, format, *args):
        return


def run_http_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f'HTTPサーバー起動: ポート {port}')
    server.serve_forever()


# HTTPサーバーをバックグラウンドで起動
http_thread = Thread(target=run_http_server, daemon=True)
http_thread.start()

# botを実行
if __name__ == "__main__":
    bot.run(TOKEN)
