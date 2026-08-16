import discord
from discord.ext import commands
import asyncio
from flask import Flask
from threading import Thread

# --- CONFIGURATION DU MINI-SERVEUR WEB POUR GARDER LE BOT REVEILLÉ ---
app = Flask('')

@app.route('/')
def home():
    return "Le bot est en ligne et fonctionnel !"

def run_web_server():
    # Le serveur tourne sur le port 10000 exigé par Render
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

# --- CONFIGURATION DU BOT DISCORD ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

classement_top = []

def obtenir_equipe_et_salon(position):
    if position <= 5:
        return 1
    else:
        return 2 + (position - 6) // 6

async def rafraichir_messages_et_roles(guild):
    total_joueurs = len(classement_top)
    max_team_necessaire = obtenir_equipe_et_salon(total_joueurs) if total_joueurs > 0 else 1

    for num_team in range(1, max_team_necessaire + 1):
        nom_role = f"Team {num_team}"
        nom_salon = f"team-{num_team}"

        role = discord.utils.get(guild.roles, name=nom_role)
        if not role:
            role = await guild.create_role(name=nom_role, reason="Création auto par le système de Top")

        salon = discord.utils.get(guild.channels, name=nom_salon)
        if not salon:
            await guild.create_text_channel(name=nom_salon, reason="Création auto par le système de Top")

    for index, user_id in enumerate(classement_top):
        position = index + 1
        num_team_actuelle = obtenir_equipe_et_salon(position)
        
        member = guild.get_member(user_id)
        if member:
            role_cible = discord.utils.get(guild.roles, name=f"Team {num_team_actuelle}")
            roles_a_retirer = [r for r in member.roles if r.name.startswith("Team ") and r != role_cible]
            if roles_a_retirer:
                await member.remove_roles(*roles_a_retirer)
                
            if role_cible and role_cible not in member.roles:
                await member.add_roles(role_cible)

    for num_team in range(1, max_team_necessaire + 1):
        nom_salon = f"team-{num_team}"
        salon = discord.utils.get(guild.channels, name=nom_salon)
        
        if salon:
            try:
                await salon.purge(limit=100)
            except Exception:
                pass

            lignes_joueurs = []
            for index, user_id in enumerate(classement_top):
                pos = index + 1
                if obtenir_equipe_et_salon(pos) == num_team:
                    lignes_joueurs.append(f"**Top {pos}** : <@{user_id}>")

            if lignes_joueurs:
                texte_message = f"🏆 **Classement Actuel - Team {num_team}** 🏆\n\n" + "\n".join(lignes_joueurs)
                await salon.send(texte_message)
            else:
                await salon.send(f"Cette équipe (*Team {num_team}*) n'a pas encore de joueurs assignés.")

@bot.command(name="add")
@commands.has_permissions(administrator=True)
async def ajouter_joueur_top(ctx, membre: discord.Member, position: int):
    global classement_top
    index_cible = position - 1

    if index_cible < 0:
        await ctx.send("❌ La position doit être supérieure ou égale à 1.")
        return
    if index_cible > len(classement_top):
        index_cible = len(classement_top)

    if membre.id in classement_top:
        classement_top.remove(membre.id)

    classement_top.insert(index_cible, membre.id)
    await ctx.send(f"✅ {membre.mention} a été inséré au **Top {index_cible + 1}**.")
    await rafraichir_messages_et_roles(ctx.guild)

@bot.event
async def on_ready():
    print(f"Le bot {bot.user.name} est en ligne !")

# Lancement du mini-site web puis du bot Discord
keep_alive()
import os
bot.run(os.environ.get("DISCORD_TOKEN"))
