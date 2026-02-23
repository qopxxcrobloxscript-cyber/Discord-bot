import discord
from discord import app_commands
import os
import re
import time
from collections import defaultdict
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.moderation = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

ROLE_NAME = "俺のあなる"
ALLOWED_USER_ID = int(os.environ.get('ALLOWED_USER_ID'))

welcome_channel_id = None
anti_channels = set()

suspicious_users = set()
recent_joins = []
message_history = defaultdict(list)

spam_score = defaultdict(float)
spam_messages = defaultdict(list)

audit_actions = defaultdict(list)

NSFW_DOMAINS = [
    "pornhub.com", "xvideos.com", "xhamster.com", "redtube.com",
    "youporn.com", "tube8.com", "spankbang.com", "xnxx.com",
    "tnaflix.com", "motherless.com", "hentaihaven.xxx", "nhentai.net",
    "rule34.xxx", "gelbooru.com", "danbooru.donmai.us", "e621.net",
    "onlyfans.com", "fapello.com", "erome.com", "bunkr.si",
]

RULES_TEXT_EN = """📜 **Server Rules**
**1. No Fighting**
- Please choose your words carefully and be mindful of others at all times.
- Even if you have a disagreement, do not become aggressive. Maintain an attitude of mutual respect as individuals.

**2. Prohibited Harassment and Offensive Speech**
- Verbal abuse, harassment, and discrimination are strictly prohibited for any reason.
- Please refrain from actions that disturb the peace of the server, such as trolling, spamming, or intentional disruption.
- Even if you intended it as "just a joke," it is a rule violation if it makes others uncomfortable. Be responsible for your own words.

**3. Posting NSFW Content**
- Content containing sexual or extreme expressions must only be posted in the designated channels.
- Posting such content in general channels is strictly prohibited.

**4. Unauthorized Advertising and Solicitation**
- Advertising or soliciting for external servers or services without permission is prohibited.
- Posting links to scams, phishing, or dangerous sites will result in immediate and severe action upon discovery.

**5. Security and Privacy Protection**
- Never post personal information (real names, addresses, contact info, etc.) belonging to yourself or others.
- Sending links containing IP loggers or viruses, or any suspicious files, is strictly forbidden. Please prioritize safety.

**6. Management Team's Judgment and Instructions**
- In the event of trouble or for administrative purposes, staff may issue instructions or warnings. Please follow them promptly. The management team has the final authority.

**7. Supplementary Notes and Penalties**
- The management will take action against any behavior deemed "dangerous" or "malicious," even if it is not explicitly stated in these rules.

👑 **Admin Rules**
**1. Prohibited Actions**
- Do not abuse server functions or permissions."""

RULES_TEXT_JP = """━━━━━━━━━━━━━━━━━━━━━━

**1. 喧嘩をしないでください**
- どんな時も、相手を思いやった言葉選びをお願いします。
- 意見が違う場合でも、攻撃的にならず、一人の人間として尊重し合う姿勢を忘れないでください。

**2. 迷惑行為・攻撃的な発言の禁止**
- 他者への暴言、嫌がらせ、差別は、理由を問わず一切禁止です。
- 荒らし、スパム、意図的な攪乱など、サーバーの平穏を乱す行為はやめてください。
- 「冗談のつもり」でも、相手が不快に感じればルール違反です。自分の発言には責任を持ちましょう。

**3. NSFWコンテンツの投稿**
- 性的・過激な表現を含むコンテンツは、必ず指定の専用チャンネルでのみ投稿してください。
- 一般チャンネルへの投稿は固く禁じます。

**4. 無許可の宣伝・勧誘について**
- 許可なく外部サーバーやサービスの宣伝、勧誘を行う行為は禁止です。
- 詐欺やフィッシング、危険なサイトへ誘導するリンクの投稿は、確認次第即座に厳重な対処を行います。

**5. セキュリティとプライバシーの保護**
- 自分や他人の個人情報（本名・住所・連絡先など）を書き込むのは絶対にやめてください。
- IPロガーやウイルスを含むリンク、不審なファイルの送信は厳禁です。安全な利用を心がけましょう。

**6. 運営チームの判断と指示**
- トラブル発生時や管理上の必要がある場合、運営スタッフから指示や警告を出すことがあります。その際は速やかに従ってください。最終的な決定権は運営チームにあります。

**7. 禁止事項の補足とペナルティ**
- 本ルールに明記されていないことでも、運営が「危険」「悪質」と判断した行為には対処を行います。

👑 **管理者のルール**
**1. 禁止事項**
- 機能を乱用しないでください"""

def is_random_id(name: str) -> bool:
    digit_count = sum(c.isdigit() for c in name)
    return len(name) >= 6 and digit_count >= 4

def is_new_account(user) -> bool:
    account_age = discord.utils.utcnow() - user.created_at
    return account_age.days < 1

def contains_nsfw_link(content: str) -> bool:
    urls = re.findall(r'https?://[^\s]+', content)
    for url in urls:
        for domain in NSFW_DOMAINS:
            if domain in url.lower():
                return True
    return False

