import discord
from discord.ext import commands
import asyncio

# Configuration des permissions du bot
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Liste globale en mémoire pour stocker les IDs des joueurs dans l'ordre du TOP
# Exemple : [ID_Joueur_1, ID_Joueur_2, ID_Joueur_3...]
classement_top = []

def obtenir_equipe_et_salon(position):
    """Calcule le numéro de la team selon la position exacte dans le classement (1-indexed)."""
    if position <= 5:
        return 1
    else:
        # Team 1 = positions 1 à 5 (5 places)
        # À partir de la position 6, on avance par tranches de 6 places
        return 2 + (position - 6) // 6

async def rafraichir_messages_et_roles(guild):
    """Met à jour l'intégralité des rôles des membres et des messages dans les salons."""
    # 1. Calculer la structure actuelle des équipes requises
    total_joueurs = len(classement_top)
    max_team_necessaire = obtenir_equipe_et_salon(total_joueurs) if total_joueurs > 0 else 1

    # 2. Création automatique des rôles et salons manquants au fil du temps
    for num_team in range(1, max_team_necessaire + 1):
        nom_role = f"Team {num_team}"
        nom_salon = f"team-{num_team}"

        # Vérifier/Créer le rôle
        role = discord.utils.get(guild.roles, name=nom_role)
        if not role:
            role = await guild.create_role(name=nom_role, reason="Création auto par le système de Top")

        # Vérifier/Créer le salon textuel public
        salon = discord.utils.get(guild.channels, name=nom_salon)
        if not salon:
            await guild.create_text_channel(name=nom_salon, reason="Création auto par le système de Top")

    # 3. Répartition et mise à jour des rôles pour chaque joueur du classement
    for index, user_id in enumerate(classement_top):
        position = index + 1
        num_team_actuelle = obtenir_equipe_et_salon(position)
        
        member = guild.get_member(user_id)
        if member:
            # Identifier le rôle que le joueur DOIT avoir
            role_cible = discord.utils.get(guild.roles, name=f"Team {num_team_actuelle}")
            
            # Lister et retirer tous les AUTRES rôles de Team qu'il possède déjà
            roles_a_retirer = [r for r in member.roles if r.name.startswith("Team ") and r != role_cible]
            if roles_a_retirer:
                await member.remove_roles(*roles_a_retirer)
                
            # Lui attribuer son rôle unique s'il ne l'a pas
            if role_cible and role_cible not in member.roles:
                await member.add_roles(role_cible)

    # 4. Nettoyage et réaffichage des messages dans les salons de chaque Team
    for num_team in range(1, max_team_necessaire + 1):
        nom_salon = f"team-{num_team}"
        salon = discord.utils.get(guild.channels, name=nom_salon)
        
        if salon:
            # Supprimer l'ancien historique de messages pour éviter les doublons
            try:
                await salon.purge(limit=100)
            except Exception:
                pass # Évite de bloquer si le salon vient d'être créé et est vide

            # Filtrer les joueurs appartenant à cette Team précise
            lignes_joueurs = []
            for index, user_id in enumerate(classement_top):
                pos = index + 1
                if obtenir_equipe_et_salon(pos) == num_team:
                    lignes_joueurs.append(f"**Top {pos}** : <@{user_id}>")

            # Envoyer le nouveau message propre mis à jour
            if lignes_joueurs:
                texte_message = f"🏆 **Classement Actuel - Team {num_team}** 🏆\n\n" + "\n".join(lignes_joueurs)
                await salon.send(texte_message)
            else:
                await salon.send(f"Cette équipe (*Team {num_team}*) n'a pas encore de joueurs assignés.")

@bot.command(name="add")
@commands.has_permissions(administrator=True)
async def ajouter_joueur_top(ctx, membre: discord.Member, position: int):
    """Commande pour ajouter un joueur à une position précise (Ex: !add @Alexis 3)"""
    global classement_top
    
    # Ajustement de l'index (la position 1 correspond à l'index 0 en Python)
    index_cible = position - 1

    # Sécurité si la position demandée est trop éloignée
    if index_cible < 0:
        await ctx.send("❌ La position doit être supérieure ou égale à 1.")
        return
    if index_cible > len(classement_top):
        index_cible = len(classement_top) # L'ajoute simplement à la fin si l'index dépasse

    # Si le joueur est déjà présent ailleurs dans le classement, on le retire d'abord pour éviter les doublons
    if membre.id in classement_top:
        classement_top.remove(membre.id)

    # Insertion à la position souhaitée -> Décale automatiquement tous les index suivants vers le bas
    classement_top.insert(index_cible, membre.id)
    
    await ctx.send(f"✅ {membre.mention} a été inséré à la position **Top {index_cible + 1}**. Calcul du décalage en cours...")
    
    # Lancement de la mise à jour globale sur Discord
    await rafraichir_messages_et_roles(ctx.guild)
    await ctx.send("🔄 Tous les salons, rôles et décalages ont été mis à jour avec succès !")

@bot.event
async def on_ready():
    print(f"Le bot {bot.user.name} est en ligne et prêt à gérer le classement !")

# Remplacez VOTRE_TOKEN_ICI par le token copié à l'étape 1
bot.run("MTUzODU1MTI5Nzk4NzMyMTk1OQ.GyDP9S.6QxjeNCcCguCDkuXktoeUzL4OywMwrf9uuoHGk")
