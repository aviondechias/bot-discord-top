import os
import json
import asyncio
from threading import Thread

import discord
from discord.ext import commands
from flask import Flask


# ============================================================
# SERVEUR WEB KEEP-ALIVE
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot de classement actif !"


def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    thread = Thread(target=run_web_server, daemon=True)
    thread.start()


# ============================================================
# CONFIGURATION
# ============================================================

PREFIX = "!"
DATA_FILE = "classement.json"


intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents
)


# ============================================================
# STOCKAGE
# ============================================================

# Structure :
#
# {
#     "guild_id": {
#         "salon_top": 123456,
#         "message_top": 123456,
#         "classement": [111111, 222222]
#     }
# }

donnees = {}


def charger_donnees():
    global donnees

    if not os.path.exists(DATA_FILE):
        donnees = {}
        return

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as fichier:
            donnees = json.load(fichier)

    except (json.JSONDecodeError, OSError):
        print("⚠️ Impossible de charger classement.json.")
        donnees = {}


def sauvegarder_donnees():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as fichier:
            json.dump(
                donnees,
                fichier,
                ensure_ascii=False,
                indent=4
            )

    except OSError as erreur:
        print(f"❌ Erreur sauvegarde : {erreur}")


def obtenir_donnees_guild(guild_id):
    guild_id = str(guild_id)

    if guild_id not in donnees:
        donnees[guild_id] = {
            "salon_top": None,
            "message_top": None,
            "classement": []
        }

    return donnees[guild_id]


# ============================================================
# NOMS DES TEAMS
# ============================================================

def obtenir_nom_salon_team(numero):
    noms = {
        1: "𝐌𝐀𝐈𝐍 𝐑𝐎𝐒𝐓𝐄𝐑",
        2: "︱𝐓𝐄𝐀𝐌-𝟐",
        3: "︱𝐓𝐄𝐀𝐌-𝟑",
        4: "︱𝐓𝐄𝐀𝐌-𝟒",
        5: "︱𝐓𝐄𝐀𝐌-𝟓",
        6: "︱𝐓𝐄𝐀𝐌-𝟔",
        7: "︱𝐓𝐄𝐀𝐌-𝟕",
        8: "︱𝐓𝐄𝐀𝐌-𝟖",
    }

    return noms.get(
        numero,
        f"︱𝐓𝐄𝐀𝐌-{numero}"
    )


def obtenir_equipe(position):
    """
    Position :
    1-5  -> Team 1
    6-11 -> Team 2
    12-17 -> Team 3
    etc.
    """

    if position <= 5:
        return 1

    return 2 + (position - 6) // 6


def obtenir_nombre_teams(nombre_joueurs):
    if nombre_joueurs <= 0:
        return 1

    return obtenir_equipe(nombre_joueurs)


# ============================================================
# OUTILS DISCORD
# ============================================================

async def obtenir_ou_creer_role(guild, nom):
    role = discord.utils.get(
        guild.roles,
        name=nom
    )

    if role:
        return role

    try:
        return await guild.create_role(
            name=nom,
            reason="Gestion automatique du classement"
        )

    except discord.Forbidden:
        print(
            f"❌ Impossible de créer le rôle {nom} "
            f"dans {guild.name}."
        )

    except discord.HTTPException as erreur:
        print(
            f"❌ Erreur création rôle {nom}: {erreur}"
        )

    return None


async def obtenir_ou_creer_salon(guild, nom):
    salon = discord.utils.find(
        lambda channel:
            channel.name.casefold() == nom.casefold(),
        guild.text_channels
    )

    if salon:
        return salon

    try:
        return await guild.create_text_channel(
            name=nom,
            reason="Gestion automatique du classement"
        )

    except discord.Forbidden:
        print(
            f"❌ Impossible de créer le salon {nom} "
            f"dans {guild.name}."
        )

    except discord.HTTPException as erreur:
        print(
            f"❌ Erreur création salon {nom}: {erreur}"
        )

    return None


