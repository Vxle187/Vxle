# ----------------------------------
# LSPD Discord Bot – FIXED & READY
# ----------------------------------

import os
import logging
import threading
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select
from flask import Flask

# =========================
# Logging
# =========================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("lspd-bot")

# =========================
# Discord-Setup
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# =========================
# Server/Kanal/Kategorie-IDs
# =========================
SERVER_ID = 1396969113955602562

# Willkommens-/Leave-/Post-Kanäle
WILLKOMMEN_KANAL_ID = 1396969114039226598
LEAVE_KANAL_ID = 1396969114442006538
POST_CHANNEL_ID = 1396969114039226599  # Ranking/Logs/Transkript-Fallback

# Panel-Zielkanal
TICKET_PANEL_CHANNEL_ID = 1396969114442006539

# Ticket-Kategorien (deine Category-IDs!)
TICKET_CATEGORY_IDS = {
    "bewerbung": 1410111339359113318,
    "beschwerde": 1410111382237483088,
    "leitung": 1410111463783268382,
}

# Berechtigungsrolle zum /tickets posten & /ticketclose
TICKET_ADMIN_ROLE_ID = 1410124850265198602

# Rollen/Ranking
POLICE_ROLLEN_IDS = list(reversed([
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
]))
ROLLEN_IDS = [
    1396969113955602569,
    1396969114022711376,
]
BEFUGTE_RANG_IDS = [
    1396969114005930128,
    1396969114031095936,
    1396969114031095937,
    1396969114039226595,
]
ERLAUBTE_ROLLEN_ID = 1401284034109243557  # Für !loeschen

# Auto-Rolle bei Join
AUTO_ROLE_ID = 1396969113955602563

# Logo
LOGO_URL = "https://cdn.discordapp.com/attachments/1396969116195360941/1401653566283710667/IMG_2859.png"

# =========================
# Datenspeicher
# =========================
registrierte_user = {}
user_tickets = {}
# Struktur:
# user_tickets[user_id] = {
#   "channel_id": int,
#   "art": "bewerbung"|"beschwerde"|"leitung",
#   "fragen": [..],
#   "antworten": [],
#   "created_at": "dd.mm.YYYY | HH:MM Uhr",
#   "completed": bool
# }

# Fragen je Ticket-Art
ticket_fragen = {
    "bewerbung": [
        "Wie lautet dein vollständiger Name?",
        "Wie alt bist du?",
        "Warum möchtest du Teil unseres Teams werden?",
        "Welche Erfahrungen bringst du mit?",
    ],
    "beschwerde": [
        "Wen betrifft die Beschwerde? (Name/ID)",
        "Bitte beschreibe die Situation so detailliert wie möglich.",
        "Wann ist es passiert?",
        "Hast du Beweise (Screenshots, Chatlogs etc.)?",
    ],
    "leitung": [
        "Welches Anliegen möchtest du der Leitung mitteilen?",
        "Wie dringend ist dein Anliegen (1-10)?",
        "Möchtest du anonym bleiben? (Ja/Nein)",
    ],
}

# =========================
# Utils
# =========================
def resolve_target_text_channel(guild: discord.Guild, target_id: int) -> discord.TextChannel | None:
    """Gibt einen Textkanal in einer Kategorie zurück, oder None."""
    if not guild:
        return None
    target = guild.get_channel(target_id)
    if isinstance(target, discord.TextChannel):
        return target
    if isinstance(target, discord.CategoryChannel):
        # zuerst einen Kanal mit ticket/log/team im Namen
        for ch in target.channels:
            if isinstance(ch, discord.TextChannel) and any(k in ch.name for k in ("ticket", "log", "team")):
                return ch
        # sonst der erste Textkanal
        for ch in target.channels:
            if isinstance(ch, discord.TextChannel):
                return ch
    # Fallback
    fb = guild.get_channel(POST_CHANNEL_ID)
    return fb if isinstance(fb, discord.TextChannel) else None

