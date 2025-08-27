# ----------------------------------
# LSPD Discord Bot (überarbeitet + komplettes Ticketsystem)
# ----------------------------------

import discord
from discord import app_commands
from discord.ext import commands
import os
from flask import Flask
import threading
import logging
from datetime import datetime
from discord.ui import View

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
# Server und Kanal-IDs (deine Werte)
# =========================
SERVER_ID = 1396969113955602562  # Deine Server-ID
WILLKOMMEN_KANAL_ID = 1396969114039226598
LEAVE_KANAL_ID = 1396969114442006538
POST_CHANNEL_ID = 1396969114039226599  # Post-Kanal (Ranking)
LOGO_URL = "https://cdn.discordapp.com/attachments/1396969116195360941/1401653566283710667/IMG_2859.png"

# Ticket Ziel-Kanäle (wo die fertigen Tickets/Transcripts landen)
BEWERBUNGEN_CHANNEL_ID = 1410111339359113318
BESCHWERDEN_CHANNEL_ID = 1410111382237483088
LEITUNG_CHANNEL_ID = 1410111463783268382

# Kanal in dem das Ticket-Panel automatisch gepostet werden soll
TICKET_PANEL_CHANNEL_ID = 1396969114442006539

# =========================
# Rollen und Ränge (Police Officer Rollen)
# =========================
registrierte_user = {}

POLICE_ROLLEN_IDS = [
    1396969114022711376,  # Rekrut
    1396969114022711377,  # Officer I
    1396969114022711378,  # Officer II
    1396969114022711383,  # Sergeant
    1396969114031095929,  # Lieutenant
    1396969114031095930,  # First Lieutenant
    1396969114031095931,  # Captain
    1396969114031095932,  # Major
    1396969114031095933,  # Commander
    1396969114031095935,  # Deputy Chief
    1396969114031095936,  # Assistant Chief
    1396969114031095937,  # Chief of Police
]

# Neue Reihenfolge (höchster Rang zuerst)
POLICE_ROLLEN_IDS = list(reversed(POLICE_ROLLEN_IDS))

ROLLEN_IDS = [
    1396969113955602569,
    1396969114022711376,
]

RANGLISTE = POLICE_ROLLEN_IDS  # für andere Funktionen, falls benötigt

BEFUGTE_RANG_IDS = [
    1396969114005930128,
    1396969114031095936,
    1396969114031095937,
    1396969114039226595
]

ERLAUBTE_ROLLEN_ID = 1401284034109243557  # Für !loeschen

# =========================
# 🎟️ Ticket-System: Fragen & Speicher
# =========================
ticket_categories = {
    "bewerbung": [
        "Wie lautet dein vollständiger Name?",
        "Wie alt bist du?",
        "Warum möchtest du Teil unseres Teams werden?",
        "Welche Erfahrungen bringst du mit?"
    ],
    "beschwerde": [
        "Wen betrifft die Beschwerde?",
        "Bitte beschreibe die Situation so detailliert wie möglich.",
        "Hast du Beweise (Screenshots, Chatlogs etc.)?"
    ],
    "leitung": [
        "Welches Anliegen möchtest du der Leitung mitteilen?",
        "Wie dringend ist dein Anliegen (1-10)?",
        "Möchtest du anonym bleiben? (Ja/Nein)"
    ]
}

# Mapping Ticket-Art -> Ziel-Channel-ID für Transcripts
TICKET_TARGET_CHANNEL = {
    "bewerbung": BEWERBUNGEN_CHANNEL_ID,
    "beschwerde": BESCHWERDEN_CHANNEL_ID,
    "leitung": LEITUNG_CHANNEL_ID
}

# Laufende Tickets:
# key = owner_user_id -> value = {
#   'channel_id': int,
#   'art': 'bewerbung'|'beschwerde'|'leitung',
#   'fragen': [...remaining...],
#   'antworten': [...],
#   'completed': bool
# }
user_tickets = {}

