import discord
from discord.ext import commands
import asyncio
from flask import Flask
from threading import Thread
import os

# --- SERVEUR WEB KEEP-ALIVE ---
app = Flask('')

@app.route('/')
def home():
    return "Bot de classement actif !"

def run_web_server():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    Thread(target=run_web_server).start()

# --- CONFIGURATION BOT ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Stockage des données en mémoire
classement_top = []
id_message_principal = None
id_salon_principal = None

def obtenir_nom_salon_team(num_team):
    """Retourne le nom stylisé du salon Discord pour chaque équipe."""
    noms_speciaux = {
        1: "🏅𝐌𝐀𝐈𝐍 𝐑𝐎𝐒𝐓𝐄𝐑🏅",
        2: "🥈︱𝐓𝐄𝐀𝐌-𝟐🥈",
        3: "🥉︱𝐓𝐄𝐀𝐌-𝟑🥉",
        4: "🎖︱𝐓𝐄𝐀𝐌-𝟒🎖",
        5: "🏆︱𝐓𝐄𝐀𝐌-𝟓🏆",
        6: "🎗︱𝐓𝐄𝐀𝐌-𝟔🎗",
        7: "🎟︱𝐓𝐄𝐀𝐌-𝟕🎟",  # Émoji ✨ nettoyé du caractère invisible ici !
        8: "🎫︱𝐓𝐄𝐀𝐌-𝟖🎫"
    }
    return noms_speciaux.get(num_team, f"💫︱𝐓𝐄𝐀𝐌-{num_team}💫")

def obtenir_nom_role_team(num_team):
    """Retourne le nom exact du rôle pour chaque équipe (Main Roster pour la team 1)."""
    if num_team == 1:
        return "Main Roster"
    return f"Team {num_team}"

def obtenir_equipe_et_salon(position):
    """Détermine le numéro d'équipe en fonction du classement du joueur."""
    if position <= 5: 
        return 1
    return 2 + (position - 6) // 6

def normaliser_nom_salon(nom):
    """Nettoie en profondeur le nom du salon pour éviter les erreurs d'émojis et de tirets Discord."""
    # En plus des tirets et espaces, on retire le sélecteur de variante invisible (\ufe0f) que Discord supprime
    return nom.lower().replace("-", "").replace(" ", "").replace("\ufe0f", "")

async def rafraichir_partout(guild):
    global id_message_principal, id_salon_principal
    if not id_salon_principal: return

    total_joueurs = len(classement_top)
    max_team = obtenir_equipe_et_salon(total_joueurs) if total_joueurs > 0 else 1

    # 1. Nettoyage des rôles sur les membres hors classement
    for member in guild.members:
        if member.id not in classement_top:
            roles_mauvais = [r for r in member.roles if r.name.startswith("Team ") or r.name == "Main Roster"]
            if roles_mauvais: 
                try: await member.remove_roles(*roles_mauvais)
                except: pass

    # 2. Création automatique des rôles et salons manquants
    for num_team in range(1, max_team + 1):
        nom_role = obtenir_nom_role_team(num_team)
        nom_salon_stylise = obtenir_nom_salon_team(num_team)

        if not discord.utils.get(guild.roles, name=nom_role):
            try: await guild.create_role(name=nom_role)
            except: pass
            
        salon_existe = any(normaliser_nom_salon(c.name) == normaliser_nom_salon(nom_salon_stylise) for c in guild.channels)
        if not salon_existe:
            try: await guild.create_text_channel(name=nom_salon_stylise)
            except: pass

    # 3. Mise à jour dynamique des rôles pour les joueurs du top
    for index, user_id in enumerate(classement_top):
        pos = index + 1
        team_cible = obtenir_equipe_et_salon(pos)
        
        try:
            member = await guild.fetch_member(user_id)
        except discord.NotFound:
            member = None

        if member:
            nom_role_cible = obtenir_nom_role_team(team_cible)
            role_bon = discord.utils.get(guild.roles, name=nom_role_cible)
            
            roles_mauvais = [r for r in member.roles if (r.name.startswith("Team ") or r.name == "Main Roster") and r != role_bon]
            if roles_mauvais: 
                try: await member.remove_roles(*roles_mauvais)
                except: pass
            if role_bon and role_bon not in member.roles: 
                try: await member.add_roles(role_bon)
                except: pass

    # 4. Actualisation du message de Classement Général complet
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

    # 5. Nettoyage et affichage actualisé dans les salons de Teams respectifs
    for num_team in range(1, max_team + 1):
        nom_salon_stylise = obtenir_nom_salon_team(num_team)
        salon_team = discord.utils.find(lambda c: normaliser_nom_salon(c.name) == normaliser_nom_salon(nom_salon_stylise), guild.channels)
        
        if salon_team:
            try: 
                await salon_team.purge(limit=50)
            except Exception as e:
                print(f"Impossible de purger le salon Team {num_team} : {e}")
            
            lignes = [f"**Top {i+1}** : <@{uid}>" for i, uid in enumerate(classement_top) if obtenir_equipe_et_salon(i+1) == num_team]
            titre_affichage = "MAIN ROSTER" if num_team == 1 else f"Team {num_team}"
            
            try:
                if lignes:
                    await salon_team.send(f"🏆 **Membres - {titre_affichage}** 🏆\n\n" + "\n".join(lignes))
                else:
                    await salon_team.send(f"Aucun joueur assigné au {titre_affichage} actuellement.")
            except Exception as e:
                print(f"Erreur d'envoi dans le salon Team {num_team} : {e}")