def build_police_ranking_embed(guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(
        title="📈 Unsere Police Officer",
        description="Hier ist die aktuelle Übersicht des LSPD-Teams:",
        color=discord.Color.from_str("#8B0000"),
    )
    embed.set_thumbnail(url=LOGO_URL)
    now = datetime.utcnow().strftime("%d.%m.%Y | %H:%M Uhr")

    # Chief oben → POLICE_ROLLEN_IDS ist bereits highest→lowest
    for role_id in POLICE_ROLLEN_IDS:
        role = guild.get_role(role_id)
        if not role:
            continue
        members = role.members
        value = "_Keine Mitglieder_" if not members else "\n".join(f"> {m.mention}" for m in members)
        embed.add_field(name=f"**{role.name}** 〔{len(members)}〕", value=value, inline=False)

    embed.set_footer(text=f"BloodLife Police Department • Aktualisiert: {now}", icon_url=LOGO_URL)
    embed.set_image(url=LOGO_URL)
    return embed

async def start_ticket_dialog(channel: discord.TextChannel, user: discord.Member, art: str):
    """Frage/Antwort-Dialog im Ticket-Channel führen und anschließend Zusammenfassung posten."""
    qlist = list(ticket_fragen.get(art, []))
    intro = {
        "bewerbung": f"Hallo {user.mention}, willkommen im **Bewerbungs**-Ticket! Bitte beantworte folgende Fragen:",
        "beschwerde": f"Hallo {user.mention}, dies ist dein **Beschwerde**-Ticket. Bitte beantworte:",
        "leitung": f"Hallo {user.mention}, **Leitung**-Ticket eröffnet. Bitte beantworte kurz:",
    }.get(art, f"Hallo {user.mention}, bitte beantworte die folgenden Fragen:")

    await channel.send(intro)

    answers: list[tuple[str, str]] = []

    def check(m: discord.Message) -> bool:
        return (m.channel.id == channel.id) and (m.author.id == user.id)

    try:
        for i, q in enumerate(qlist, start=1):
            await channel.send(f"**{i}. {q}**")
            msg = await bot.wait_for("message", check=check, timeout=600)
            answers.append((q, msg.content))
    except Exception as e:
        await channel.send(f"⚠️ Dialog abgebrochen/Fehler: `{e}`")

    # Zusammenfassung
    embed = discord.Embed(
        title=f"Ticket-Zusammenfassung: {art.title()}",
        color=discord.Color.from_str("#2F3136"),
    )
    embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
    for q, a in answers:
        a_trim = a if len(a) <= 1024 else a[:1021] + "..."
        embed.add_field(name=q, value=a_trim, inline=False)
    embed.set_footer(text="BloodLife Police Department", icon_url=LOGO_URL)
    embed.set_thumbnail(url=LOGO_URL)
    await channel.send(content="Danke! Hier ist deine Zusammenfassung:", embed=embed)

# =========================
# Ticket-UI
# =========================
class TicketSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="📄 Bewerbung", value="bewerbung", description="Starte deine Bewerbung"),
            discord.SelectOption(label="⚠️ Beschwerde", value="beschwerde", description="Reiche eine Beschwerde ein"),
            discord.SelectOption(label="📢 Leitungsanliegen", value="leitung", description="Kontaktiere die Leitung"),
        ]
        super().__init__(
            placeholder="Bitte wähle einen Grund",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_dropdown",
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user
        art = self.values[0]

        category_id = TICKET_CATEGORY_IDS.get(art)
        category = guild.get_channel(category_id) if category_id else None

        base_name = f"{art}-{user.name}".replace(" ", "-").lower()
        channel_name = base_name[:90]

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, manage_messages=True),
        }

        # Channel in Kategorie erstellen
        if isinstance(category, discord.CategoryChannel):
            ticket_channel = await guild.create_text_channel(channel_name, overwrites=overwrites, category=category)
        else:
            ticket_channel = await guild.create_text_channel(channel_name, overwrites=overwrites)

        created_at = datetime.utcnow().strftime("%d.%m.%Y | %H:%M Uhr")
        user_tickets[user.id] = {
            "channel_id": ticket_channel.id,
            "art": art,
            "fragen": list(ticket_fragen.get(art, [])),
            "antworten": [],
            "created_at": created_at,
            "completed": False,
        }

        # Begrüßung im Ticket
        start_embed = discord.Embed(
            title=f"🎫 Ticket: {art.title()}",
            description="Bitte beantworte der Reihe nach die Fragen. Du hast pro Frage 10 Minuten Zeit.",
            color=discord.Color.blue(),
        )
        start_embed.set_thumbnail(url=LOGO_URL)
        await ticket_channel.send(embed=start_embed)

        # Start Dialog (nicht blockierend für Interaktion-Antwort)
        bot.loop.create_task(start_ticket_dialog(ticket_channel, user, art))

        # Ephemeral Bestätigung
        try:
            await interaction.response.send_message(f"✅ Ticket erstellt: {ticket_channel.mention}", ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(f"✅ Ticket erstellt: {ticket_channel.mention}", ephemeral=True)

class TicketDropdown(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# =========================
# Slash-Befehle – Panel, Close, Rollen, Dienst
# =========================
@tree.command(name="tickets", description="Postet das Ticket-Panel in den vorgesehenen Kanal.")
async def tickets(interaction: discord.Interaction):
    role = interaction.guild.get_role(TICKET_ADMIN_ROLE_ID)
    if role not in interaction.user.roles:
        await interaction.response.send_message("❌ Du hast keine Berechtigung, das Ticket-Panel zu posten.", ephemeral=True)
        return

    channel = interaction.guild.get_channel(TICKET_PANEL_CHANNEL_ID)
    if not channel:
        await interaction.response.send_message("❌ Ticket-Panel-Kanal wurde nicht gefunden.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎫 Ticket-System",
        description=(
            "Willkommen im Ticketsystem! Bitte wähle einen Grund aus, um dein Ticket zu erstellen.\n\n"
            "📄 **Bewerbung** → Bewerbungen\n"
            "⚠️ **Beschwerde** → Beschwerden\n"
            "📢 **Leitungsanliegen** → Direkt zur Leitung"
        ),
        color=discord.Color.blue(),
    )
    embed.set_thumbnail(url=LOGO_URL)
    embed.set_image(url=LOGO_URL)
    embed.set_footer(text="BloodLife Police Department", icon_url=LOGO_URL)

    await channel.send(embed=embed, view=TicketDropdown())
    await interaction.response.send_message("✅ Ticket-Panel wurde gepostet.", ephemeral=True)

@tree.command(name="ticketclose", description="Schließt das aktuelle Ticket (nur Leitung/Admins).")
async def ticketclose(interaction: discord.Interaction):
    # Berechtigung
    if not any((role.id == TICKET_ADMIN_ROLE_ID) or (role.id in BEFUGTE_RANG_IDS) for role in interaction.user.roles):
        await interaction.response.send_message("❌ Du hast keine Berechtigung, Tickets zu schließen.", ephemeral=True)
        return

    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message("❌ Dieser Befehl muss in einem Ticket-Channel ausgeführt werden.", ephemeral=True)
        return

    # Ticket-Datensatz finden
    owner_id = None
    data = None
    for uid, t in user_tickets.items():
        if t.get("channel_id") == channel.id:
            owner_id = uid
            data = t
            break

    # Optional Transkript an Kategorie-Info-Kanal
    if data:
        category_id = TICKET_CATEGORY_IDS.get(data["art"])
        ziel = resolve_target_text_channel(interaction.guild, category_id)
        if ziel:
            antworten_text = "\n".join([f"**Antwort {i+1}:** {a}" for i, a in enumerate(data.get("antworten", []))]) or "_Keine Antworten_"
            embed = discord.Embed(
                title=f"🗂 Ticket-Transkript: {data['art'].title()}",
                description=f"Von: <@{owner_id}> • geschlossen von {interaction.user.mention}",
                color=discord.Color.orange(),
            )
            embed.add_field(name="Antworten", value=antworten_text, inline=False)
            embed.set_footer(text=f"Erstellt: {data.get('created_at')}", icon_url=LOGO_URL)
            embed.set_thumbnail(url=LOGO_URL)
            await ziel.send(embed=embed)
        user_tickets.pop(owner_id, None)

    await interaction.response.send_message("✅ Ticket wird geschlossen…", ephemeral=True)
    try:
        await channel.delete()
    except discord.Forbidden:
        await interaction.followup.send("⚠️ Ich habe keine Berechtigung, den Kanal zu löschen.", ephemeral=True)

# Rolle vergeben
@tree.command(name="rolle", description="Vergibt eine Rolle an einen bestimmten User (nur Leitung).")
@app_commands.describe(user="Der User, der die Rolle bekommen soll", rolle="Die Rolle, die vergeben werden soll")
async def rolle(interaction: discord.Interaction, user: discord.Member, rolle: discord.Role):
    berechtigungsrolle = interaction.guild.get_role(1410223848657522698)
    if berechtigungsrolle not in interaction.user.roles:
        await interaction.response.send_message("❌ Du hast keine Berechtigung, diesen Befehl zu nutzen.", ephemeral=True)
        return
    try:
        await user.add_roles(rolle)
        await interaction.response.send_message(f"✅ {user.mention} hat die Rolle **{rolle.name}** erhalten.")
    except Exception as e:
        await interaction.response.send_message(f"⚠️ Fehler: {e}", ephemeral=True)

# Dienstbezogene Befehle
@tree.command(name="einstellen", description="Stellt eine Person ein, gibt Rollen und setzt den Namen.")
@app_commands.describe(user="Wähle den User aus", dienstnummer="Trage die Dienstnummer ein", name="Trage den Namen ein")
async def einstellen(interaction: discord.Interaction, user: discord.Member, dienstnummer: str, name: str):
    guild = interaction.guild
    registrierte_user[user.id] = {"dienstnummer": dienstnummer, "name": name}

    hinzu = []
    for rid in ROLLEN_IDS:
        rolle = guild.get_role(rid)
        if rolle:
            await user.add_roles(rolle)
            hinzu.append(rolle.name)
        else:
            await interaction.response.send_message(f"⚠️ Rolle mit ID `{rid}` nicht gefunden!", ephemeral=True)
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
        f"🎓 Rollen: {', '.join(hinzu)}"
    )

@tree.command(name="profil", description="Zeigt dein Profil an.")
async def profil(interaction: discord.Interaction):
    uid = interaction.user.id
    if uid in registrierte_user:
        d = registrierte_user[uid]
        await interaction.response.send_message(
            f"🧾 Dein Profil:\n"
            f"📄 Dienstnummer: `{d['dienstnummer'].zfill(2)}`\n"
            f"📛 Name: `{d['name']}`"
        )
    else:
        await interaction.response.send_message("⚠️ Du bist noch nicht registriert. Nutze `/einstellen`.", ephemeral=True)

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

    user_r = [r for r in [guild.get_role(rid) for rid in POLICE_ROLLEN_IDS] if r in user.roles]
    if not user_r:
        await interaction.response.send_message("⚠️ Der Nutzer hat keine der Police Rollen.", ephemeral=True)
        return

    aktuelle = user_r[0]
    idx = POLICE_ROLLEN_IDS.index(aktuelle.id)
    if idx == 0:
        await interaction.response.send_message("⚠️ Der Nutzer ist bereits auf dem höchsten Rang.", ephemeral=True)
        return

    neue = guild.get_role(POLICE_ROLLEN_IDS[idx - 1])
    if neue:
        await user.remove_roles(aktuelle)
        await user.add_roles(neue)
        await interaction.response.send_message(f"✅ {user.mention} wurde befördert: {aktuelle.name} → {neue.name}.")
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

    user_r = [r for r in [guild.get_role(rid) for rid in POLICE_ROLLEN_IDS] if r in user.roles]
    if not user_r:
        await interaction.response.send_message("⚠️ Der Nutzer hat keine der Police Rollen.", ephemeral=True)
        return

    aktuelle = user_r[0]
    idx = POLICE_ROLLEN_IDS.index(aktuelle.id)
    if idx == len(POLICE_ROLLEN_IDS) - 1:
        await interaction.response.send_message("⚠️ Der Nutzer ist bereits auf dem niedrigsten Rang.", ephemeral=True)
        return

    neue = guild.get_role(POLICE_ROLLEN_IDS[idx + 1])
    if neue:
        await user.remove_roles(aktuelle)
        await user.add_roles(neue)
        await interaction.response.send_message(f"✅ {user.mention} wurde degradiert: {aktuelle.name} → {neue.name}.")
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
        color=discord.Color.blue(),
    )
    embed.set_thumbnail(url=LOGO_URL)
    for user_id, daten in registrierte_user.items():
        member = interaction.guild.get_member(user_id)
        if member:
            embed.add_field(
                name=f"{member.display_name}",
                value=f"> 🆔 **Dienstnummer:** `{daten['dienstnummer'].zfill(2)}`\n> 📛 **Name:** `{daten['name']}`",
                inline=False,
            )
    embed.set_footer(text="BloodLife • Automatisch generierte Liste", icon_url=LOGO_URL)
    await interaction.response.send_message(embed=embed)