# =========================
# Ticket-Panel View (Buttons)
# =========================
class TicketPanel(View):
    def __init__(self):
        super().__init__(timeout=None)  # persistente View

    async def _create_ticket_channel(self, interaction: discord.Interaction, art: str):
        """Hilfsfunktion: Ticket-Channel erstellen und Ticket-Daten anlegen."""
        guild = interaction.guild
        owner = interaction.user

        # Prüfen, ob User schon ein offenes Ticket hat
        if owner.id in user_tickets:
            await interaction.response.send_message("⚠️ Du hast bereits ein offenes Ticket. Bitte warte, bis dieses abgeschlossen ist.", ephemeral=True)
            return None

        # Berechtigungen / Overwrites
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            owner: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        # Leitung / Admin Rollen Leserechte geben
        for role_id in BEFUGTE_RANG_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        # Channel-Name sauber generieren
        safe_name = str(owner.display_name).lower().replace(" ", "-")[:80]
        channel_name = f"ticket-{safe_name}"

        ticket_channel = await guild.create_text_channel(channel_name, overwrites=overwrites)

        # Ticket-Daten anlegen (nicht löschen, erst beim /ticketclose)
        user_tickets[owner.id] = {
            "channel_id": ticket_channel.id,
            "art": art,
            "fragen": list(ticket_categories[art]),
            "antworten": [],
            "completed": False,
            "owner_id": owner.id,
            "created_at": datetime.utcnow().isoformat()
        }

        return ticket_channel

    @discord.ui.button(label="📄 Bewerbung", style=discord.ButtonStyle.primary, custom_id="ticket_bewerbung")
    async def bewerbung_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_channel = await self._create_ticket_channel(interaction, "bewerbung")
        if not ticket_channel:
            return
        await interaction.response.send_message(f"✅ Dein Bewerbungs-Ticket wurde erstellt: {ticket_channel.mention}", ephemeral=True)
        frage = user_tickets[interaction.user.id]["fragen"].pop(0)
        await ticket_channel.send(f"🎟️ Hallo {interaction.user.mention}, willkommen in deinem **Bewerbungs-Ticket**.\nBitte beantworte die folgenden Fragen:")
        await ticket_channel.send(f"❓ {frage}")

    @discord.ui.button(label="⚠️ Beschwerde", style=discord.ButtonStyle.danger, custom_id="ticket_beschwerde")
    async def beschwerde_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_channel = await self._create_ticket_channel(interaction, "beschwerde")
        if not ticket_channel:
            return
        await interaction.response.send_message(f"✅ Dein Beschwerde-Ticket wurde erstellt: {ticket_channel.mention}", ephemeral=True)
        frage = user_tickets[interaction.user.id]["fragen"].pop(0)
        await ticket_channel.send(f"🎟️ Hallo {interaction.user.mention}, willkommen in deinem **Beschwerde-Ticket**.\nBitte beantworte die folgenden Fragen:")
        await ticket_channel.send(f"❓ {frage}")

    @discord.ui.button(label="📢 Leitungsanliegen", style=discord.ButtonStyle.secondary, custom_id="ticket_leitung")
    async def leitung_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_channel = await self._create_ticket_channel(interaction, "leitung")
        if not ticket_channel:
            return
        await interaction.response.send_message(f"✅ Dein Leitungs-Ticket wurde erstellt: {ticket_channel.mention}", ephemeral=True)
        frage = user_tickets[interaction.user.id]["fragen"].pop(0)
        await ticket_channel.send(f"🎟️ Hallo {interaction.user.mention}, willkommen in deinem **Leitungs-Ticket**.\nBitte beantworte die folgenden Fragen:")
        await ticket_channel.send(f"❓ {frage}")

# =========================
# 📡 EVENTS (on_ready, on_member_update, join/leave, on_message erweitert)
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

    # Persistent View registrieren (damit Buttons nach Neustart funktionieren)
    bot.add_view(TicketPanel())

    # Ticket Panel automatisch posten in dem gewünschten Kanal (einmalig, vermeidet Doppelposts)
    guild = bot.get_guild(SERVER_ID)
    if guild:
        panel_channel = guild.get_channel(TICKET_PANEL_CHANNEL_ID)
        if panel_channel:
            should_post = True
            async for msg in panel_channel.history(limit=20):
                if msg.author == bot.user and msg.embeds:
                    emb = msg.embeds[0]
                    if emb.title == "🎫 Ticket-System":
                        should_post = False
                        break
            if should_post:
                embed = discord.Embed(
                    title="🎫 Ticket-System",
                    description="Klicke unten auf die passende Schaltfläche, um ein Ticket zu öffnen:\n\n"
                                "📄 Bewerbung → Bewerbungen\n"
                                "⚠️ Beschwerde → Beschwerden\n"
                                "📢 Leitungsanliegen → Direkt zur Leitung",
                    color=discord.Color.blue()
                )
                view = TicketPanel()
                await panel_channel.send(embed=embed, view=view)
                logging.info("📌 Ticket-Panel im Kanal gepostet.")

