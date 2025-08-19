def build_ranking_embed(guild):
    embed = discord.Embed(
        title="👮 Polizei Rangliste (automatisch aktualisiert)",
        description="📋 Aktueller Stand aller LSPD-Dienstgrade:",
        color=discord.Color.dark_blue()
    )
    embed.set_thumbnail(url=LOGO_URL)

    rang_emojis = {
        1396969114022711376: "🔴 ⭐⭐⭐⭐⭐",  # Chief of Police
        1396969114022711377: "🔴 ⭐⭐⭐⭐",
        1396969114022711378: "🔴 ⭐⭐⭐",
        1396969114022711383: "🔴 ⚙️",
        1396969114031095929: "⚪ 🌟",
        1396969114031095930: "🟣 ▇▇▇",
        1396969114031095931: "🟣 ▇▇",
        1396969114031095932: "🔵 ▇",
        1396969114031095933: "🔵 ▲▲▲",
        1396969114031095935: "🔵 ▲▢",
        1396969114031095936: "🟢 ~",
        1396969114031095937: "🟢 ○",
    }

    rang_names = {
        1396969114022711376: "Chief of Police",
        1396969114022711377: "Assistant Chief",
        1396969114022711378: "Deputy Chief",
        1396969114022711383: "Commander",
        1396969114031095929: "Major",
        1396969114031095930: "Captain",
        1396969114031095931: "First Lieutenant",
        1396969114031095932: "Lieutenant",
        1396969114031095933: "Sergeant",
        1396969114031095935: "II Officer",
        1396969114031095936: "Officer",
        1396969114031095937: "Rekrut",
    }

    for role_id in RANGLISTE:
        role = guild.get_role(role_id)
        if not role:
            continue
        emoji = rang_emojis.get(role_id, "")
        name = rang_names.get(role_id, role.name)

        if len(role.members) > 0:
            max_anzeigen = 5
            member_mentions = [member.mention for member in role.members[:max_anzeigen]]
            rest = len(role.members) - max_anzeigen
            if rest > 0:
                member_mentions.append(f"und {rest} weitere")
            mitglieder_text = " ".join(member_mentions)
            value_text = mitglieder_text
        else:
            # Keine Mitglieder, nur Rang ohne weiteren Text
            value_text = "‎"  # unsichtbares Leerzeichen, damit Feld nicht komplett leer ist

        embed.add_field(
            name=f"{emoji} | {name}",
            value=value_text,
            inline=False
        )

    embed.set_footer(text=f"Stand: <t:{int(discord.utils.utcnow().timestamp())}:D>")

    return embed