# =========================
# Textbefehle – löschen
# =========================
@bot.command(name="loeschen")
async def loeschen(ctx: commands.Context, anzahl: int):
    await nachrichten_loeschen(ctx, anzahl)

@bot.command(name="löschen")
async def löschen_umlaut(ctx: commands.Context, anzahl: int):
    await nachrichten_loeschen(ctx, anzahl)

async def nachrichten_loeschen(ctx: commands.Context, anzahl: int):
    erlaubnis = discord.utils.get(ctx.author.roles, id=ERLAUBTE_ROLLEN_ID)
    if not erlaubnis:
        await ctx.send("❌ Du hast keine Berechtigung für diesen Befehl.")
        return
    if anzahl < 1 or anzahl > 100:
        await ctx.send("⚠️ Du kannst nur zwischen 1 und 100 Nachrichten löschen.")
        return
    await ctx.channel.purge(limit=anzahl + 1)
    await ctx.send(f"🧹 {anzahl} Nachrichten gelöscht.", delete_after=5)

# =========================
# Events
# =========================
@bot.event
async def on_ready():
    await tree.sync()
    bot.add_view(TicketDropdown())  # persistente View
    log.info(f"✅ Bot online als {bot.user} (Guilds: {[g.id for g in bot.guilds]})")

    # Ticket-Panel auto-posten (nur wenn noch nicht im Verlauf)
    guild = bot.get_guild(SERVER_ID)
    if guild:
        panel_channel = guild.get_channel(TICKET_PANEL_CHANNEL_ID)
        if isinstance(panel_channel, discord.TextChannel):
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
                    description=(
                        "Willkommen im Ticketsystem! Bitte wähle einen Grund aus, um dein Ticket zu erstellen.\n\n"
                        "**Wichtig:** Bitte beschreibe dein Anliegen so genau wie möglich."
                    ),
                    color=discord.Color.red(),
                )
                embed.set_thumbnail(url=LOGO_URL)
                embed.set_footer(text="BloodLife Police Department", icon_url=LOGO_URL)
                await panel_channel.send(embed=embed, view=TicketDropdown())
                log.info("📌 Ticket-Panel automatisch gepostet.")