@bot.event
async def on_member_update(before, after):
    before_roles = set(role.id for role in before.roles)
    after_roles = set(role.id for role in after.roles)

    if before_roles == after_roles:
        return  # keine Rollenänderung

    # Prüfen, ob sich Rollen aus der Police-Liste geändert haben
    role_change = any(
        (role_id in before_roles) != (role_id in after_roles)
        for role_id in POLICE_ROLLEN_IDS
    )
    if not role_change:
        return

    channel = after.guild.get_channel(POST_CHANNEL_ID)
    if channel:
        # Alte Ranglisten-Nachricht löschen
        async for msg in channel.history(limit=50):
            if msg.author == bot.user and msg.embeds:
                embed = msg.embeds[0]
                if embed.title == "📈 Unsere Police Officer":
                    try:
                        await msg.delete()
                    except discord.Forbidden:
                        logging.warning("Keine Berechtigung, alte Nachricht zu löschen.")
                    break

        # Neue Rangliste senden
        embed = build_police_ranking_embed(after.guild)
        await channel.send(embed=embed)

@bot.event
async def on_member_join(member):
    if member.guild.id != SERVER_ID:
        return
    
    channel = member.guild.get_channel(WILLKOMMEN_KANAL_ID)
    if channel:
        embed = discord.Embed(
            title=f"<@{member.id}>, willkommen auf **Blood Life Police Department** 👮",
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

@bot.event
async def on_message(message):
    EINSTELLUNGSKANAL_ID = 1396969115813544127  # Der Kanal, in dem /einstellen verwendet wird

    # Ignoriere Bots
    if message.author.bot:
        return

    # -------------------------
    # Ticket-Antworten verarbeiten
    # -------------------------
    # Wenn der Autor ein Ticket besitzt und im zugehörigen Ticket-Channel schreibt,
    # werden die Antworten gespeichert und bei Abschluss in den Ziel-Channel gesendet.
    owner_id = message.author.id
    if owner_id in user_tickets:
        ticket = user_tickets[owner_id]
        if message.channel.id == ticket["channel_id"]:
            # Nur die Antworten des Ticket-Owners zählen als Antworten (Staff kann normal chatten)
            ticket["antworten"].append(message.content)

            if ticket["fragen"]:
                # nächste Frage
                frage = ticket["fragen"].pop(0)
                await message.channel.send(f"❓ {frage}")
            else:
                # Alle Fragen beantwortet -> Ticket ist "abgeschlossen" (await staff close)
                ticket["completed"] = True
                await message.channel.send("✅ Vielen Dank! Deine Antworten wurden gespeichert. Ein Teammitglied wird sich melden. Du kannst das Ticket schließen lassen, wenn alles geklärt ist.")

                # Sofortes Senden einer Kopie / Übersicht an den zuständigen Ziel-Channel
                ziel_channel_id = TICKET_TARGET_CHANNEL.get(ticket["art"])
                if ziel_channel_id:
                    ziel_channel = message.guild.get_channel(ziel_channel_id)
                    if ziel_channel:
                        antworten_text = "\n".join([f"**Antwort {i+1}:** {a}" for i, a in enumerate(ticket['antworten'])]) or "_Keine Antworten gefunden_"
                        embed = discord.Embed(
                            title=f"📩 Neues {ticket['art'].capitalize()}-Ticket (eingereicht)",
                            description=f"Von: {message.author.mention}\nChannel: <#{ticket['channel_id']}>",
                            color=discord.Color.blue()
                        )
                        embed.add_field(name="Antworten", value=antworten_text, inline=False)
                        embed.set_footer(text=f"Erstellt: {ticket.get('created_at')}")
                        await ziel_channel.send(embed=embed)

    # -------------------------
    # Originale on_message-Logik (EINSTELLUNGSKANAL_ID & Commands)
    # -------------------------
    if message.channel.id == EINSTELLUNGSKANAL_ID:
        try:
            channel = message.guild.get_channel(POST_CHANNEL_ID)
            if channel:
                # Alte Ranglisten-Nachricht löschen
                async for msg in channel.history(limit=50):
                    if msg.author == bot.user and msg.embeds:
                        embed = msg.embeds[0]
                        if embed.title == "📈 Unsere Police Officer":
                            try:
                                await msg.delete()
                            except discord.Forbidden:
                                logging.warning("Keine Berechtigung, alte Nachricht zu löschen.")
                            break

                embed = build_police_ranking_embed(message.guild)
                await channel.send(embed=embed)
        except Exception as e:
            logging.error(f"Fehler bei automatischer Ranglisten-Aktualisierung: {e}")

    # Damit Slash- und Prefix-Befehle weiterhin funktionieren
    await bot.process_commands(message)

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
# ✅ Slash-Befehle (einstellen/profil/entlassen/uprank/downrank/dienstnummern)
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

    user_ränge = [r for r in [guild.get_role(rid) for rid in POLICE_ROLLEN_IDS] if r in user.roles]
    if not user_ränge:
        await interaction.response.send_message("⚠️ Der Nutzer hat keine der Police Rollen.", ephemeral=True)
        return

    aktuelle_rolle = user_ränge[0]
    index = POLICE_ROLLEN_IDS.index(aktuelle_rolle.id)
    if index == 0:
        await interaction.response.send_message("⚠️ Der Nutzer ist bereits auf dem höchsten Rang.", ephemeral=True)
        return

    neue_rolle = guild.get_role(POLICE_ROLLEN_IDS[index - 1])
    if neue_rolle:
        await user.remove_roles(aktuelle_rolle)
        await user.add_roles(neue_rolle)
        await interaction.response.send_message(
            f"✅ {user.mention} wurde befördert von {aktuelle_rolle.name} zu {neue_rolle.name}."
        )
    else:
        await interaction.response.send_message("⚠️ Neue Rolle nicht gefunden.", ephemeral=True)

@tree.command(name="downrank", description="Degradiert einen User.")
@app_commands.describe(user="User, der degradiert werden soll")
async def downrank(interaction: discord.Interaction, user: discord.Member):
    guild = interaction.guild
    invoker = interaction.user

    if not any(discord.utils.get(invoker.roles, id=r) for r in BEFUGTE_RANG_IDS):
        await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
        return

    user_ränge = [r for r in [guild.get_role(rid) for rid in POLICE_ROLLEN_IDS] if r in user.roles]
    if not user_ränge:
        await interaction.response.send_message("⚠️ Der Nutzer hat keine der Police Rollen.", ephemeral=True)
        return

    aktuelle_rolle = user_ränge[0]
    index = POLICE_ROLLEN_IDS.index(aktuelle_rolle.id)
    if index == len(POLICE_ROLLEN_IDS) - 1:
        await interaction.response.send_message("⚠️ Der Nutzer ist bereits auf dem niedrigsten Rang.", ephemeral=True)
        return

    neue_rolle = guild.get_role(POLICE_ROLLEN_IDS[index + 1])
    if neue_rolle:
        await user.remove_roles(aktuelle_rolle)
        await user.add_roles(neue_rolle)
        await interaction.response.send_message(
            f"✅ {user.mention} wurde degradiert von {aktuelle_rolle.name} zu {neue_rolle.name}."
        )
    else:
        await interaction.response.send_message("⚠️ Neue Rolle nicht gefunden.", ephemeral=True)

@tree.command(name="dienstnummern", description="Zeigt eine Liste aller registrierten Mitglieder mit Dienstnummer.")
async def dienstnummern(interaction: discord.Interaction):
    if not registrierte_user:
        await interaction.response.send_message("📭 Es wurden noch keine Dienstnummern registriert.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📋 Dienstnummern-Liste",
        description="Alle registrierten Mitglieder mit Dienstnummer:",
        color=discord.Color.blue()
    )

    for user_id, daten in registrierte_user.items():
        mitglied = interaction.guild.get_member(user_id)
        if mitglied:
            embed.add_field(
                name=f"{mitglied.display_name}",
                value=f"> 🆔 **Dienstnummer:** `{daten['dienstnummer'].zfill(2)}`\n> 📛 **Name:** `{daten['name']}`",
                inline=False
            )

    embed.set_footer(text="BloodLife • Automatisch generierte Liste")
    await interaction.response.send_message(embed=embed)

# =========================
# Slash-Befehl: Ticket schließen (nur für Leitung/Admins)
# =========================
@tree.command(name="ticketclose", description="Schließt das aktuelle Ticket (nur Leitung/Admins).")
async def ticketclose(interaction: discord.Interaction):
    # Rechte prüfen
    if not any(role.id in BEFUGTE_RANG_IDS for role in interaction.user.roles):
        await interaction.response.send_message("❌ Du hast keine Berechtigung, Tickets zu schließen.", ephemeral=True)
        return

    channel = interaction.channel
    # Finde Ticket-Eintrag (falls vorhanden)
    ticket_owner_id = None
    for uid, data in user_tickets.items():
        if data.get("channel_id") == channel.id:
            ticket_owner_id = uid
            ticket_data = data
            break
    else:
        ticket_owner_id = None
        ticket_data = None

    # Wenn es ein Ticket-Channel ist: optionale Transkript-Sendung und Löschung
    if channel.name.startswith("ticket-"):
        # Wenn Ticket-Daten vorhanden -> sende Transkript an Ziel-Channel
        if ticket_data:
            ziel_channel_id = TICKET_TARGET_CHANNEL.get(ticket_data["art"])
            if ziel_channel_id:
                ziel_channel = interaction.guild.get_channel(ziel_channel_id)
                if ziel_channel:
                    antworten_text = "\n".join([f"**Antwort {i+1}:** {a}" for i, a in enumerate(ticket_data.get('antworten', []))]) or "_Keine Antworten_"
                    embed = discord.Embed(
                        title=f"🗂 Ticket-Transkript: {ticket_data['art'].capitalize()}",
                        description=f"Von: <@{ticket_owner_id}> (geschlossen von {interaction.user.mention})",
                        color=discord.Color.orange()
                    )
                    embed.add_field(name="Antworten", value=antworten_text, inline=False)
                    embed.set_footer(text=f"Erstellt: {ticket_data.get('created_at')}")
                    await ziel_channel.send(embed=embed)

            # Ticket aus Speicher entfernen
            try:
                del user_tickets[ticket_owner_id]
            except KeyError:
                pass

        await interaction.response.send_message("✅ Ticket wird geschlossen und gelöscht.", ephemeral=True)
        await channel.delete()
    else:
        await interaction.response.send_message("❌ Dies ist kein Ticket-Channel.", ephemeral=True)

# =========================
# Hilfsfunktion: Embed bauen (mit gedrehter Reihenfolge)
# =========================
def build_police_ranking_embed(guild):
    embed = discord.Embed(
        title="📈 Unsere Police Officer",
        description="Hier ist die aktuelle Übersicht des LSPD-Teams:\n",
        color=discord.Color.from_str("#8B0000")  # Dark Red
    )
    embed.set_thumbnail(url=LOGO_URL)

    # Rollen umkehren, damit Chief oben ist
    for role_id in reversed(POLICE_ROLLEN_IDS):
        role = guild.get_role(role_id)
        if not role:
            continue

        members = role.members
        if len(members) == 0:
            value = "_Keine Mitglieder_"
        else:
            # User mit @mention auflisten
            value = "\n".join([f"> {member.mention}" for member in members])

        embed.add_field(
            name=f"**{role.name}** 〔{len(members)}〕",
            value=value,
            inline=False
        )

    # Zeitstempel einfügen
    now = datetime.utcnow().strftime("%d.%m.%Y | %H:%M Uhr")
    embed.set_footer(text=f"BloodLife Police Department • Aktualisiert: {now}")

    # Optional größeres Bild oben
    embed.set_image(url=LOGO_URL)

    return embed

# =========================
# Webserver (für Uptime / Keepalive)
# =========================
app = Flask('')

@app.route('/')
def home():
    return "Bot ist online."

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()

# =========================
# Start des Bots
# =========================
keep_alive()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    logging.error("❌ Kein Bot-Token gefunden. Bitte setze die ENV Variable DISCORD_BOT_TOKEN.")
else:
    bot.run(TOKEN)
