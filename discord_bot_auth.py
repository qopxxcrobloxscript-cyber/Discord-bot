import discord
from discord.ext import commands
from discord.ui import Button, View
import os
from dotenv import load_dotenv

# 環境変数を読み込む
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID', '0'))
ROLE_ID = int(os.getenv('ROLE_ID', '0'))

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
async def on_ready():
    """botが起動したときの処理"""
    print(f'{bot.user} がログインしました')
    print(f'botのID: {bot.user.id}')


@bot.command(name='auth_setup')
@commands.has_permissions(administrator=True)
async def auth_setup(ctx):
    """認証ボタンを表示するコマンド（管理者のみ）"""
    embed = discord.Embed(
        title="🔐 認証",
        description="下のボタンをクリックして認証を完了してください。",
        color=discord.Color.blue()
    )
    
    view = AuthenticationView()
    await ctx.send(embed=embed, view=view)
    await ctx.send("✅ 認証ボタンが設置されました。")


@bot.command(name='ping')
async def ping(ctx):
    """botの応答確認"""
    await ctx.send(f'🏓 Pong! {round(bot.latency * 1000)}ms')


# botを実行
if __name__ == "__main__":
    bot.run(TOKEN)