@bot.event
async def on_member_join(member: discord.Member):
    if member.guild.id != SERVER_ID:
        return
    # Willkommens-Embed
    channel = member.guild.get_channel(WILLKOMMEN_KANAL_ID)
    if isinstance(channel, discord.TextChannel):
        embed = discord.Embed(
            title=f"{member.display_name}, willkommen auf **Blood Life Police Department** 👮",
            description="📚 **Schön, dass du da bist!**\n❗ **Bitte halte dich im Dienst an die Funkcodes**\n\n🛡️ **Fragen?** Wende dich an die Leitung!",
            color=discord.Color.dark_blue(),
        )
        embed.set_author(name="Police Department | BloodLife", icon_url=member.guild.icon.url if member.guild.icon else discord.Embed.Empty)
        embed.set_thumbnail(url=LOGO_URL)
        embed.set_footer(text="Willkommen auf dem BloodLife Police Department Discord!", icon_url=LOGO_URL)
        await channel.send(embed=embed)

    # Auto-Rolle
    role = member.guild.get_role(AUTO_ROLE_ID)
    if role:
        try:
            await member.add_roles(role)
        except Exception as e:
            log.warning(f"Auto-Role fehlgeschlagen: {e}")

@bot.event
async def on_member_remove(member: discord.Member):
    if member.guild.id != SERVER_ID:
        return
    channel = member.guild.get_channel(LEAVE_KANAL_ID)
    if isinstance(channel, discord.TextChannel):
        embed = discord.Embed(
            title="👋 Auf Wiedersehen!",
            description=f"{member.mention} hat den Server verlassen, wir hoffen, wir sehen uns bald wieder!",
            color=discord.Color.dark_grey(),
        )
        embed.set_thumbnail(url=LOGO_URL)
        embed.set_footer(text="BloodLife Police Department", icon_url=LOGO_URL)
        await channel.send(embed=embed)

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    # wenn Rollen aus POLICE_ROLLEN_IDS sich ändern → Ranking neu posten
    if set(r.id for r in before.roles) == set(r.id for r in after.roles):
        return
    if not any(((rid in [r.id for r in before.roles]) != (rid in [r.id for r in after.roles])) for rid in POLICE_ROLLEN_IDS):
        return

    ch = after.guild.get_channel(POST_CHANNEL_ID)
    if isinstance(ch, discord.TextChannel):
        # alte Rangliste entfernen
        async for msg in ch.history(limit=50):
            if msg.author == bot.user and msg.embeds and msg.embeds[0].title == "📈 Unsere Police Officer":
                try:
                    await msg.delete()
                except discord.Forbidden:
                    pass
                break
        await ch.send(embed=build_police_ranking_embed(after.guild))