# --- INTERFACES DES FENÊTRES POP-UP (MODALS) ---
class FenetreDeplacement(discord.ui.Modal, title="Changer la place (Décaler)"):
    pos_depart = discord.ui.TextInput(label="Position actuelle du joueur", placeholder="Ex: 5")
    pos_arrivee = discord.ui.TextInput(label="Sa nouvelle position voulue", placeholder="Ex: 2")

    async def on_submit(self, interaction: discord.Interaction):
        global classement_top
        try:
            p_dep = int(self.pos_depart.value) - 1
            p_arr = int(self.pos_arrivee.value) - 1
            if p_dep < 0 or p_arr < 0 or p_dep >= len(classement_top) or p_arr >= len(classement_top):
                await interaction.response.send_message("❌ Positions invalides.", ephemeral=True)
                return
            joueur_id = classement_top.pop(p_dep)
            classement_top.insert(p_arr, joueur_id)
            await interaction.response.send_message("📈 Déplacement effectué !", ephemeral=True)
            await rafraichir_partout(interaction.guild)
        except ValueError:
            await interaction.response.send_message("❌ Veuillez entrer des nombres entiers.", ephemeral=True)

class FenetreEchange(discord.ui.Modal, title="Échanger 2 places (Permuter)"):
    pos1 = discord.ui.TextInput(label="Position du 1er joueur", placeholder="Ex: 2")
    pos2 = discord.ui.TextInput(label="Position du 2ème joueur", placeholder="Ex: 5")

    async def on_submit(self, interaction: discord.Interaction):
        global classement_top
        try:
            p1 = int(self.pos1.value) - 1
            p2 = int(self.pos2.value) - 1
            if p1 < 0 or p2 < 0 or p1 >= len(classement_top) or p2 >= len(classement_top):
                await interaction.response.send_message("❌ Positions invalides.", ephemeral=True)
                return
            classement_top[p1], classement_top[p2] = classement_top[p2], classement_top[p1]
            await interaction.response.send_message("🔄 Échange effectué !", ephemeral=True)
            await rafraichir_partout(interaction.guild)
        except ValueError:
            await interaction.response.send_message("❌ Veuillez entrer des nombres entiers.", ephemeral=True)

class FenetreSuppression(discord.ui.Modal, title="Retirer un joueur du Top"):
    pos_suppr = discord.ui.TextInput(label="Position du joueur à supprimer", placeholder="Ex: 3")

    async def on_submit(self, interaction: discord.Interaction):
        global classement_top
        try:
            p = int(self.pos_suppr.value) - 1
            if p < 0 or p >= len(classement_top):
                await interaction.response.send_message("❌ Position invalide.", ephemeral=True)
                return
            classement_top.pop(p)
            await interaction.response.send_message("❌ Joueur retiré avec succès !", ephemeral=True)
            await rafraichir_partout(interaction.guild)
        except ValueError:
            await interaction.response.send_message("❌ Veuillez entrer un nombre valide.", ephemeral=True)