# ============================================================
# MISE À JOUR DES RÔLES
# ============================================================

async def mettre_a_jour_roles(guild, classement):
    """
    Retire les anciens rôles Team et donne
    le bon rôle à chaque joueur.
    """

    roles_team = [
        role
        for role in guild.roles
        if role.name.startswith("Team ")
    ]

    # Retirer les rôles Team aux membres qui ne sont plus
    # dans le classement.
    for member in guild.members:

        if member.id in classement:
            continue

        mauvais_roles = [
            role
            for role in member.roles
            if role in roles_team
        ]

        if not mauvais_roles:
            continue

        try:
            await member.remove_roles(
                *mauvais_roles,
                reason="Joueur retiré du classement"
            )

        except discord.Forbidden:
            print(
                f"⚠️ Impossible de modifier les rôles de "
                f"{member}."
            )

    # Donner les bons rôles aux joueurs du classement.
    for index, user_id in enumerate(classement):

        position = index + 1
        numero_team = obtenir_equipe(position)

        member = guild.get_member(user_id)

        if member is None:
            continue

        role_cible = discord.utils.get(
            guild.roles,
            name=f"Team {numero_team}"
        )

        if role_cible is None:
            role_cible = await obtenir_ou_creer_role(
                guild,
                f"Team {numero_team}"
            )

        if role_cible is None:
            continue

        mauvais_roles = [
            role
            for role in member.roles
            if role in roles_team
            and role != role_cible
        ]

        if mauvais_roles:
            try:
                await member.remove_roles(
                    *mauvais_roles,
                    reason="Changement de Team"
                )

            except discord.Forbidden:
                pass

        if role_cible not in member.roles:
            try:
                await member.add_roles(
                    role_cible,
                    reason="Classement automatique"
                )

            except discord.Forbidden:
                pass


# ============================================================
# CRÉATION DES TEAMS
# ============================================================

async def preparer_teams(guild, nombre_teams):
    for numero in range(1, nombre_teams + 1):

        await obtenir_ou_creer_role(
            guild,
            f"Team {numero}"
        )

        await obtenir_ou_creer_salon(
            guild,
            obtenir_nom_salon_team(numero)
        )


# ============================================================
# MISE À JOUR DU MESSAGE PRINCIPAL
# ============================================================

async def mettre_a_jour_message_top(guild, classement):
    config = obtenir_donnees_guild(guild.id)

    salon_id = config.get("salon_top")

    if not salon_id:
        return

    salon = guild.get_channel(salon_id)

    if salon is None:
        print(
            f"⚠️ Salon principal introuvable dans {guild.name}."
        )
        return

    texte = "🏆 **CLASSEMENT GÉNÉRAL COMPLET** 🏆\n\n"

    if not classement:
        texte += "Aucun joueur dans le top pour le moment."

    else:
        lignes = []

        for index, user_id in enumerate(classement):
            lignes.append(
                f"**Top {index + 1} :** <@{user_id}>"
            )

        texte += "\n".join(lignes)

    message_id = config.get("message_top")

    message = None

    if message_id:
        try:
            message = await salon.fetch_message(
                message_id
            )

        except discord.NotFound:
            message = None

        except discord.Forbidden:
            print(
                "❌ Le bot n'a pas accès au message principal."
            )
            return

        except discord.HTTPException:
            message = None

    try:

        if message:
            await message.edit(
                content=texte,
                view=VueControleTop()
            )

        else:
            message = await salon.send(
                content=texte,
                view=VueControleTop()
            )

            config["message_top"] = message.id
            sauvegarder_donnees()

    except discord.Forbidden:
        print(
            "❌ Le bot ne peut pas envoyer/modifier "
            "le message du classement."
        )

    except discord.HTTPException as erreur:
        print(
            f"❌ Erreur message principal : {erreur}"
        )


# ============================================================
# MISE À JOUR DES SALONS TEAMS
# ============================================================

