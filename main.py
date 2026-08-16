import discord
from discord.ext import commands
import asyncio
from flask import Flask
from threading import Thread
import os

# --- SERVEUR WEB KEEP-ALIVE ---
app = Flask('')
@app.route('/')
def home(): return "Bot de classement actif !"
def run_web_server(): app.run(host='0.0.0.0', port=10000)
def keep_alive(): Thread(target=run_web_server).start()

# --- CONFIGURATION BOT ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Liste globale en mémoire pour stocker les IDs des joueurs dans l'ordre du TOP
classement_top = []
id_message_principal = None
id_salon_principal = None

def obtenir_equipe_et_salon(position):
    if position <= 5: return 1
    return 2 + (position - 6) // 6

async def rafraichir_partout(guild):
    global id_message_principal, id_salon_principal
    if not id_salon_principal: return

    total_joueurs = len(classement_top)
    max_team = obtenir_equipe_et_salon(total_joueurs) if total_joueurs > 0 else 1

    # 1. Création des rôles / salons manquants
    for num_team in range(1, max_team + 1):
        if not discord.utils.get(guild.roles, name=f"Team {num_team}"):
            await guild.create_role(name=f"Team {num_team}")
        if not discord.utils.get(guild.channels, name=f"team-{num_team}"):
            await guild.create_text_channel(name=f"team-{num_team}")

    # 2. Mise à jour des rôles des membres
    for index, user_id in enumerate(classement_top):
        pos = index + 1
        team_cible = obtenir_equipe_et_salon(pos)
        member = guild.get_member(user_id)
        if member:
            role_bon = discord.utils.get(guild.roles, name=f"Team {team_cible}")
            roles_mauvais = [r for r in member.roles if r.name.startswith("Team ") and r != role_bon]
            if roles_mauvais: await member.remove_roles(*roles_mauvais)
            if role_bon and role_bon not in member.roles: await member.add_roles(role_bon)

    # 3. Mise à jour du message du TOP Principal
    salon_top = guild.get_channel(id_salon_principal)
    if salon_top:
        texte_top = "🏆 **CLASSEMENT GÉNÉRAL COMPLET** 🏆\n\n"
        if not classement_top:
            texte_top += "*Aucun joueur dans le top pour le moment.*"
        for index, u_id in enumerate(classement_top):
            texte_top += f"**Top {index + 1}** : <@{u_id}>\n"
        
        view = VueControleTop()
        if id_message_principal:
            try:
                msg = await salon_top.fetch_message(id_message_principal)
                await msg.edit(content=texte_top, view=view)
            except discord.NotFound:
                msg = await salon_top.send(content=texte_top, view=view)
                id_message_principal = msg.id
        else:
            msg = await salon_top.send(content=texte_top, view=view)
            id_message_principal = msg.id

    # 4. Mise à jour des salons d'équipes individuels
    for num_team in range(1, max_team + 1):
        salon_team = discord.utils.get(guild.channels, name=f"team-{num_team}")
        if salon_team:
            try: await salon_team.purge(limit=50)
            except: pass
            lignes = [f"**Top {i+1}** : <@{uid}>" for i, uid in enumerate(classement_top) if obtenir_equipe_et_salon(i+1) == num_team]
            if lignes:
                await salon_team.send(f"🏆 **Membres - Team {num_team}** 🏆\n\n" + "\n".join(lignes))
            else:
                await salon_team.send(f"Aucun joueur dans la Team {num_team}.")

# --- INTERFACES VISUELLES (BOUTONS & POP-UP) ---
class FenetreDeplacement(discord.ui.Modal, title="Changer la place d'un joueur"):
    pos_depart = discord.ui.TextInput(label="Position actuelle du joueur", placeholder="Ex: 5")
    pos_arrivee = discord.ui.TextInput(label="Sa nouvelle position voulue", placeholder="Ex: 2")

    async def on_submit(self, interaction: discord.Interaction):
        global classement_top
        try:
            p_dep = int(self.pos_depart.value) - 1
            p_arr = int(self.pos_arrivee.value) - 1
            
            if p_dep < 0 or p_arr < 0 or p_dep >= len(classement_top) or p_arr >= len(classement_top):
                await interaction.response.send_message("❌ Positions invalides. Vérifiez le classement actuel.", ephemeral=True)
                return
            
            # Algorithme de déplacement avec décalage automatique :
            # On retire le joueur de son ancienne position et on l'insère à la nouvelle
            joueur_id = classement_top.pop(p_dep)
            classement_top.insert(p_arr, joueur_id)
            
            await interaction.response.send_message("📈 Déplacement effectué et classement décalé ! Mise à jour...", ephemeral=True)
            await rafraichir_partout(interaction.guild)
        except ValueError:
            await interaction.response.send_message("❌ Veuillez entrer des nombres entiers.", ephemeral=True)

class VueControleTop(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Changer de place 📈", style=discord.ButtonStyle.primary, custom_id="bouton_deplacer_top")
    async def bouton_deplace(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Tu dois être administrateur.", ephemeral=True)
            return
        await interaction.response.send_modal(FenetreDeplacement())

# --- COMMANDES ADMIN ---
@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def initialiser_salon_top(ctx):
    """Crée le panneau du Top dans le salon actuel (Ex: !setup)"""
    global id_salon_principal, id_message_principal
    id_salon_principal = ctx.channel.id
    id_message_principal = None
    await ctx.message.delete()
    await rafraichir_partout(ctx.guild)

@bot.command(name="add")
@commands.has_permissions(administrator=True)
async def ajouter_joueur(ctx, membre: discord.Member):
    """Ajoute simplement un nouveau joueur à la fin du classement (Ex: !add @Alexis)"""
    global classement_top
    if membre.id not in classement_top:
        classement_top.append(membre.id)
    await ctx.send(f"✅ {membre.mention} a été ajouté à la fin du classement.", delete_after=5)
    await ctx.message.delete()
    await rafraichir_partout(ctx.guild)

@bot.event
async def on_ready(): print(f"Bot connecté : {bot.user.name}")

keep_alive()
bot.run(os.environ.get("DISCORD_TOKEN"))
