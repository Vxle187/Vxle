# ----------------------------------
# LSPD Discord Bot (überarbeitet)
# ----------------------------------

import discord
from discord import app_commands
from discord.ext import commands
import os
from flask import Flask
import threading
import logging

# Logging aktivieren (für bessere Fehlersuche)
logging.basicConfig(level=logging.INFO)

# =========================
# 🤖 Discord Bot Setup
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# =========================
# Server und Kanal-IDs
# =========================
SERVER_ID = 1396969113955602562  # Deine Server-ID
WILLKOMMEN_KANAL_ID = 1396969114039226598
LEAVE_KANAL_ID = 1396969114442006538
POST_CHANNEL_ID = 1396969114039226599
LOGO_URL = "https://cdn.discordapp.com/attachments/1396969116195360941/1401653566283710667/IMG_2859.png"

# =========================
# Rollen und Ränge
# =========================
registrierte_user = {}

ROLLEN_IDS = [
    1396969113955602569,
    1396969114022711376,
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
    1396969114031095937,
    1396969114039226595
]

ERLAUBTE_ROLLEN_ID = 1401284034109243557  # Für !loeschen

# =========================
# 📡 EVENTS
# =========================

@bot.event
async def on_ready():
    # Prüfen, ob der Bot im richtigen Server ist
    if any(guild.id == SERVER_ID for guild in bot.guilds):
        logging.info(f"✅ Verbunden mit Server ID {SERVER_ID}.")
    else:
        logging.warning(f"❌ Server ID {SERVER_ID} nicht gefunden!")
    
    # Slash-Befehle synchronisieren
    await tree.sync()
    logging.info(f"✅ Bot ist online als {bot.user}")
    logging.info("🔍 Geladene Textbefehle: %s", [cmd.name for cmd in bot.commands])
    logging.info("🔧 Slash-Befehle synchronisiert.")

@bot.event
async def on_member_update(before, after):
    before_roles = set(role.id for role in before.roles)
    after_roles = set(role.id for role in after.roles)

    if before_roles == after_roles:
        return  # keine Rollenänderung

    if not any((role_id in before_roles) != (role_id in after_roles) for role_id in RANGLISTE):
        return

    channel = after.guild.get_channel(POST_CHANNEL_ID)
    if channel:
        embed = build_ranking_embed(after.guild)
        await channel.send(embed=embed)

@bot.event
async def on_member_join(member):
    if member.guild.id != SERVER_ID:
        return
    
    channel = member.guild.get_channel(WILLKOMMEN_KANAL_ID)
    if channel:
        embed = discord.Embed(
            title=f"<@{member.id}>, willkommen auf **Straze Police Department** 👮",
            description=(
                "📚 **Schön, dass du da bist!**\n"
                "❗ **Bitte halte dich im Dienst an die Funkcodes**\n\n"
                "🛡️ **Falls du Fragen hast**, **wende dich an die Leitung!**"
            ),
            color=discord.Color.dark_blue()
        )
        embed.set_author(
            name="Police Department | BloodLife",
            icon_url=member.guild.icon.url if member.guild.icon else None
        )
        embed.set_image(url=LOGO_URL)
        embed.set_footer(
            text="Willkommen auf dem BloodLife Police Department Discord!"
        )
        await channel.send(embed=embed)

    auto_role_id = 1396969113955602563
    role = member.guild.get_role(auto_role_id)
    if role:
        try:
            await member.add_roles(role)
            logging.info(f"✅ Rolle '{role.name}' wurde an {member} vergeben.")
        except discord.Forbidden:
            logging.warning(f"❌ Keine Berechtigung, um {member} die Rolle zu geben.")
        except discord.HTTPException as e:
            logging.warning(f"❌ Fehler beim Vergeben der Rolle an {member}: {e}")
    else:
        logging.warning(f"⚠️ Rolle mit ID {auto_role_id} nicht gefunden.")

@bot.event
async def on_member_remove(member):
    if member.guild.id != SERVER_ID:
        return
    
    channel = member.guild.get_channel(LEAVE_KANAL_ID)
    if not channel:
        return

    embed = discord.Embed(
        title="👋 Auf Wiedersehen!",
        description=f"{member.mention} hat den Server verlassen, wir hoffen, wir sehen uns bald wieder!",
        color=discord.Color.dark_grey()
    )
    embed.set_image(url=LOGO_URL)
    embed.set_author(
        name="Police Department | Blood Life",
        icon_url=member.guild.icon.url if member.guild.icon else None
    )
    embed.set_footer(text="Auf Wiedersehen.")
    await channel.send(embed=embed)