async def mettre_a_jour_salons_teams(guild, classement):
    nombre_teams = obtenir_nombre_teams(
        len(classement)
    )

    for numero_team in range(1, nombre_teams + 1):

        nom = obtenir_nom_salon_team(numero_team)

        salon = discord.utils.find(
            lambda channel:
                channel.name.casefold() == nom.casefold(),
            guild.text_channels
        )

        if salon is None:
            continue

        # Nettoyage des anciens messages du bot.
        try:
            await salon.purge(
                limit=100,
                check=lambda message:
                    message.author == bot.user
            )

        except discord.Forbidden:
            print(
                f"⚠️ Impossible de nettoyer #{salon.name}."
            )

        except discord.HTTPException:
            pass

        joueurs_team = []

        for index, user_id in enumerate(classement):

            position = index + 1

            if obtenir_equipe(position) == numero_team:
                joueurs_team.append(
                    f"**Top {position} :** <@{user_id}>"
                )

        if joueurs_team:
            texte = (
                f"👥 **Membres - Team {numero_team}**\n\n"
                + "\n".join(joueurs_team)
            )

        else:
            texte = (
                f"**Aucun joueur assigné à la "
                f"Team {numero_team} actuellement.**"
            )

        try:
            await salon.send(texte)

        except discord.Forbidden:
            print(
                f"⚠️ Impossible d'écrire dans #{salon.name}."
            )

        except discord.HTTPException:
            pass


# ============================================================
# RAFRAÎCHISSEMENT COMPLET
# ============================================================

async def rafraichir_partout(guild):
    if guild is None:
        return

    config = obtenir_donnees_guild(guild.id)

    classement = config["classement"]

    nombre_teams = obtenir_nombre_teams(
        len(classement)
    )

    await preparer_teams(
        guild,
        nombre_teams
    )

    await mettre_a_jour_roles(
        guild,
        classement
    )

    await mettre_a_jour_message_top(
        guild,
        classement
    )

    await mettre_a_jour_salons_teams(
        guild,
        classement
    )

    sauvegarder_donnees()


# ============================================================
# MODAL : DÉPLACER
# ============================================================

class FenetreDeplacement(discord.ui.Modal, title="Changer la place"):

    pos_depart = discord.ui.TextInput(
        label="Position actuelle",
        placeholder="Ex : 5",
        required=True,
        max_length=5
    )

    pos_arrivee = discord.ui.TextInput(
        label="Nouvelle position",
        placeholder="Ex : 2",
        required=True,
        max_length=5
    )

    async def on_submit(self, interaction):
        config = obtenir_donnees_guild(
            interaction.guild.id
        )

        classement = config["classement"]

        try:
            depart = int(self.pos_depart.value) - 1
            arrivee = int(self.pos_arrivee.value) - 1

        except ValueError:
            await interaction.response.send_message(
                "❌ Les positions doivent être des nombres.",
                ephemeral=True
            )
            return

        if not (
            0 <= depart < len(classement)
            and 0 <= arrivee < len(classement)
        ):
            await interaction.response.send_message(
                "❌ Une des positions est invalide.",
                ephemeral=True
            )
            return

        joueur = classement.pop(depart)
        classement.insert(arrivee, joueur)

        sauvegarder_donnees()

        await interaction.response.send_message(
            "✅ Joueur déplacé avec succès !",
            ephemeral=True
        )

        await rafraichir_partout(
            interaction.guild
        )


# ============================================================
# MODAL : ÉCHANGER
# ============================================================