def similar(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a, b = a.lower(), b.lower()
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    matches = sum(c in longer for c in shorter)
    return matches / len(longer)

async def apply_spam_score(member: discord.Member, add: float, channel: discord.TextChannel):
    spam_score[member.id] += add
    print(f"📊 スパムスコア {member.name}: {spam_score[member.id]:.1f}%")

    if spam_score[member.id] >= 100:
        spam_score[member.id] = 0
        spam_messages[member.id] = []
        try:
            await member.timeout(discord.utils.utcnow() + discord.timedelta(hours=24))
            await channel.send(f"🚫 {member.mention} はスパムのためタイムアウトされました。")
            print(f"🚫 24時間タイムアウト: {member.name}")
        except Exception as e:
            print(f"タイムアウト失敗: {e}")

async def nuke_timeout(guild: discord.Guild, user_id: int, reason: str):
    member = guild.get_member(user_id)
    if member is None:
        return
    if member.id == ALLOWED_USER_ID:
        return
    try:
        await member.timeout(discord.utils.utcnow() + discord.timedelta(hours=48))
        channel = guild.system_channel or next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
        if channel:
            await channel.send(f"🛡️ {member.mention} がNuke行為（{reason}）のため48時間タイムアウトされました。")
        print(f"🛡️ 48時間タイムアウト: {member.name} 理由: {reason}")
    except Exception as e:
        print(f"Nukeタイムアウト失敗: {e}")

async def check_nuke_action(guild: discord.Guild, user_id: int, action_type: str):
    now = time.time()
    key = f"{user_id}_{action_type}"
    audit_actions[key] = [t for t in audit_actions[key] if now - t <= 10]
    audit_actions[key].append(now)

    if len(audit_actions[key]) >= 3:
        audit_actions[key] = []
        await nuke_timeout(guild, user_id, action_type)

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

        if is_random_id(interaction.user.name) or is_new_account(interaction.user):
            suspicious_users.add(interaction.user.id)
            reason = []
            if is_random_id(interaction.user.name):
                reason.append("乱雑なID")
            if is_new_account(interaction.user):
                reason.append("新規アカウント")
            print(f"👀 監視対象に追加: {interaction.user.name} ({interaction.user.id}) 理由: {', '.join(reason)}")

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

@tree.command(name="anti", description="このチャンネルのNSFWリンクを自動削除します")
async def slash_anti(interaction: discord.Interaction):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message("❌ このコマンドは使用できません / You do not have permission to use this command.", ephemeral=True)
        return

    anti_channels.add(interaction.channel_id)
    await interaction.response.send_message("✅ このチャンネルのNSFWリンク自動削除を有効にしました！", ephemeral=True)

@tree.command(name="rule", description="サーバールールを表示します")
async def slash_rule(interaction: discord.Interaction):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message("❌ このコマンドは使用できません / You do not have permission to use this command.", ephemeral=True)
        return

    await interaction.response.send_message(RULES_TEXT_EN)
    await interaction.channel.send(RULES_TEXT_JP)

@tree.command(name="clean", description="チャンネルのメッセージを削除します")
@app_commands.describe(
    target="ユーザー名またはlinkを指定（空白で全削除）"
)
async def slash_clean(interaction: discord.Interaction, target: str = None):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message("❌ このコマンドは使用できません / You do not have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    channel = interaction.channel
    deleted = 0

    try:
        if target is None:
            # 全メッセージ削除
            deleted_msgs = await channel.purge(limit=None)
            deleted = len(deleted_msgs)
            await channel.send(f"🧹 {deleted}件のメッセージを削除しました。", delete_after=5)

        elif target.lower() == "link":
            # リンクのみ削除
            def has_link(msg):
                return bool(re.search(r'https?://[^\s]+', msg.content))
            deleted_msgs = await channel.purge(limit=None, check=has_link)
            deleted = len(deleted_msgs)
            await channel.send(f"🧹 {deleted}件のリンクメッセージを削除しました。", delete_after=5)

        else:
            # 指定ユーザーのメッセージ削除（ユーザー名で検索）
            def is_target_user(msg):
                return (
                    msg.author.name.lower() == target.lower() or
                    msg.author.display_name.lower() == target.lower()
                )
            deleted_msgs = await channel.purge(limit=None, check=is_target_user)
            deleted = len(deleted_msgs)
            await channel.send(f"🧹 {target} のメッセージを{deleted}件削除しました。", delete_after=5)

    except Exception as e:
        await interaction.followup.send(f"❌ エラー: {str(e)}", ephemeral=True)
        print(f"cleanコマンドエラー: {e}")
        return

    await interaction.followup.send(f"✅ 完了！{deleted}件削除しました。", ephemeral=True)

# =============================================
# Nuke対策イベント
# =============================================
@client.event
async def on_guild_channel_delete(channel):
    guild = channel.guild
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        if entry.user and entry.user.id != ALLOWED_USER_ID and not entry.user.bot:
            await check_nuke_action(guild, entry.user.id, "チャンネル大量削除")

@client.event
async def on_guild_role_delete(role):
    guild = role.guild
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
        if entry.user and entry.user.id != ALLOWED_USER_ID and not entry.user.bot:
            await check_nuke_action(guild, entry.user.id, "ロール大量削除")

@client.event
async def on_member_ban(guild, user):
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
        if entry.user and entry.user.id != ALLOWED_USER_ID and not entry.user.bot:
            await check_nuke_action(guild, entry.user.id, "大量Ban")

@client.event
async def on_member_remove(member):
    guild = member.guild
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
        if entry.target and entry.target.id == member.id:
            if entry.user and entry.user.id != ALLOWED_USER_ID and not entry.user.bot:
                await check_nuke_action(guild, entry.user.id, "大量キック")

    if welcome_channel_id is None:
        return
    channel = client.get_channel(welcome_channel_id)
    if channel is None:
        return
    member_count = guild.member_count
    embed = discord.Embed(
        title="👋 メンバー退出 / Member Left",
        description=f"{member.name} が退出しました。\n{member.name} has left the server.",
        color=discord.Color.red()
    )
    embed.add_field(name="👥 現在のサーバー人数 / Member Count", value=f"{member_count}人")
    embed.set_thumbnail(url=member.display_avatar.url)
    await channel.send(embed=embed)

@client.event
async def on_webhooks_update(channel):
    guild = channel.guild
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.webhook_create):
        if entry.user and entry.user.id != ALLOWED_USER_ID and not entry.user.bot:
            await check_nuke_action(guild, entry.user.id, "Webhook大量作成")

@client.event
async def on_guild_channel_create(channel):
    guild = channel.guild
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
        if entry.user and entry.user.id != ALLOWED_USER_ID and not entry.user.bot:
            await check_nuke_action(guild, entry.user.id, "チャンネル大量作成")

@client.event
async def on_member_join(member):
    global recent_joins

    if is_random_id(member.name) or is_new_account(member):
        suspicious_users.add(member.id)
        reason = []
        if is_random_id(member.name):
            reason.append("乱雑なID")
        if is_new_account(member):
            reason.append("新規アカウント")
        print(f"👀 監視対象に追加(参加時): {member.name} ({member.id}) 理由: {', '.join(reason)}")

    now = time.time()
    recent_joins.append((now, member))
    recent_joins = [(t, m) for t, m in recent_joins if now - t <= 10]

    if 3 <= len(recent_joins) <= 5:
        for join_time, join_member in recent_joins:
            try:
                await join_member.timeout(discord.utils.utcnow() + discord.timedelta(minutes=5))
                print(f"⏱️ 5分タイムアウト: {join_member.name}")
            except Exception as e:
                print(f"タイムアウト失敗: {e}")
        recent_joins = []

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
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id in anti_channels:
        if contains_nsfw_link(message.content):
            try:
                await message.delete()
                await message.channel.send(f"🚫 {message.author.mention} NSFWリンクを検出したため削除しました。", delete_after=5)
            except Exception as e:
                print(f"メッセージ削除失敗: {e}")
            return

    if message.author.id in suspicious_users:
        user_id = message.author.id
        now = time.time()
        message_history[user_id] = [t for t in message_history[user_id] if now - t <= 5]
        message_history[user_id].append(now)

        if len(message_history[user_id]) >= 8 and len(message.content) >= 20:
            try:
                await message.author.timeout(discord.utils.utcnow() + discord.timedelta(hours=12))
                message_history[user_id] = []
                print(f"🚫 12時間タイムアウト: {message.author.name}")
                await message.channel.send(f"🚫 {message.author.mention} がスパムのため12時間タイムアウトされました。", delete_after=10)
            except Exception as e:
                print(f"タイムアウト失敗: {e}")
            return

    member = message.guild.get_member(message.author.id)
    if member is None:
        return

    now = time.time()
    content = message.content
    user_id = message.author.id

    spam_messages[user_id] = [m for m in spam_messages[user_id] if now - m["time"] <= 30]
    spam_messages[user_id].append({"content": content, "time": now})

    recent = spam_messages[user_id]

    if len(recent) >= 2:
        last = recent[-2]["content"]
        curr = recent[-1]["content"]

        if similar(last, curr) >= 0.7:
            await apply_spam_score(member, 5, message.channel)

        recent_long = [m for m in recent if len(m["content"]) >= 20 and now - m["time"] <= 3]
        if len(recent_long) >= 2:
            await apply_spam_score(member, 10, message.channel)

        if len(content) >= 10 and len(set(content.replace(" ", ""))) <= 3:
            await apply_spam_score(member, 10, message.channel)

        if len(message.mentions) >= 3:
            await apply_spam_score(member, 15, message.channel)

        very_recent = [m for m in recent if now - m["time"] <= 5]
        if len(very_recent) >= 5:
            await apply_spam_score(member, 10, message.channel)

        if len(content) >= 10:
            upper_ratio = sum(c.isupper() for c in content if c.isalpha()) / max(sum(c.isalpha() for c in content), 1)
            if upper_ratio >= 0.5:
                await apply_spam_score(member, 5, message.channel)

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
