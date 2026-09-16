import os
import json
import asyncio
from threading import Thread

import discord
from discord.ext import commands
from flask import Flask

# ----------------------------
# Flask keep-alive
# ----------------------------
app = Flask("")

@app.route("/")
def home():
    return "Bot actif"

def run_web_server():
    app.run(host="0.0.0.0", port=10000)

def keep_alive():
    Thread(target=run_web_server, daemon=True).start()

# ----------------------------
# Discord bot
# ----------------------------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------------
# Structure de données
# ----------------------------
# guild_id -> {channel_id: [user_ids]}
classements_par_salon = {}

# guild_id -> {channel_id: message_id}
id_messages_principaux = {}

# guild_id -> config
config_serveurs = {}

FICHIER_CONFIG = "config_serveurs.json"

# ----------------------------
# Configuration serveur
# ----------------------------
def charger_config_globale():
    if not os.path.exists(FICHIER_CONFIG):
        return {}
    try:
        with open(FICHIER_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def enregistrer_config_globale(data):
    with open(FICHIER_CONFIG, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def obtenir_config_serveur(guild_id):
    global config_serveurs
    gid_str = str(guild_id)
    configs = charger_config_globale()

    if gid_str not in configs:
        configs[gid_str] = {
            "role_admin_id": 0,
            "taille_team": 5,
            "noms_salons": {
                "1": "🏅 MAIN ROSTER",
                "2": "🥈 TEAM 2",
                "3": "🥉 TEAM 3",
                "4": "🎖 TEAM 4",
                "5": "🏆 TEAM 5",
                "6": "🎗 TEAM 6",
                "7": "✨ TEAM 7",
                "8": "🎫 TEAM 8",
            },
            "noms_roles": {
                "1": "Main Roster",
                "2": "Team 2",
                "3": "Team 3",
                "4": "Team 4",
                "5": "Team 5",
                "6": "Team 6",
                "7": "Team 7",
                "8": "Team 8",
            },
            "motifs_tickets": ["Admin", "Test Team", "Tryout"]
        }
        enregistrer_config_globale(configs)

    config_serveurs[guild_id] = configs[gid_str]
    return configs[gid_str]

def mettre_a_jour_config_serveur(guild_id, cle, valeur):
    configs = charger_config_globale()
    gid_str = str(guild_id)

    if gid_str not in configs:
        obtenir_config_serveur(guild_id)

    configs[gid_str][cle] = valeur
    enregistrer_config_globale(configs)
    config_serveurs[guild_id] = configs[gid_str]

def normaliser_nom_salon(nom):
    return nom.lower().replace("-", "").replace(" ", "").replace("\ufe0f", "")

# ----------------------------
# Utilitaires Top par salon
# ----------------------------
def obtenir_classement(guild_id, channel_id):
    if guild_id not in classements_par_salon:
        classements_par_salon[guild_id] = {}

    if channel_id not in classements_par_salon[guild_id]:
        classements_par_salon[guild_id][channel_id] = []

    return classements_par_salon[guild_id][channel_id]

def obtenir_id_message_top(guild_id, channel_id):
    return id_messages_principaux.get(guild_id, {}).get(channel_id)

def enregistrer_id_message_top(guild_id, channel_id, msg_id):
    if guild_id not in id_messages_principaux:
        id_messages_principaux[guild_id] = {}
    id_messages_principaux[guild_id][channel_id] = msg_id

async def rafraichir_classement(guild, channel_id):
    classement = obtenir_classement(guild.id, channel_id)
    channel = guild.get_channel(channel_id)

    if channel is None:
        return

    texte = f"🏆 **CLASSEMENT - #{channel.name}** 🏆\n\n"

    if not classement:
        texte += "*Aucun joueur dans ce classement pour le moment.*"
    else:
        for index, user_id in enumerate(classement):
            texte += f"**Top {index + 1}** : <@{user_id}>\n"

    msg_id = obtenir_id_message_top(guild.id, channel_id)

    try:
        if msg_id:
            msg = await channel.fetch_message(msg_id)
            await msg.edit(content=texte)
            return
    except Exception:
        pass

    msg = await channel.send(content=texte)
    enregistrer_id_message_top(guild.id, channel_id, msg.id)

# ----------------------------
# Commandes admin
# ----------------------------
@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def initialiser_salon_top(ctx):
    guild_id = ctx.guild.id
    channel_id = ctx.channel.id

    if guild_id not in classements_par_salon:
        classements_par_salon[guild_id] = {}

    classements_par_salon[guild_id][channel_id] = []

    msg_id = obtenir_id_message_top(guild_id, channel_id)
    if msg_id:
        try:
            msg = await ctx.channel.fetch_message(msg_id)
            await msg.delete()
        except Exception:
            pass

    id_messages_principaux.setdefault(guild_id, {}).pop(channel_id, None)

    await ctx.message.delete()
    await rafraichir_classement(ctx.guild, channel_id)

@bot.command(name="config")
@commands.has_permissions(administrator=True)
async def config_bot(ctx):
    await ctx.message.delete()
    conf = obtenir_config_serveur(ctx.guild.id)
    embed = discord.Embed(
        title="⚙️ Configuration du bot",
        description="Voici les paramètres actuels du serveur.",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Role admin ID", value=str(conf.get("role_admin_id", 0)), inline=False)
    embed.add_field(name="Taille du roster", value=str(conf.get("taille_team", 5)), inline=False)
    embed.add_field(name="Motifs tickets", value=", ".join(conf.get("motifs_tickets", [])) or "Aucun", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="add")
@commands.has_permissions(administrator=True)
async def ajouter_joueur(ctx, membre: discord.Member):
    classement = obtenir_classement(ctx.guild.id, ctx.channel.id)

    if membre.id not in classement:
        classement.append(membre.id)

    await ctx.message.delete()
    await rafraichir_classement(ctx.guild, ctx.channel.id)

@bot.command(name="addmany")
@commands.has_permissions(administrator=True)
async def ajouter_plusieurs_joueurs(ctx, *membres: discord.Member):
    classement = obtenir_classement(ctx.guild.id, ctx.channel.id)

    for membre in membres:
        if membre.id not in classement:
            classement.append(membre.id)

    await ctx.message.delete()
    await rafraichir_classement(ctx.guild, ctx.channel.id)

@bot.command(name="remove")
@commands.has_permissions(administrator=True)
async def supprimer_joueur_txt(ctx, membre: discord.Member):
    classement = obtenir_classement(ctx.guild.id, ctx.channel.id)

    if membre.id in classement:
        classement.remove(membre.id)

    await ctx.message.delete()
    await rafraichir_classement(ctx.guild, ctx.channel.id)

@bot.command(name="reset")
@commands.has_permissions(administrator=True)
async def reset_top_salon(ctx):
    classement = obtenir_classement(ctx.guild.id, ctx.channel.id)
    classement.clear()

    msg_id = obtenir_id_message_top(ctx.guild.id, ctx.channel.id)
    if msg_id:
        try:
            msg = await ctx.channel.fetch_message(msg_id)
            await msg.delete()
        except Exception:
            pass
        id_messages_principaux.setdefault(ctx.guild.id, {}).pop(ctx.channel.id, None)

    await ctx.message.delete()
    await rafraichir_classement(ctx.guild, ctx.channel.id)

@bot.command(name="showtop")
@commands.has_permissions(administrator=True)
async def afficher_top(ctx):
    await rafraichir_classement(ctx.guild, ctx.channel.id)

# ----------------------------
# Help
# ----------------------------
@bot.command(name="help_top")
@commands.has_permissions(administrator=True)
async def aide_top(ctx):
    texte = (
        "```"
        "!setup      -> Initialise le classement dans ce salon\n"
        "!add @user  -> Ajoute un joueur au classement du salon actuel\n"
        "!addmany @u1 @u2 ... -> Ajoute plusieurs joueurs\n"
        "!remove @user -> Retire un joueur du classement du salon actuel\n"
        "!reset      -> Vide le classement du salon actuel\n"
        "!showtop    -> Rafraîchit le classement dans ce salon\n"
        "!config     -> Affiche la config du serveur\n"
        "```"
    )
    await ctx.send(texte)

# ----------------------------
# Événements
# ----------------------------
@bot.event
async def on_ready():
    print(f"Bot connecté : {bot.user.name}")
    print("Le classement est maintenant géré par salon.")

# ----------------------------
# Lancement
# ----------------------------
keep_alive()
bot.run(os.environ.get("DISCORD_TOKEN"))