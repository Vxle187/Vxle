# ----------------------------------
# LSPD Discord Bot
# ----------------------------------

import discord
from discord import app_commands
from discord.ext import commands
import os
from flask import Flask
import threading

# =========================
# 🤖 Discord Bot Setup
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Kanal-IDs (anpassen!)
WILLKOMMEN_KANAL_ID = 123456789012345678
LEAVE_KANAL_ID = 1396969114442006538

# Rollen und Ränge
registrierte_user = {}

ROLLEN_IDS = [
    1396969113955602569,
    1396969114022711376
]

RANGLISTE = [
    1396969114022711376,
    1396969114022711377,
    1396969114022711378,
    1396969114022711383,
    1396969114031095929,
    1396969114031095930,
    1396969114031095931,
    1396969114031095932,
    1396969114031095933,
    1396969114031095935,
    1396969114031095936,
    1396969114031095937,
]

BEFUGTE_RANG_IDS = [
    1396969114005930128,
    1396969114031095936,
    1396969114031095937
]

# =========================
# 📡 EVENTS
# =========================
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot ist online als {bot.user}")

@bot.event
async def on_member_join(member):
    channel = member.guild.get_channel(WILLKOMMEN_KANAL_ID)
    if not channel:
        return
    embed = discord.Embed(
        title="👋 Welcome here!",
        description=(
            f"Hey {member.mention}! Please follow all our rules and be respectful.\nHave fun!"
        ),
        color=discord.Color.gold()
    )
    embed.set_author(name="Police Department | Alpha City", icon_url=member.guild.icon.url if member.guild.icon else None)
    embed.set_footer(text="Welcome to our Discord Server!")
    await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    channel = member.guild.get_channel(LEAVE_KANAL_ID)
    if not channel:
        return
    embed = discord.Embed(
        title="👋 Goodbye!",
        description=f"{member.name} has left the server. See you soon!",
        color=discord.Color.dark_grey()
    )
    embed.set_author(name="Police Department | Alpha City", icon_url=member.guild.icon.url if member.guild.icon else None)
    embed.set_footer(text="User left the Discord Server.")
    await channel.send(embed=embed)

# =========================
# 🛠️ Slash-Befehle
# =========================
@tree.command(name="einstellen", description="Stellt eine Person ein, gibt Rollen und setzt den Namen.")
@app_commands.describe(user="Wähle den User aus", dienstnummer="Trage die Dienstnummer ein", name="Trage den Namen ein")
async def einstellen(interaction: discord.Interaction, user: discord.Member, dienstnummer: str, name: str):
    guild = interaction.guild
    registrierte_user[user.id] = {"dienstnummer": dienstnummer, "name": name}

    hinzugefügte_rollen = []
    for rollen_id in ROLLEN_IDS:
        rolle = guild.get_role(rollen_id)
        if rolle:
            await user.add_roles(rolle)
            hinzugefügte_rollen.append(rolle.name)
        else:
            await interaction.response.send_message(f"⚠️ Rolle mit ID `{rollen_id}` nicht gefunden!", ephemeral=True)
            return

    nickname = f"[{dienstnummer.zfill(2)}] {name}"
    try:
        await user.edit(nick=nickname)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Ich kann den Nickname nicht ändern!", ephemeral=True)
        return

    await interaction.response.send_message(
        f"✅ {user.mention} wurde eingestellt!\n"
        f"📄 Dienstnummer: `{dienstnummer.zfill(2)}`\n"
        f"📛 Neuer Name: `{nickname}`\n"
        f"🎓 Rollen: {', '.join(hinzugefügte_rollen)}"
    )