# =========================
# 🧹 Text-Befehle: !loeschen und !löschen
# =========================

@bot.command(name='loeschen')
async def loeschen(ctx, anzahl: int):
    await nachrichten_loeschen(ctx, anzahl)

@bot.command(name='löschen')
async def löschen_umlaut(ctx, anzahl: int):
    await nachrichten_loeschen(ctx, anzahl)

async def nachrichten_loeschen(ctx, anzahl: int):
    autor = ctx.author
    erlaubnis = discord.utils.get(autor.roles, id=ERLAUBTE_ROLLEN_ID)

    if not erlaubnis:
        await ctx.send("❌ Du hast keine Berechtigung für diesen Befehl.")
        return

    if anzahl < 1 or anzahl > 100:
        await ctx.send("⚠️ Du kannst nur zwischen 1 und 100 Nachrichten löschen.")
        return

    await ctx.channel.purge(limit=anzahl + 1)
    await ctx.send(f"🧹 {anzahl} Nachrichten gelöscht.", delete_after=5)

# =========================
# ✅ Slash-Befehle
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
    alte_rolle = guild.get_role(RANGLISTE[user_index])

    try:
        await user.remove_roles(alte_rolle)
        await user.add_roles(neue_rolle)
        await interaction.response.send_message(f"🔝 {user.mention} wurde befördert: {alte_rolle.name} → {neue_rolle.name}")
    except discord.Forbidden:
        await interaction.response.send_message("❌ Keine Berechtigung zum Ändern der Rollen.", ephemeral=True)

@tree.command(name="downrank", description="Degradiert einen User.")
@app_commands.describe(user="User, der degradiert werden soll")
async def downrank(interaction: discord.Interaction, user: discord.Member):
    guild = interaction.guild
    invoker = interaction.user

    if not any(discord.utils.get(invoker.roles, id=r) for r in BEFUGTE_RANG_IDS):
        await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
        return

    user_ränge = [r for r in [guild.get_role(rid) for rid in RANGLISTE] if r in user.roles]
    if not user_ränge:
        await interaction.response.send_message(f"{user.mention} hat keine Rangrolle.", ephemeral=True)
        return
    user_index = min(RANGLISTE.index(r.id) for r in user_ränge)

    if user_index == 0:
        await interaction.response.send_message("✅ Nutzer hat bereits niedrigsten Rang.", ephemeral=True)
        return

    neue_rolle = guild.get_role(RANGLISTE[user_index - 1])
    alte_rolle = guild.get_role(RANGLISTE[user_index])

    try:
        await user.remove_roles(alte_rolle)
        await user.add_roles(neue_rolle)
        await interaction.response.send_message(f"🔻 {user.mention} wurde degradiert: {alte_rolle.name} → {neue_rolle.name}")
    except discord.Forbidden:
        await interaction.response.send_message("❌ Keine Berechtigung zum Ändern der Rollen.", ephemeral=True)

# =========================
# 🔄 Helper: Rangliste-Embed aktualisieren
# =========================

def build_ranking_embed(guild):
    embed = discord.Embed(
        title="📈 Rangliste der Mitglieder",
        description="Aktuelle Verteilung der Ränge im LSPD",
        color=discord.Color.blue()
    )
    for role_id in RANGLISTE:
        role = guild.get_role(role_id)
        if role:
            count = len(role.members)
            embed.add_field(
                name=f"• {role.name}",
                value=f"Mitglieder: {count}\n",
                inline=False
            )

    embed.set_thumbnail(url="https://static.wikia.nocookie.net/arab-fivem/images/8/8f/Los_Santos_Police_Department.png")
    embed.set_footer(text="Straze Police Department")
    return embed

# =========================
# 🔄 Flask Webserver (für Keep-Alive)
# =========================

app = Flask("")

@app.route("/")
def home():
    return "Bot läuft..."

def run():
    # Starte Flask-Webserver
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    # Flask-Webserver in separatem Thread parallel starten
    thread = threading.Thread(target=run)
    thread.start()

# =========================
# 🚀 Start Bot
# =========================

if __name__ == "__main__":
    keep_alive()  # Starte Webserver parallel

    TOKEN = os.getenv("DISCORD_BOT_TOKEN")  # Bot Token in Umgebungsvariablen setzen

    if not TOKEN:
        logging.error("❌ Kein Token in Umgebungsvariablen gefunden! Bitte setze DISCORD_BOT_TOKEN.")
    else:
        bot.run(TOKEN)