# --- BLOC DE CONTROLE (BOUTONS) ---
class VueControleTop(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Changer de place 📈", style=discord.ButtonStyle.primary, custom_id="btn_deplace")
    async def bouton_deplace(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Tu dois être admin.", ephemeral=True)
            return
        await interaction.response.send_modal(FenetreDeplacement())

    @discord.ui.button(label="Échanger 2 places 🔄", style=discord.ButtonStyle.secondary, custom_id="btn_echange")
    async def bouton_echange(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Tu dois être admin.", ephemeral=True)
            return
        await interaction.response.send_modal(FenetreEchange())

    @discord.ui.button(label="Retirer du Top ❌", style=discord.ButtonStyle.danger, custom_id="btn_suppr")
    async def bouton_supprime(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Tu dois être admin.", ephemeral=True)
            return
        await interaction.response.send_modal(FenetreSuppression())

    @discord.ui.button(label="Liste des Commandes ❓", style=discord.ButtonStyle.success, custom_id="btn_help")
    async def bouton_aide(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🤖 Guide des commandes du Bot de Classement",
            description="Voici la liste des commandes disponibles pour gérer et consulter le classement.",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="🛠️ Commandes Administrateur",
            value=(
                "`!setup` : Initialise le système dans le salon actuel (affiche le classement général).\n"
                "`!add @membre` : Ajoute un joueur à la fin du classement.\n"
                "`!addmany @m1 @m2...` : Ajoute plusieurs joueurs en même temps.\n"
                "`!remove @membre` : Retire un joueur spécifique du classement."
            ),
            inline=False
        )
        embed.add_field(
            name="🎛️ Panneau de Contrôle (Boutons)",
            value=(
                "📈 **Changer de place** : Décaler un joueur vers une autre position.\n"
                "🔄 **Échanger 2 places** : Permuter les positions de deux joueurs.\n"
                "❌ **Retirer du Top** : Supprimer un joueur via son numéro de Top.\n"
                "❓ **Liste des Commandes** : Affiche ce guide (visible uniquement par vous)."
            ),
            inline=False
        )
        embed.set_footer(text="Note : Les boutons de modification et les commandes sont réservés aux administrateurs.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

# --- COMMANDES ADMIN DE BASE ---
@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def initialiser_salon_top(ctx):
    global id_salon_principal, id_message_principal
    id_salon_principal = ctx.channel.id
    id_message_principal = None
    await ctx.message.delete()
    await rafraichir_partout(ctx.guild)

@bot.command(name="add")
@commands.has_permissions(administrator=True)
async def ajouter_joueur(ctx, membre: discord.Member):
    global classement_top
    if membre.id not in classement_top:
        classement_top.append(membre.id)
    await ctx.send(f"✅ {membre.mention} ajouté en fin de liste.", delete_after=3)
    await ctx.message.delete()
    await rafraichir_partout(ctx.guild)

@bot.command(name="addmany")
@commands.has_permissions(administrator=True)
async def ajouter_plusieurs_joueurs(ctx, *membres: discord.Member):
    global classement_top
    if not membres:
        await ctx.send("❌ Veuillez mentionner au moins un joueur. Exemple : `!addmany @joueur1 @joueur2`", delete_after=5)
        await ctx.message.delete()
        return

    membres_ajoutes = []
    for membre in membres:
        if membre.id not in classement_top:
            classement_top.append(membre.id)
            membres_ajoutes.append(membre.mention)

    if membres_ajoutes:
        liste_mentions = ", ".join(membres_ajoutes)
        await ctx.send(f"✅ Joueurs ajoutés en fin de liste : {liste_mentions}", delete_after=5)
    else:
        await ctx.send("ℹ️ Tous les joueurs mentionnés sont déjà dans le classement.", delete_after=5)

    await ctx.message.delete()
    await rafraichir_partout(ctx.guild)

@bot.command(name="remove")
@commands.has_permissions(administrator=True)
async def supprimer_joueur_txt(ctx, membre: discord.Member):
    global classement_top
    if membre.id in classement_top:
        classement_top.remove(membre.id)
        await ctx.send(f"❌ {membre.mention} retiré.", delete_after=3)
        await ctx.message.delete()
        await rafraichir_partout(ctx.guild)
    else:
        await ctx.send("Ce joueur n'est pas dans le top.", delete_after=3)

@bot.event
async def on_ready():
    print(f"Bot en ligne : {bot.user.name}")

keep_alive()
bot.run(os.environ.get("DISCORD_TOKEN"))
 