class FenetreEchange(discord.ui.Modal, title="Échanger 2 places"):

    pos1 = discord.ui.TextInput(
        label="Position du premier joueur",
        placeholder="Ex : 2",
        required=True,
        max_length=5
    )

    pos2 = discord.ui.TextInput(
        label="Position du deuxième joueur",
        placeholder="Ex : 5",
        required=True,
        max_length=5
    )

    async def on_submit(self, interaction):
        config = obtenir_donnees_guild(
            interaction.guild.id
        )

        classement = config["classement"]

        try:
            position1 = int(self.pos1.value) - 1
            position2 = int(self.pos2.value) - 1

        except ValueError:
            await interaction.response.send_message(
                "❌ Les positions doivent être des nombres.",
                ephemeral=True
            )
            return

        if not (
            0 <= position1 < len(classement)
            and 0 <= position2 < len(classement)
        ):
            await interaction.response.send_message(
                "❌ Une des positions est invalide.",
                ephemeral=True
            )
            return

        classement[position1], classement[position2] = (
            classement[position2],
            classement[position1]
        )

        sauvegarder_donnees()

        await interaction.response.send_message(
            "✅ Échange effectué avec succès !",
            ephemeral=True
        )

        await rafraichir_partout(
            interaction.guild
        )


# ============================================================
# MODAL : SUPPRIMER
# ============================================================

class FenetreSuppression(
    discord.ui.Modal,
    title="Retirer un joueur"
):

    position = discord.ui.TextInput(
        label="Position du joueur",
        placeholder="Ex : 3",
        required=True,
        max_length=5
    )

    async def on_submit(self, interaction):
        config = obtenir_donnees_guild(
            interaction.guild.id
        )

        classement = config["classement"]

        try:
            position = int(self.position.value) - 1

        except ValueError:
            await interaction.response.send_message(
                "❌ La position doit être un nombre.",
                ephemeral=True
            )
            return

        if not 0 <= position < len(classement):
            await interaction.response.send_message(
                "❌ Position invalide.",
                ephemeral=True
            )
            return

        classement.pop(position)

        sauvegarder_donnees()

        await interaction.response.send_message(
            "✅ Joueur retiré du classement !",
            ephemeral=True
        )

        await rafraichir_partout(
            interaction.guild
        )


# ============================================================
# VUE DES BOUTONS
# ============================================================

class VueControleTop(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Changer de place",
        style=discord.ButtonStyle.primary,
        custom_id="classement_deplacer"
    )
    async def bouton_deplacer(
        self,
        interaction,
        button
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Tu dois être administrateur.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            FenetreDeplacement()
        )

    @discord.ui.button(
        label="Échanger 2 places",
        style=discord.ButtonStyle.secondary,
        custom_id="classement_echanger"
    )
    async def bouton_echanger(
        self,
        interaction,
        button
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Tu dois être administrateur.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            FenetreEchange()
        )

    @discord.ui.button(
        label="Retirer du Top",
        style=discord.ButtonStyle.danger,
        custom_id="classement_supprimer"
    )
    async def bouton_supprimer(
        self,
        interaction,
        button
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Tu dois être administrateur.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            FenetreSuppression()
        )


# ============================================================
# VÉRIFICATION ADMIN
# ============================================================

def est_admin(ctx):
    return (
        ctx.guild is not None
        and ctx.author.guild_permissions.administrator
    )


# ============================================================
# !SETUP
# ============================================================

@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def initialiser_salon_top(ctx):

    config = obtenir_donnees_guild(
        ctx.guild.id
    )

    config["salon_top"] = ctx.channel.id
    config["message_top"] = None

    sauvegarder_donnees()

    try:
        await ctx.message.delete()

    except discord.HTTPException:
        pass

    await rafraichir_partout(
        ctx.guild
    )


# ============================================================
# !ADD
# ============================================================

@bot.command(name="add")
@commands.has_permissions(administrator=True)
async def ajouter_joueur(ctx, membre: discord.Member):

    config = obtenir_donnees_guild(
        ctx.guild.id
    )

    classement = config["classement"]

    if membre.id in classement:

        await ctx.send(
            f"⚠️ {membre.mention} est déjà dans le classement.",
            delete_after=5
        )

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        return

    classement.append(membre.id)

    sauvegarder_donnees()

    await ctx.send(
        f"✅ {membre.mention} ajouté en position "
        f"**{len(classement)}**.",
        delete_after=4
    )

    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    await rafraichir_partout(
        ctx.guild
    )