@tree.command(name="profil", description="Zeigt dein Profil an.")
async def profil(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in registrierte_user:
        daten = registrierte_user[user_id]
        await interaction.response.send_message(
            f"🧾 Dein Profil:\n"
            f"📄 Dienstnummer: `{daten['dienstnummer'].zfill(2)}`\n"
            f"📛 Name: `{daten['name']}`"
        )
    else:
        await interaction.response.send_message("⚠️ Du bist noch nicht registriert. Nutze `/einstellen`.")

@tree.command(name="entlassen", description="Entlässt eine Person vom Server.")
@app_commands.describe(user="User, der gekickt werden soll", grund="Grund (optional)")
async def entlassen(interaction: discord.Interaction, user: discord.Member, grund: str = "Kein Grund angegeben"):
    if user.id == interaction.user.id:
        await interaction.response.send_message("❌ Du kannst dich nicht selbst entlassen!", ephemeral=True)
        return
    try:
        await user.kick(reason=grund)
        registrierte_user.pop(user.id, None)
        await interaction.response.send_message(f"👢 {user.mention} wurde entlassen. Grund: `{grund}`")
    except discord.Forbidden:
        await interaction.response.send_message("❌ Keine Berechtigung zum Kicken!", ephemeral=True)

@tree.command(name="uprank", description="Befördert einen User.")
@app_commands.describe(user="User, der befördert werden soll")
async def uprank(interaction: discord.Interaction, user: discord.Member):
    guild = interaction.guild
    invoker = interaction.user

    if not any(discord.utils.get(invoker.roles, id=r) for r in BEFUGTE_RANG_IDS):
        await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
        return

    user_ränge = [r for r in [guild.get_role(rid) for rid in RANGLISTE] if r in user.roles]
    if not user_ränge:
        await interaction.response.send_message(f"{user.mention} hat keine Rangrolle.", ephemeral=True)
        return
    user_index = max(RANGLISTE.index(r.id) for r in user_ränge)

    if user_index >= len(RANGLISTE) - 1:
        await interaction.response.send_message("✅ Nutzer hat bereits höchsten Rang.", ephemeral=True)
        return

    neue_rolle = guild.get_role(RANGLISTE[user_index + 1])
    aktuelle_rolle = guild.get_role(RANGLISTE[user_index])
    try:
        await user.remove_roles(aktuelle_rolle)
        await user.add_roles(neue_rolle)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Rollenwechsel fehlgeschlagen.", ephemeral=True)
        return

    await interaction.response.send_message(f"🎉 {user.mention} wurde befördert: `{aktuelle_rolle.name}` ➜ `{neue_rolle.name}`")

@tree.command(name="derank", description="Degradiert einen User.")
@app_commands.describe(user="User, der degradiert werden soll")
async def derank(interaction: discord.Interaction, user: discord.Member):
    guild = interaction.guild
    invoker = interaction.user

    if not any(discord.utils.get(invoker.roles, id=r) for r in BEFUGTE_RANG_IDS):
        await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
        return

    user_ränge = [r for r in [guild.get_role(rid) for rid in RANGLISTE] if r in user.roles]
    if not user_ränge:
        await interaction.response.send_message(f"{user.mention} hat keine Rangrolle.", ephemeral=True)
        return
    user_index = max(RANGLISTE.index(r.id) for r in user_ränge)

    if user_index == 0:
        await interaction.response.send_message("✅ Nutzer hat bereits den niedrigsten Rang.", ephemeral=True)
        return

    neue_rolle = guild.get_role(RANGLISTE[user_index - 1])
    aktuelle_rolle = guild.get_role(RANGLISTE[user_index])
    try:
        await user.remove_roles(aktuelle_rolle)
        await user.add_roles(neue_rolle)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Rollenwechsel fehlgeschlagen.", ephemeral=True)
        return

    await interaction.response.send_message(f"⬇️ {user.mention} wurde degradiert: `{aktuelle_rolle.name}` ➜ `{neue_rolle.name}`")

# =========================
# 🌐 Webserver für UptimeRobot
# =========================
from flask import Flask
import threading
import os  # <--- fehlt in deinem Code
import discord  # falls du es noch nicht importiert hast

app = Flask('')

@app.route('/')
def home():
    return "✅ Bot is running!"

def run():
    app.run(host='0.0.0.0', port=5000)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()

# Webserver starten
keep_alive()

# Bot starten
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
