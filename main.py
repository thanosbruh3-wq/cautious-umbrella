import discord
from discord.ext import commands
import asyncio
from datetime import datetime

# ──────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────
BOT_TOKEN = "MTM4NTI4OTM0Njg3MzI5NDkzOQ.GM7w3o.h0Q_WMh8M8LsoVztH4s_jdBrx10jeKluD_tkPE"   # 🔑 Replace with your bot token
PREFIX    = "!"

# Rate-limit: max DMs per invocation
MAX_DM_LIMIT = 50

# Cooldown (seconds) between uses of !dm per admin
DM_COOLDOWN = 30

# ──────────────────────────────────────────────
#  INTENTS & BOT
# ──────────────────────────────────────────────
intents = discord.Intents.default()
intents.members  = True   # needed to iterate guild members
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# ──────────────────────────────────────────────
#  HELPERS
# ──────────────────────────────────────────────
def is_admin():
    """Custom check: caller must have Administrator permission."""
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
    embed  = discord.Embed(title=f"{status}", color=color, timestamp=datetime.utcnow())
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
        activity=discord.Activity(type=discord.ActivityType.watching, name="!dm | admin only")
    )


# ──────────────────────────────────────────────
#  !dm  COMMAND
# ──────────────────────────────────────────────
@bot.command(name="dm")
@is_admin()
@commands.cooldown(1, DM_COOLDOWN, commands.BucketType.user)
async def dm_command(ctx: commands.Context):
    """
    Interactive admin DM command.
    Usage: !dm  (then follow the prompts)
    """

    def check_author(m: discord.Message) -> bool:
        return m.author == ctx.author and m.channel == ctx.channel

    async def ask(prompt_embed: discord.Embed, *, timeout: float = 60.0) -> discord.Message | None:
        await ctx.send(embed=prompt_embed)
        try:
            return await bot.wait_for("message", check=check_author, timeout=timeout)
        except asyncio.TimeoutError:
            t = discord.Embed(title="⏰ Timed Out", description="No response in time. Command cancelled.", color=discord.Color.orange())
            await ctx.send(embed=t)
            return None

    # ── Step 1: target ────────────────────────────────────────────────────────
    e1 = discord.Embed(
        title="📬 Mass DM — Step 1 of 4: Target",
        description=(
            "Who should receive the DM?\n\n"
            "• Type `everyone` — all server members\n"
            "• Mention a **role** (e.g. `@Members`) — only that role\n"
            "• Type `cancel` to abort"
        ),
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow()
    )
    e1.set_footer(text=f"Admin: {ctx.author} • dm_bot")
    resp1 = await ask(e1)
    if resp1 is None:
        return

    raw_target = resp1.content.strip().lower()
    if raw_target == "cancel":
        await ctx.send(embed=discord.Embed(title="🛑 Cancelled", color=discord.Color.red()))
        return

    target_role: discord.Role | None = None
    target_everyone = False

    if raw_target == "everyone":
        target_everyone = True
    elif resp1.role_mentions:
        target_role = resp1.role_mentions[0]
    else:
        err = discord.Embed(
            title="❌ Invalid Target",
            description='Type `everyone` or mention a role like `@Members`.',
            color=discord.Color.red()
        )
        await ctx.send(embed=err)
        return

    # ── Step 2: title ─────────────────────────────────────────────────────────
    e2 = discord.Embed(
        title="📬 Mass DM — Step 2 of 4: Embed Title",
        description="What should the **title** of the DM embed be?\n*(max 256 characters)*",
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow()
    )
    resp2 = await ask(e2)
    if resp2 is None:
        return

    dm_title = resp2.content.strip()[:256]

    # ── Step 3: message body ──────────────────────────────────────────────────
    e3 = discord.Embed(
        title="📬 Mass DM — Step 3 of 4: Message Body",
        description="What's the **message** you want to send?\n*(max 4000 characters — supports Discord markdown)*",
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow()
    )
    resp3 = await ask(e3, timeout=120.0)
    if resp3 is None:
        return

    dm_body = resp3.content.strip()[:4000]
    if not dm_body:
        await ctx.send(embed=discord.Embed(title="❌ Empty message", color=discord.Color.red()))
        return

    # ── Step 4: confirmation ──────────────────────────────────────────────────
    target_label = "Everyone" if target_everyone else f"Role: @{target_role.name}"

    # Build a preview
    preview_dm = discord.Embed(
        title=dm_title,
        description=dm_body,
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )
    preview_dm.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    preview_dm.set_footer(text=f"Sent by {ctx.author.display_name} • {ctx.guild.name}")

    e4 = discord.Embed(
        title="📬 Mass DM — Step 4 of 4: Confirm",
        description=(
            f"**Target:** {target_label}\n"
            f"**Limit:** up to **{MAX_DM_LIMIT}** members\n\n"
            "Below is a **preview** of the DM.\n"
            "Reply `yes` to send, or `no` / `cancel` to abort."
        ),
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )
    await ctx.send(embed=e4)
    await ctx.send(embed=preview_dm)   # preview

    resp4 = await ask(discord.Embed(title="✅ Confirm? (yes / no)", color=discord.Color.gold()))
    if resp4 is None:
        return

    if resp4.content.strip().lower() not in ("yes", "y"):
        await ctx.send(embed=discord.Embed(title="🛑 Aborted", color=discord.Color.red()))
        return

    # ── Collect members ───────────────────────────────────────────────────────
    if target_everyone:
        members = [m for m in ctx.guild.members if not m.bot]
    else:
        members = [m for m in target_role.members if not m.bot]

    members = members[:MAX_DM_LIMIT]
    total   = len(members)

    if total == 0:
        await ctx.send(embed=discord.Embed(
            title="⚠️ No Members Found",
            description="There are no eligible members to DM.",
            color=discord.Color.orange()
        ))
        return

    # ── Confirm member count ──────────────────────────────────────────────────
    count_embed = discord.Embed(
        title="📋 Member Count",
        description=f"About to DM **{total}** member(s).\nReply `go` to start, or anything else to cancel.",
        color=discord.Color.blurple()
    )
    resp_go = await ask(count_embed)
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
            skipped += 1   # DMs disabled
        except discord.HTTPException:
            failed += 1

        # Update progress every 10 members
        if (i + 1) % 10 == 0 or (i + 1) == total:
            await prog_msg.edit(embed=make_progress_embed(sent, failed, skipped, total))

        await asyncio.sleep(0.1)   # fast (~10 DMs/sec)

    # ── Final report ──────────────────────────────────────────────────────────
    await prog_msg.edit(embed=make_progress_embed(sent, failed, skipped, total, done=True))

    log_embed = discord.Embed(
        title="📊 DM Report",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
    log_embed.add_field(name="Admin",   value=ctx.author.mention, inline=True)
    log_embed.add_field(name="Target",  value=target_label,       inline=True)
    log_embed.add_field(name="✉️ Sent",    value=str(sent),    inline=True)
    log_embed.add_field(name="⏭️ Skipped", value=str(skipped), inline=True)
    log_embed.add_field(name="❌ Failed",  value=str(failed),  inline=True)
    log_embed.set_footer(text="dm_bot • mass DM complete")
    await ctx.send(embed=log_embed)


# ──────────────────────────────────────────────
#  !help  (custom)
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
        name="`!dm`",
        value=(
            "Start an interactive mass-DM session.\n"
            "You'll be asked:\n"
            "1. **Target** — `everyone` or a `@role`\n"
            "2. **Embed title**\n"
            "3. **Message body**\n"
            "4. **Confirmation + member count check**\n\n"
            f"Max {MAX_DM_LIMIT} members per use • {DM_COOLDOWN}s cooldown per admin"
        ),
        inline=False
    )
    embed.set_footer(text="Admin-only • dm_bot")
    await ctx.send(embed=embed)


# ──────────────────────────────────────────────
#  ERROR HANDLING
# ──────────────────────────────────────────────
@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandOnCooldown):
        embed = discord.Embed(
            title="⏳ Cooldown",
            description=f"You can use `!dm` again in **{error.retry_after:.0f}s**.",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed, delete_after=10)
    elif isinstance(error, commands.CheckFailure):
        pass   # already handled inside is_admin()
    elif isinstance(error, commands.CommandNotFound):
        pass   # ignore unknown commands silently
    else:
        embed = discord.Embed(
            title="💥 Unexpected Error",
            description=f"```{error}```",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        raise error


# ──────────────────────────────────────────────
#  RUN
# ──────────────────────────────────────────────
bot.run(BOT_TOKEN)