@bot.event
async def on_message(message: discord.Message):
    # Bots ignorieren
    if message.author.bot:
        return

    # Ticket-Antworten: Wenn User in seinem Ticket-Channel schreibt, speichere & stelle Folgefrage
    uid = message.author.id
    if uid in user_tickets:
        t = user_tickets[uid]
        if message.channel.id == t["channel_id"]:
            # nur Owner zählt
            t["antworten"].append(message.content)
            if t["fragen"]:
                frage = t["fragen"].pop(0)
                await message.channel.send(f"❓ {frage}")
            else:
                t["completed"] = True
                await message.channel.send("✅ Vielen Dank! Deine Antworten wurden gespeichert. Ein Teammitglied meldet sich bald.")

                # Übersicht an Zielkanal in der passenden Kategorie
                category_id = TICKET_CATEGORY_IDS.get(t["art"])
                ziel = resolve_target_text_channel(message.guild, category_id)
                if ziel:
                    antworten_text = "\n".join([f"**Antwort {i+1}:** {a}" for i, a in enumerate(t['antworten'])]) or "_Keine Antworten gefunden_"
                    embed = discord.Embed(
                        title=f"📩 Neues {t['art'].title()}-Ticket (eingereicht)",
                        description=f"Von: {message.author.mention}\nChannel: <#{t['channel_id']}>",
                        color=discord.Color.blue(),
                    )
                    embed.add_field(name="Antworten", value=antworten_text, inline=False)
                    embed.set_footer(text=f"Erstellt: {t.get('created_at')}", icon_url=LOGO_URL)
                    embed.set_thumbnail(url=LOGO_URL)
                    await ziel.send(embed=embed)

    await bot.process_commands(message)

# =========================
# Flask – Keepalive (für Render/gunicorn)
# =========================
app = Flask(__name__)

@app.get("/")
def home():
    return "Bot ist online."

def run_web():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = threading.Thread(target=run_web, daemon=True)
    t.start()

# =========================
# Start
# =========================
if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    if not TOKEN:
        log.error("❌ Kein Bot-Token gefunden. Bitte setze die ENV-Variable DISCORD_BOT_TOKEN.")
    else:
        bot.run(TOKEN)