# ============================================================
# !ADDMANY
# ============================================================

@bot.command(name="addmany")
@commands.has_permissions(administrator=True)
async def ajouter_plusieurs_joueurs(ctx, *membres: discord.Member):

    if not membres:
        await ctx.send(
            "❌ Mentionne au moins un joueur.\n\n"
            "Exemple :\n"
            "`!addmany @Joueur1 @Joueur2 @Joueur3`",
            delete_after=7
        )
        return

    config = obtenir_donnees_guild(
        ctx.guild.id
    )

    classement = config["classement"]

    ajoutes = []
    deja_presents = []

    for membre in membres:

        if membre.id in classement:
            if membre not in deja_presents:
                deja_presents.append(membre)

            continue

        classement.append(membre.id)
        ajoutes.append(membre)

    sauvegarder_donnees()

    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    messages = []

    if ajoutes:
        mentions = " ".join(
            membre.mention
            for membre in ajoutes
        )

        messages.append(
            f"✅ **{len(ajoutes)} joueur(s) ajouté(s) :**\n"
            f"{mentions}"
        )

    if deja_presents:
        mentions = " ".join(
            membre.mention
            for membre in deja_presents
        )

        messages.append(
            f"⚠️ **Déjà présent(s) :**\n"
            f"{mentions}"
        )

    if messages:
        await ctx.send(
            "\n\n".join(messages),
            delete_after=7
        )

    await rafraichir_partout(
        ctx.guild
    )


# ============================================================
# !REMOVE
# ============================================================

@bot.command(name="remove")
@commands.has_permissions(administrator=True)
async def supprimer_joueur(ctx, membre: discord.Member):

    config = obtenir_donnees_guild(
        ctx.guild.id
    )

    classement = config["classement"]

    if membre.id not in classement:

        await ctx.send(
            f"⚠️ {membre.mention} n'est pas dans le classement.",
            delete_after=5
        )
        return

    classement.remove(membre.id)

    sauvegarder_donnees()

    await ctx.send(
        f"✅ {membre.mention} a été retiré du classement.",
        delete_after=4
    )

    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    await rafraichir_partout(
        ctx.guild
    )


# ============================================================
# GESTION DES ERREURS DES COMMANDES
# ============================================================

@initialiser_salon_top.error
@ajouter_joueur.error
@ajouter_plusieurs_joueurs.error
@supprimer_joueur.error
async def erreur_commandes(ctx, error):

    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            "❌ Tu dois être administrateur.",
            delete_after=5
        )
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            "❌ Il manque un joueur ou un argument.",
            delete_after=5
        )
        return

    if isinstance(error, commands.MemberNotFound):
        await ctx.send(
            "❌ Un des joueurs indiqués est introuvable.",
            delete_after=5
        )
        return

    print(
        f"❌ Erreur commande {ctx.command}: {error}"
    )


# ============================================================
# ÉVÉNEMENT READY
# ============================================================

@bot.event
async def on_ready():

    print(
        f"✅ Bot connecté : {bot.user} "
        f"(ID : {bot.user.id})"
    )

    # Rend les boutons persistants après redémarrage.
    if not getattr(bot, "_vue_ajoutee", False):

        bot.add_view(
            VueControleTop()
        )

        bot._vue_ajoutee = True

    print(
        f"🌐 Connecté à {len(bot.guilds)} serveur(s)."
    )


# ============================================================
# CHARGEMENT DES DONNÉES
# ============================================================

charger_donnees()


# ============================================================
# LANCEMENT
# ============================================================

keep_alive()

token = os.environ.get("DISCORD_TOKEN")

if not token:
    raise RuntimeError(
        "❌ La variable d'environnement "
        "DISCORD_TOKEN est introuvable."
    )

bot.run(token)
