import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
from flask import Flask
import threading
import logging
import datetime

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
POST_CHANNEL_ID = 1396969114039226599  # Kanal für Rangliste
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
# Variable zur Speicherung der letzten Ranglisten-Nachricht
# =========================
ranglisten_message_id = None

# =========================
# 🔄 Helper: Rangliste-Embed erstellen
# =========================

def build_ranking_embed(guild):
    embed = discord.Embed(
        title="📈 Rangliste der Mitglieder",
        description="Aktuelle Verteilung der Ränge im LSPD",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.utcnow()
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
    embed.set_thumbnail(url=LOGO_URL)
    embed.set_footer(text="Straze Police Department")
    return embed

# =========================
# 🔄 Task: Rangliste regelmäßig aktualisieren
# =========================

@tasks.loop(minutes=10)
async def update_rangliste():
    global ranglisten_message_id
    guild = bot.get_guild(SERVER_ID)
    if not guild:
        logging.warning(f"Server mit ID {SERVER_ID} nicht gefunden.")
        return

    channel = guild.get_channel(POST_CHANNEL_ID)
    if not channel:
        logging.warning(f"Kanal mit ID {POST_CHANNEL_ID} nicht gefunden.")
        return

    embed = build_ranking_embed(guild)

    # Alte Nachricht löschen, falls vorhanden
    if ranglisten_message_id:
        try:
            alte_msg = await channel.fetch_message(ranglisten_message_id)
            await alte_msg.delete()
            logging.info("Alte Ranglisten-Nachricht gelöscht.")
        except Exception as e:
            logging.warning(f"Fehler beim Löschen der alten Ranglisten-Nachricht: {e}")

    # Neue Nachricht senden und ID speichern
    neue_msg = await channel.send(embed=embed)
    ranglisten_message_id = neue_msg.id
    logging.info(f"Neue Ranglisten-Nachricht gesendet mit ID: {ranglisten_message_id}")

# =========================
# 📡 EVENTS
# =========================

@bot.event
async def on_ready():
    if any(guild.id == SERVER_ID for guild in bot.guilds):
        logging.info(f"✅ Verbunden mit Server ID {SERVER_ID}.")
    else:
        logging.warning(f"❌ Server ID {SERVER_ID} nicht gefunden!")

    await tree.sync()
    logging.info(f"✅ Bot ist online als {bot.user}")
    update_rangliste.start()

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
        embed = discord.Embed(title=f"Profil von {interaction.user.name}", color=discord.Color.blue())
        embed.add_field(name="Dienstnummer", value=daten.get("dienstnummer", "Nicht gesetzt"))
        embed.add_field(name="Name", value=daten.get("name", "Nicht gesetzt"))
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Du bist nicht registriert.", ephemeral=True)

# =========================
# Flask Webserver (für Keep-Alive)
# =========================

app = Flask("")

@app.route("/")
def home():
    return "Bot läuft..."

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    thread = threading.Thread(target=run)
    thread.start()

# =========================
# Bot starten
# =========================

keep_alive()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not TOKEN:
    logging.error("❌ Kein Token in Umgebungsvariablen gefunden! Bitte setze DISCORD_BOT_TOKEN.")
else:
    bot.run(TOKEN)
