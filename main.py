import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import asyncio
import os
import json
import traceback


# ============================================================
# KEEP ALIVE / RENDER
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
# BOT
# ============================================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)


# ============================================================
# VARIABLES
# ============================================================

FICHIER_CONFIG = "config_serveurs.json"

config_serveurs = {}
classements_par_serveur = {}

id_messages_principaux = {}
id_salons_principaux = {}

verrous_rafraichissement = {}

vues_chargees = False


# ============================================================
# NOMS PAR DÉFAUT
# ============================================================

def nom_salon_par_defaut(numero):
    noms = {
        1: "🏅︱𝐌𝐀𝐈𝐍-𝐑𝐎𝐒𝐓𝐄𝐑🏅",
        2: "🥈︱𝐓𝐄𝐀𝐌-𝟐🥈",
        3: "🥉︱𝐓𝐄𝐀𝐌-𝟑🥉",
        4: "🎖︱𝐓𝐄𝐀𝐌-𝟒🎖",
        5: "🏆︱𝐓𝐄𝐀𝐌-𝟓🏆",
        6: "🎗︱𝐓𝐄𝐀𝐌-𝟔🎗",
        7: "✨︱𝐓𝐄𝐀𝐌-𝟕✨",
        8: "🎫︱𝐓𝐄𝐀𝐌-𝟖🎫",
    }

    return noms.get(numero, f"💫︱𝐓𝐄𝐀𝐌-{numero}💫")


def nom_role_par_defaut(numero):
    if numero == 1:
        return "Main Roster"

    return f"Team {numero}"


# ============================================================
# CONFIG PAR DÉFAUT
# ============================================================

def creer_config_par_defaut():
    teams = {}

    # On commence avec 3 teams.
    # Il n'y a AUCUNE limite à 3 dans le système.
    for numero in range(1, 4):
        teams[str(numero)] = {
            "nom_salon": nom_salon_par_defaut(numero),
            "nom_role": nom_role_par_defaut(numero),
            "max_joueurs": 5,
            "role_id": None,
            "channel_id": None,
            "message_id": None
        }

    return {
        "role_admin_id": 1529373902969770094,
        "taille_team": 5,

        "teams": teams,

        "motifs_tickets": [
            "Admin",
            "Test Team",
            "Tryout"
        ],

        "classement": [],

        "top_channel_id": None,
        "top_message_id": None
    }


# ============================================================
# NORMALISATION / MIGRATION ANCIENNE CONFIG
# ============================================================

def normaliser_config(config):
    """
    Convertit automatiquement l'ancienne structure :

        noms_salons
        noms_roles
        taille_team

    vers la nouvelle structure :

        teams = {
            "1": {
                "nom_salon": "...",
                "nom_role": "...",
                "max_joueurs": 5
            }
        }

    Cela permet de garder les anciennes données.
    """

    if not isinstance(config, dict):
        config = creer_config_par_defaut()

    # --------------------------------------------------------
    # Si l'ancienne config n'a pas encore "teams"
    # --------------------------------------------------------

    if not isinstance(config.get("teams"), dict):
        anciens_salons = config.get("noms_salons", {})
        anciens_roles = config.get("noms_roles", {})

        taille_generale = int(config.get("taille_team", 5))

        numeros = set()

        for cle in anciens_salons.keys():
            try:
                numeros.add(int(cle))
            except Exception:
                pass

        for cle in anciens_roles.keys():
            try:
                numeros.add(int(cle))
            except Exception:
                pass

        if not numeros:
            numeros = {1, 2, 3}

        numeros.update({1, 2, 3})

        teams = {}

        for numero in sorted(numeros):
            cle = str(numero)

            teams[cle] = {
                "nom_salon": anciens_salons.get(
                    cle,
                    nom_salon_par_defaut(numero)
                ),

                "nom_role": anciens_roles.get(
                    cle,
                    nom_role_par_defaut(numero)
                ),

                "max_joueurs": (
                    taille_generale
                    if numero == 1
                    else 5
                ),

                "role_id": None,
                "channel_id": None,
                "message_id": None
            }

        config["teams"] = teams

    # --------------------------------------------------------
    # Vérification des teams existantes
    # --------------------------------------------------------

    teams = config.setdefault("teams", {})

    for cle, team in list(teams.items()):

        if not isinstance(team, dict):
            teams[cle] = {
                "nom_salon": nom_salon_par_defaut(int(cle)),
                "nom_role": nom_role_par_defaut(int(cle)),
                "max_joueurs": 5,
                "role_id": None,
                "channel_id": None,
                "message_id": None
            }

            continue

        try:
            numero = int(cle)
        except Exception:
            continue

        team.setdefault(
            "nom_salon",
            nom_salon_par_defaut(numero)
        )

        team.setdefault(
            "nom_role",
            nom_role_par_defaut(numero)
        )

        team.setdefault("max_joueurs", 5)
        team.setdefault("role_id", None)
        team.setdefault("channel_id", None)
        team.setdefault("message_id", None)

        try:
            team["max_joueurs"] = max(
                1,
                int(team["max_joueurs"])
            )
        except Exception:
            team["max_joueurs"] = 5

    config.setdefault("motifs_tickets", [
        "Admin",
        "Test Team",
        "Tryout"
    ])

    config.setdefault("classement", [])

    config.setdefault("top_channel_id", None)
    config.setdefault("top_message_id", None)

    # Ancien champ gardé pour compatibilité.
    config["taille_team"] = int(
        config.get("taille_team", 5)
    )

    return config


# ============================================================
# CHARGEMENT JSON
# ============================================================

def charger_configs():
    global config_serveurs

    if not os.path.exists(FICHIER_CONFIG):
        config_serveurs = {}
        sauvegarder_configs()
        return

    try:
        with open(
            FICHIER_CONFIG,
            "r",
            encoding="utf-8"
        ) as fichier:

            donnees = json.load(fichier)

            if not isinstance(donnees, dict):
                donnees = {}

            config_serveurs = donnees

        # Normalisation
        modifie = False

        for guild_id in list(config_serveurs.keys()):
            ancienne = config_serveurs[guild_id]

            nouvelle = normaliser_config(ancienne)

            if nouvelle != ancienne:
                config_serveurs[guild_id] = nouvelle
                modifie = True

        if modifie:
            sauvegarder_configs()

    except Exception as erreur:
        print("❌ Impossible de charger le fichier JSON.")
        print(erreur)

        config_serveurs = {}


def sauvegarder_configs():
    try:
        temporaire = FICHIER_CONFIG + ".tmp"

        with open(
            temporaire,
            "w",
            encoding="utf-8"
        ) as fichier:

            json.dump(
                config_serveurs,
                fichier,
                indent=4,
                ensure_ascii=False
            )

        os.replace(
            temporaire,
            FICHIER_CONFIG
        )

    except Exception as erreur:
        print("❌ Erreur sauvegarde JSON :", erreur)


# ============================================================
# CONFIG SERVEUR
# ============================================================

def obtenir_config_serveur(guild_id):

    cle = str(guild_id)

    if cle not in config_serveurs:
        config_serveurs[cle] = creer_config_par_defaut()
        sauvegarder_configs()

    config_serveurs[cle] = normaliser_config(
        config_serveurs[cle]
    )

    return config_serveurs[cle]


def sauvegarder_config_serveur(guild_id):
    config = obtenir_config_serveur(guild_id)

    config_serveurs[str(guild_id)] = config

    sauvegarder_configs()


# ============================================================
# TEAMS
# ============================================================

def obtenir_teams(guild_id):

    config = obtenir_config_serveur(guild_id)

    teams = []

    for cle, team in config.get("teams", {}).items():

        try:
            numero = int(cle)
        except Exception:
            continue

        teams.append(
            (numero, team)
        )

    teams.sort(key=lambda x: x[0])

    return teams


def obtenir_team(guild_id, numero):

    config = obtenir_config_serveur(guild_id)

    return config["teams"].get(str(numero))


def obtenir_nom_role_team(guild_id, numero):

    team = obtenir_team(
        guild_id,
        numero
    )

    if team:
        return team.get(
            "nom_role",
            nom_role_par_defaut(numero)
        )

    return nom_role_par_defaut(numero)


def obtenir_nom_salon_team(guild_id, numero):

    team = obtenir_team(
        guild_id,
        numero
    )

    if team:
        return team.get(
            "nom_salon",
            nom_salon_par_defaut(numero)
        )

    return nom_salon_par_defaut(numero)


def obtenir_max_team(guild_id, numero):

    team = obtenir_team(
        guild_id,
        numero
    )

    if not team:
        return 5

    try:
        return max(
            1,
            int(team.get("max_joueurs", 5))
        )

    except Exception:
        return 5


# ============================================================
# CALCUL DE TEAM
# ============================================================

def obtenir_equipe_et_salon_dynamique(
    guild_id,
    position
):
    """
    Trouve la team correspondant à la position
    dans le classement.

    Exemple :

    Team 1 = 5
    Team 2 = 5
    Team 3 = 5

    position 1-5  -> Team 1
    position 6-10 -> Team 2
    position 11-15 -> Team 3

    Fonctionne avec 50, 100 ou davantage de teams.
    """

    if position <= 0:
        return None

    cumul = 0

    for numero, team in obtenir_teams(guild_id):

        try:
            maximum = max(
                1,
                int(team.get("max_joueurs", 5))
            )

        except Exception:
            maximum = 5

        cumul += maximum

        if position <= cumul:
            return numero

    # Toutes les teams sont pleines.
    return None


# ============================================================
# NORMALISATION NOM SALON
# ============================================================

def normaliser_nom_salon(nom):

    return (
        str(nom)
        .lower()
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
        .replace("\ufe0f", "")
    )


# ============================================================
# TROUVER / CRÉER LE ROLE
# ============================================================

async def obtenir_ou_creer_role(
    guild,
    numero,
    team
):

    nom_desire = team["nom_role"]

    role = None

    # Priorité à l'ID enregistré
    role_id = team.get("role_id")

    if role_id:
        try:
            role = guild.get_role(
                int(role_id)
            )
        except Exception:
            role = None

    # Recherche par nom
    if role is None:
        role = discord.utils.get(
            guild.roles,
            name=nom_desire
        )

    # Création
    if role is None:

        try:
            role = await guild.create_role(
                name=nom_desire,
                reason="Création automatique d'une équipe"
            )

        except discord.Forbidden:
            print(
                f"❌ Impossible de créer le rôle Team {numero}"
            )
            return None

        except discord.HTTPException as erreur:
            print(
                f"❌ Erreur création rôle Team {numero}:",
                erreur
            )
            return None

    # Renommage si nécessaire
    elif role.name != nom_desire:

        try:
            await role.edit(
                name=nom_desire,
                reason="Mise à jour configuration équipe"
            )

        except discord.Forbidden:
            print(
                f"⚠️ Impossible de renommer le rôle Team {numero}"
            )

        except discord.HTTPException:
            pass

    team["role_id"] = role.id

    return role


# ============================================================
# TROUVER / CRÉER LE SALON
# ============================================================

async def obtenir_ou_creer_salon(
    guild,
    numero,
    team
):

    nom_desire = team["nom_salon"]

    salon = None

    channel_id = team.get("channel_id")

    # Priorité à l'ID enregistré
    if channel_id:

        try:
            salon = guild.get_channel(
                int(channel_id)
            )
        except Exception:
            salon = None

    # Recherche par nom
    if salon is None:

        for channel in guild.text_channels:

            if (
                normaliser_nom_salon(channel.name)
                ==
                normaliser_nom_salon(nom_desire)
            ):
                salon = channel
                break

    # Création
    if salon is None:

        try:
            salon = await guild.create_text_channel(
                name=nom_desire,
                reason="Création automatique d'une équipe"
            )

        except discord.Forbidden:
            print(
                f"❌ Impossible de créer le salon Team {numero}"
            )
            return None

        except discord.HTTPException as erreur:
            print(
                f"❌ Erreur création salon Team {numero}:",
                erreur
            )
            return None

    # Renommage
    elif salon.name != nom_desire:

        try:
            await salon.edit(
                name=nom_desire,
                reason="Mise à jour configuration équipe"
            )

        except discord.Forbidden:
            print(
                f"⚠️ Impossible de renommer le salon Team {numero}"
            )

        except discord.HTTPException:
            pass

    team["channel_id"] = salon.id

    return salon


# ============================================================
# EMBED TEAM
# ============================================================

def creer_embed_team(
    guild_id,
    numero
):

    team = obtenir_team(
        guild_id,
        numero
    )

    embed = discord.Embed(
        title=f"🏆 TEAM {numero}",
        description=(
            f"**Salon :** {team['nom_salon']}\n"
            f"**Rôle :** {team['nom_role']}\n"
            f"**Maximum :** {team['max_joueurs']} joueurs"
        ),
        color=discord.Color.blurple()
    )

    return embed


# ============================================================
# REFRESH SÉCURISÉ
# ============================================================

async def rafraichir_partout(guild):

    guild_id = guild.id

    if guild_id not in verrous_rafraichissement:
        verrous_rafraichissement[guild_id] = asyncio.Lock()

    verrou = verrous_rafraichissement[guild_id]

    async with verrou:

        try:
            await _rafraichir_partout(guild)

        except Exception as erreur:

            print(
                f"❌ Erreur refresh serveur {guild.name}:"
            )

            traceback.print_exc()


async def _rafraichir_partout(guild):

    guild_id = guild.id

    config = obtenir_config_serveur(
        guild_id
    )

    roster = classements_par_serveur.setdefault(
        guild_id,
        config.get("classement", [])
    )

    # Synchronisation JSON
    config["classement"] = roster

    teams = obtenir_teams(guild_id)

    if not teams:
        return

    # ========================================================
    # CRÉER / METTRE À JOUR ROLES + SALONS
    # ========================================================

    roles_teams = {}
    salons_teams = {}

    for numero, team in teams:

        role = await obtenir_ou_creer_role(
            guild,
            numero,
            team
        )

        salon = await obtenir_ou_creer_salon(
            guild,
            numero,
            team
        )

        if role:
            roles_teams[numero] = role

        if salon:
            salons_teams[numero] = salon

    # ========================================================
    # DÉTERMINER LES MEMBRES DU ROSTER
    # ========================================================

    membres_roster = {}

    for position, user_id in enumerate(
        roster,
        start=1
    ):

        team_numero = (
            obtenir_equipe_et_salon_dynamique(
                guild_id,
                position
            )
        )

        if team_numero is None:
            continue

        membre = guild.get_member(
            int(user_id)
        )

        if membre is None:

            try:
                membre = await guild.fetch_member(
                    int(user_id)
                )
            except Exception:
                membre = None

        if membre:
            membres_roster[
                membre.id
            ] = team_numero

    # ========================================================
    # NETTOYAGE DES ANCIENS ROLES
    # ========================================================

    roster_ids = set(
        membres_roster.keys()
    )

    for numero, role in roles_teams.items():

        for membre in list(role.members):

            if membre.id not in roster_ids:

                try:
                    await membre.remove_roles(
                        role,
                        reason="Retrait automatique du roster"
                    )

                except discord.Forbidden:
                    pass

                except discord.HTTPException:
                    pass

    # ========================================================
    # ATTRIBUTION DES BONS ROLES
    # ========================================================

    tous_les_roles = list(
        roles_teams.values()
    )

    for membre_id, team_numero in membres_roster.items():

        membre = guild.get_member(
            membre_id
        )

        if membre is None:
            continue

        role_cible = roles_teams.get(
            team_numero
        )

        if role_cible is None:
            continue

        # Retirer les mauvais rôles
        mauvais_roles = [
            role
            for role in tous_les_roles
            if role != role_cible
            and role in membre.roles
        ]

        if mauvais_roles:

            try:
                await membre.remove_roles(
                    *mauvais_roles,
                    reason="Réorganisation automatique des teams"
                )

            except discord.Forbidden:
                pass

            except discord.HTTPException:
                pass

        # Ajouter le bon rôle
        if role_cible not in membre.roles:

            try:
                await membre.add_roles(
                    role_cible,
                    reason="Attribution automatique de team"
                )

            except discord.Forbidden:
                pass

            except discord.HTTPException:
                pass

    # ========================================================
    # SAUVEGARDE CONFIG
    # ========================================================

    config["classement"] = roster

    sauvegarder_config_serveur(
        guild_id
    )

    # ========================================================
    # MESSAGES DES TEAMS
    # ========================================================

    for numero, team in teams:

        salon = salons_teams.get(
            numero
        )

        if salon is None:
            continue

        lignes = []

        for position, user_id in enumerate(
            roster,
            start=1
        ):

            equipe = (
                obtenir_equipe_et_salon_dynamique(
                    guild_id,
                    position
                )
            )

            if equipe != numero:
                continue

            membre = guild.get_member(
                int(user_id)
            )

            if membre:

                lignes.append(
                    f"**{position}.** {membre.mention}"
                )

            else:

                lignes.append(
                    f"**{position}.** <@{user_id}>"
                )

        if not lignes:
            description = (
                "Aucun joueur dans cette team."
            )

        else:
            description = "\n".join(
                lignes
            )

        embed = discord.Embed(
            title=f"🏆 TEAM {numero}",
            description=description,
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text=(
                f"Maximum : "
                f"{team['max_joueurs']} joueurs"
            )
        )

        message = None

        message_id = team.get(
            "message_id"
        )

        # Essayer de récupérer l'ancien message
        if message_id:

            try:
                message = await salon.fetch_message(
                    int(message_id)
                )

            except discord.NotFound:
                message = None

            except discord.HTTPException:
                message = None

        # Modifier le message existant
        if message:

            try:
                await message.edit(
                    embed=embed
                )

            except discord.HTTPException:
                pass

        # Sinon créer UN nouveau message
        else:

            try:
                message = await salon.send(
                    embed=embed
                )

                team["message_id"] = message.id

            except discord.Forbidden:
                pass

            except discord.HTTPException:
                pass

    sauvegarder_config_serveur(
        guild_id
    )


# ============================================================
# REFRESH EN TÂCHE
# ============================================================

def lancer_refresh(guild):

    asyncio.create_task(
        rafraichir_partout(guild)
    )


# ============================================================
# MODAL : MODIFIER UNE TEAM
# ============================================================

class ModalModifierTeam(
    discord.ui.Modal,
    title="✏️ Modifier une Team"
):

    nom_salon = discord.ui.TextInput(
        label="Nom du salon",
        placeholder="Ex: 🏆︱𝐓𝐄𝐀𝐌-𝟕",
        max_length=100,
        required=True
    )

    nom_role = discord.ui.TextInput(
        label="Nom du rôle",
        placeholder="Ex: Team 7",
        max_length=100,
        required=True
    )

    max_joueurs = discord.ui.TextInput(
        label="Maximum de joueurs",
        placeholder="Ex: 5",
        max_length=4,
        required=True
    )

    def __init__(
        self,
        guild_id,
        numero
    ):

        super().__init__()

        self.guild_id = guild_id
        self.numero = numero

        team = obtenir_team(
            guild_id,
            numero
        )

        if team:

            self.nom_salon.default = (
                team.get("nom_salon", "")
            )

            self.nom_role.default = (
                team.get("nom_role", "")
            )

            self.max_joueurs.default = str(
                team.get("max_joueurs", 5)
            )

    async def on_submit(
        self,
        interaction
    ):

        try:
            maximum = int(
                self.max_joueurs.value.strip()
            )

            if maximum < 1:
                raise ValueError

            if maximum > 9999:
                raise ValueError

        except ValueError:

            await interaction.response.send_message(
                "❌ Le maximum doit être un nombre entre 1 et 9999.",
                ephemeral=True
            )

            return

        config = obtenir_config_serveur(
            self.guild_id
        )

        cle = str(
            self.numero
        )

        if cle not in config["teams"]:

            await interaction.response.send_message(
                "❌ Cette team n'existe plus.",
                ephemeral=True
            )

            return

        team = config["teams"][cle]

        team["nom_salon"] = (
            self.nom_salon.value.strip()
        )

        team["nom_role"] = (
            self.nom_role.value.strip()
        )

        team["max_joueurs"] = maximum

        sauvegarder_config_serveur(
            self.guild_id
        )

        await interaction.response.send_message(
            f"✅ **TEAM {self.numero}** a été modifiée.",
            ephemeral=True
        )

        guild = bot.get_guild(
            self.guild_id
        )

        if guild:
            lancer_refresh(guild)


# ============================================================
# MODAL : AJOUTER UNE TEAM
# ============================================================

class ModalAjouterTeam(
    discord.ui.Modal,
    title="➕ Ajouter une Team"
):

    nom_salon = discord.ui.TextInput(
        label="Nom du salon",
        placeholder="Ex: 🏆︱𝐓𝐄𝐀𝐌-𝟗",
        max_length=100,
        required=True
    )

    nom_role = discord.ui.TextInput(
        label="Nom du rôle",
        placeholder="Ex: Team 9",
        max_length=100,
        required=True
    )

    max_joueurs = discord.ui.TextInput(
        label="Maximum de joueurs",
        placeholder="Ex: 5",
        max_length=4,
        required=True
    )

    async def on_submit(
        self,
        interaction
    ):

        try:
            maximum = int(
                self.max_joueurs.value.strip()
            )

            if maximum < 1 or maximum > 9999:
                raise ValueError

        except ValueError:

            await interaction.response.send_message(
                "❌ Le maximum doit être un nombre entre 1 et 9999.",
                ephemeral=True
            )

            return

        config = obtenir_config_serveur(
            interaction.guild.id
        )

        teams = config["teams"]

        numeros = []

        for cle in teams.keys():

            try:
                numeros.append(
                    int(cle)
                )
            except Exception:
                pass

        # Prochaine team disponible
        nouveau_numero = (
            max(numeros, default=0) + 1
        )

        teams[str(nouveau_numero)] = {
            "nom_salon": self.nom_salon.value.strip(),
            "nom_role": self.nom_role.value.strip(),
            "max_joueurs": maximum,
            "role_id": None,
            "channel_id": None,
            "message_id": None
        }

        sauvegarder_config_serveur(
            interaction.guild.id
        )

        await interaction.response.send_message(
            (
                f"✅ **TEAM {nouveau_numero}** a été ajoutée !\n"
                f"👥 Maximum : **{maximum} joueurs**"
            ),
            ephemeral=True
        )

        lancer_refresh(
            interaction.guild
        )


# ============================================================
# MENU POUR UNE TEAM
# ============================================================

class MenuDeroulantTeam(
    discord.ui.Select
):

    def __init__(
        self,
        guild_id,
        numero,
        team,
        row
    ):

        self.guild_id = guild_id
        self.numero = numero

        nom_salon = team.get(
            "nom_salon",
            "Salon"
        )

        nom_role = team.get(
            "nom_role",
            "Rôle"
        )

        maximum = team.get(
            "max_joueurs",
            5
        )

        description = (
            f"Salon: {nom_salon} | "
            f"Rôle: {nom_role} | "
            f"Max: {maximum}"
        )

        # Discord limite la description à 100 caractères.
        description = description[:100]

        options = [
            discord.SelectOption(
                label=f"TEAM {numero}",
                description=description,
                emoji="✏️",
                value=str(numero)
            )
        ]

        super().__init__(
            placeholder=f"⚙️ Modifier TEAM {numero}",
            min_values=1,
            max_values=1,
            options=options,
            row=row
        )

    async def callback(
        self,
        interaction
    ):

        await interaction.response.send_modal(
            ModalModifierTeam(
                self.guild_id,
                self.numero
            )
        )


# ============================================================
# BOUTON AJOUTER TEAM
# ============================================================

class BoutonAjouterTeam(
    discord.ui.Button
):

    def __init__(self):

        super().__init__(
            label="Ajouter une team",
            emoji="➕",
            style=discord.ButtonStyle.success,
            row=3
        )

    async def callback(
        self,
        interaction
    ):

        await interaction.response.send_modal(
            ModalAjouterTeam()
        )


# ============================================================
# PAGINATION TEAM
# ============================================================

class BoutonPageTeam(
    discord.ui.Button
):

    def __init__(
        self,
        guild_id,
        page,
        direction
    ):

        self.guild_id = guild_id
        self.page = page
        self.direction = direction

        if direction == -1:

            label = "Précédent"
            emoji = "⬅️"

        else:

            label = "Suivant"
            emoji = "➡️"

        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            row=4
        )

    async def callback(
        self,
        interaction
    ):

        nouvelle_page = (
            self.page + self.direction
        )

        await interaction.response.edit_message(
            embed=creer_embed_personnalisation(
                self.guild_id,
                nouvelle_page
            ),
            view=VuePersonnalisationTeams(
                self.guild_id,
                nouvelle_page
            )
        )


# ============================================================
# EMBED PERSONNALISATION
# ============================================================

def creer_embed_personnalisation(
    guild_id,
    page
):

    teams = obtenir_teams(
        guild_id
    )

    par_page = 3

    total_pages = max(
        1,
        (len(teams) + par_page - 1)
        // par_page
    )

    page = max(
        0,
        min(page, total_pages - 1)
    )

    debut = page * par_page
    teams_page = teams[
        debut: debut + par_page
    ]

    embed = discord.Embed(
        title="✏️ Personnaliser les Équipes",
        description=(
            "Sélectionne une team pour modifier :\n"
            "• 🏷️ Le nom du salon\n"
            "• 🎭 Le nom du rôle\n"
            "• 👥 Le nombre maximum de joueurs\n\n"
            f"**Page {page + 1}/{total_pages}**"
        ),
        color=discord.Color.blurple()
    )

    for numero, team in teams_page:

        embed.add_field(
            name=f"🏆 TEAM {numero}",
            value=(
                f"**Salon :** {team['nom_salon']}\n"
                f"**Rôle :** {team['nom_role']}\n"
                f"**Maximum :** {team['max_joueurs']} joueurs"
            ),
            inline=False
        )

    return embed


# ============================================================
# VIEW PERSONNALISATION
# ============================================================

class VuePersonnalisationTeams(
    discord.ui.View
):

    def __init__(
        self,
        guild_id,
        page=0
    ):

        super().__init__(
            timeout=600
        )

        self.guild_id = guild_id
        self.page = page

        teams = obtenir_teams(
            guild_id
        )

        par_page = 3

        total_pages = max(
            1,
            (len(teams) + par_page - 1)
            // par_page
        )

        self.page = max(
            0,
            min(page, total_pages - 1)
        )

        debut = self.page * par_page

        teams_page = teams[
            debut: debut + par_page
        ]

        # Maximum 3 dropdowns
        for index, (numero, team) in enumerate(
            teams_page
        ):

            self.add_item(
                MenuDeroulantTeam(
                    guild_id,
                    numero,
                    team,
                    row=index
                )
            )

        # Ajouter team
        self.add_item(
            BoutonAjouterTeam()
        )

        # Navigation
        if self.page > 0:

            self.add_item(
                BoutonPageTeam(
                    guild_id,
                    self.page,
                    -1
                )
            )

        if self.page < total_pages - 1:

            self.add_item(
                BoutonPageTeam(
                    guild_id,
                    self.page,
                    1
                )
            )


# ============================================================
# MODAL TAILLE MAIN ROSTER
# ============================================================

class ModalTailleTeam(
    discord.ui.Modal,
    title="👥 Taille du Main Roster"
):

    taille = discord.ui.TextInput(
        label="Maximum de joueurs",
        placeholder="Ex: 5",
        max_length=4,
        required=True
    )

    async def on_submit(
        self,
        interaction
    ):

        try:
            valeur = int(
                self.taille.value.strip()
            )

            if valeur < 1 or valeur > 9999:
                raise ValueError

        except ValueError:

            await interaction.response.send_message(
                "❌ Entre un nombre entre 1 et 9999.",
                ephemeral=True
            )

            return

        config = obtenir_config_serveur(
            interaction.guild.id
        )

        config["taille_team"] = valeur

        # Le Main Roster = Team 1
        if "1" not in config["teams"]:

            config["teams"]["1"] = {
                "nom_salon": nom_salon_par_defaut(1),
                "nom_role": nom_role_par_defaut(1),
                "max_joueurs": valeur,
                "role_id": None,
                "channel_id": None,
                "message_id": None
            }

        else:

            config["teams"]["1"]["max_joueurs"] = valeur

        sauvegarder_config_serveur(
            interaction.guild.id
        )

        await interaction.response.send_message(
            f"✅ Le Main Roster peut maintenant contenir **{valeur} joueurs**.",
            ephemeral=True
        )

        lancer_refresh(
            interaction.guild
        )


# ============================================================
# MODAL ROLE ADMIN
# ============================================================

class ModalRoleAdmin(
    discord.ui.Modal,
    title="🛡️ Rôle Administrateur"
):

    role_id = discord.ui.TextInput(
        label="ID du rôle Discord",
        placeholder="Ex: 123456789012345678",
        max_length=25,
        required=True
    )

    async def on_submit(
        self,
        interaction
    ):

        try:
            role_id = int(
                self.role_id.value.strip()
            )

        except ValueError:

            await interaction.response.send_message(
                "❌ ID de rôle invalide.",
                ephemeral=True
            )

            return

        role = interaction.guild.get_role(
            role_id
        )

        if role is None:

            await interaction.response.send_message(
                "❌ Je ne trouve pas ce rôle sur ce serveur.",
                ephemeral=True
            )

            return

        config = obtenir_config_serveur(
            interaction.guild.id
        )

        config["role_admin_id"] = role_id

        sauvegarder_config_serveur(
            interaction.guild.id
        )

        await interaction.response.send_message(
            f"✅ Le rôle admin est maintenant {role.mention}.",
            ephemeral=True
        )


# ============================================================
# MODAL MOTIFS TICKETS
# ============================================================

class ModalMotifsTickets(
    discord.ui.Modal,
    title="🎫 Motifs des Tickets"
):

    motifs = discord.ui.TextInput(
        label="Motifs séparés par des virgules",
        placeholder="Admin, Test Team, Tryout",
        max_length=500,
        required=True
    )

    async def on_submit(
        self,
        interaction
    ):

        liste = [
            motif.strip()
            for motif in self.motifs.value.split(",")
            if motif.strip()
        ]

        if not liste:

            await interaction.response.send_message(
                "❌ Tu dois entrer au moins un motif.",
                ephemeral=True
            )

            return

        config = obtenir_config_serveur(
            interaction.guild.id
        )

        config["motifs_tickets"] = liste

        sauvegarder_config_serveur(
            interaction.guild.id
        )

        await interaction.response.send_message(
            "✅ Les motifs des tickets ont été mis à jour.",
            ephemeral=True
        )


# ============================================================
# MENU CONFIGURATION
# ============================================================

class MenuDeroulantConfiguration(
    discord.ui.Select
):

    def __init__(
        self,
        guild_id
    ):

        self.guild_id = guild_id

        options = [

            discord.SelectOption(
                label="Taille du Main Roster",
                description="Modifier le maximum de joueurs de la Team 1.",
                emoji="👥",
                value="taille"
            ),

            discord.SelectOption(
                label="Lier le Rôle Admin",
                description="Associer le rôle de modération.",
                emoji="🛡️",
                value="role_admin"
            ),

            discord.SelectOption(
                label="Personnaliser les Équipes",
                description="Modifier les teams, rôles, salons et capacités.",
                emoji="✏️",
                value="custom_team"
            ),

            discord.SelectOption(
                label="Raisons des Tickets",
                description="Modifier les choix des tickets.",
                emoji="🎫",
                value="motifs"
            )
        ]

        super().__init__(
            placeholder="⚙️ Sélectionnez l'élément à configurer...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(
        self,
        interaction
    ):

        choix = self.values[0]

        if choix == "taille":

            await interaction.response.send_modal(
                ModalTailleTeam()
            )

        elif choix == "role_admin":

            await interaction.response.send_modal(
                ModalRoleAdmin()
            )

        elif choix == "custom_team":

            await interaction.response.send_message(
                embed=creer_embed_personnalisation(
                    self.guild_id,
                    0
                ),
                view=VuePersonnalisationTeams(
                    self.guild_id,
                    0
                ),
                ephemeral=True
            )

        elif choix == "motifs":

            await interaction.response.send_modal(
                ModalMotifsTickets()
            )


# ============================================================
# VIEW CONFIG
# ============================================================

class VuePanelConfig(
    discord.ui.View
):

    def __init__(
        self,
        guild_id
    ):

        super().__init__(
            timeout=300
        )

        self.add_item(
            MenuDeroulantConfiguration(
                guild_id
            )
        )


# ============================================================
# SETUP
# ============================================================

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):

    guild_id = ctx.guild.id

    config = obtenir_config_serveur(
        guild_id
    )

    # Reset roster
    classements_par_serveur[
        guild_id
    ] = []

    config["classement"] = []

    # Trouver / créer salon principal
    salon_top = None

    if config.get("top_channel_id"):

        salon_top = ctx.guild.get_channel(
            int(config["top_channel_id"])
        )

    if salon_top is None:

        salon_top = discord.utils.get(
            ctx.guild.text_channels,
            name="main-roster"
        )

    if salon_top is None:

        try:
            salon_top = await ctx.guild.create_text_channel(
                "main-roster",
                reason="Configuration du bot"
            )

        except Exception as erreur:

            await ctx.send(
                f"❌ Impossible de créer le salon : `{erreur}`"
            )

            return

    config["top_channel_id"] = salon_top.id

    embed = discord.Embed(
        title="🏆 MAIN ROSTER",
        description=(
            "Le roster est actuellement vide.\n\n"
            "Utilise `!add @membre` pour ajouter un joueur."
        ),
        color=discord.Color.blurple()
    )

    try:
        message = await salon_top.send(
            embed=embed
        )

        config["top_message_id"] = message.id

        id_messages_principaux[
            guild_id
        ] = message.id

        id_salons_principaux[
            guild_id
        ] = salon_top.id

    except Exception as erreur:

        await ctx.send(
            f"❌ Impossible d'envoyer le panneau : `{erreur}`"
        )

        return

    sauvegarder_config_serveur(
        guild_id
    )

    await ctx.send(
        "✅ Le système de classement a été configuré !",
        delete_after=10
    )

    lancer_refresh(
        ctx.guild
    )


# ============================================================
# CONFIG
# ============================================================

@bot.command()
@commands.has_permissions(administrator=True)
async def config(ctx):

    await ctx.send(
        embed=discord.Embed(
            title="⚙️ Configuration",
            description=(
                "Sélectionne ce que tu veux modifier "
                "dans le menu ci-dessous."
            ),
            color=discord.Color.blurple()
        ),
        view=VuePanelConfig(
            ctx.guild.id
        ),
        delete_after=None
    )


# ============================================================
# ADD
# ============================================================

@bot.command()
@commands.has_permissions(administrator=True)
async def add(ctx, membre: discord.Member):

    guild_id = ctx.guild.id

    roster = classements_par_serveur.setdefault(
        guild_id,
        obtenir_config_serveur(
            guild_id
        ).get("classement", [])
    )

    if membre.id in roster:

        await ctx.send(
            "⚠️ Ce joueur est déjà dans le roster.",
            delete_after=5
        )

        return

    position = len(roster) + 1

    equipe = obtenir_equipe_et_salon_dynamique(
        guild_id,
        position
    )

    if equipe is None:

        await ctx.send(
            (
                "❌ Toutes les teams configurées sont pleines.\n"
                "Utilise `!config` → **Personnaliser les Équipes** "
                "→ **Ajouter une team**."
            ),
            delete_after=10
        )

        return

    roster.append(
        membre.id
    )

    config = obtenir_config_serveur(
        guild_id
    )

    config["classement"] = roster

    sauvegarder_config_serveur(
        guild_id
    )

    await ctx.send(
        (
            f"✅ {membre.mention} a été ajouté au roster.\n"
            f"🏆 Team attribuée : **Team {equipe}**"
        ),
        delete_after=8
    )

    lancer_refresh(
        ctx.guild
    )


# ============================================================
# REMOVE
# ============================================================

@bot.command()
@commands.has_permissions(administrator=True)
async def remove(ctx, membre: discord.Member):

    guild_id = ctx.guild.id

    roster = classements_par_serveur.setdefault(
        guild_id,
        []
    )

    if membre.id not in roster:

        await ctx.send(
            "⚠️ Ce joueur n'est pas dans le roster.",
            delete_after=5
        )

        return

    roster.remove(
        membre.id
    )

    config = obtenir_config_serveur(
        guild_id
    )

    config["classement"] = roster

    sauvegarder_config_serveur(
        guild_id
    )

    await ctx.send(
        f"✅ {membre.mention} a été retiré du roster.",
        delete_after=6
    )

    lancer_refresh(
        ctx.guild
    )


# ============================================================
# SWAP
# ============================================================

@bot.command()
@commands.has_permissions(administrator=True)
async def swap(
    ctx,
    membre1: discord.Member,
    membre2: discord.Member
):

    guild_id = ctx.guild.id

    roster = classements_par_serveur.setdefault(
        guild_id,
        []
    )

    if membre1.id not in roster or membre2.id not in roster:

        await ctx.send(
            "❌ Les deux joueurs doivent être dans le roster.",
            delete_after=6
        )

        return

    index1 = roster.index(
        membre1.id
    )

    index2 = roster.index(
        membre2.id
    )

    roster[index1], roster[index2] = (
        roster[index2],
        roster[index1]
    )

    config = obtenir_config_serveur(
        guild_id
    )

    config["classement"] = roster

    sauvegarder_config_serveur(
        guild_id
    )

    await ctx.send(
        (
            f"🔄 {membre1.mention} et "
            f"{membre2.mention} ont été échangés."
        ),
        delete_after=6
    )

    lancer_refresh(
        ctx.guild
    )


# ============================================================
# LIST
# ============================================================

@bot.command()
async def roster(ctx):

    guild_id = ctx.guild.id

    roster = classements_par_serveur.setdefault(
        guild_id,
        obtenir_config_serveur(
            guild_id
        ).get("classement", [])
    )

    if not roster:

        await ctx.send(
            "🏆 Le roster est actuellement vide.",
            delete_after=6
        )

        return

    lignes = []

    for position, user_id in enumerate(
        roster,
        start=1
    ):

        membre = ctx.guild.get_member(
            int(user_id)
        )

        if membre:

            lignes.append(
                f"**{position}.** {membre.mention}"
            )

        else:

            lignes.append(
                f"**{position}.** <@{user_id}>"
            )

    embed = discord.Embed(
        title="🏆 ROSTER",
        description="\n".join(lignes),
        color=discord.Color.blurple()
    )

    await ctx.send(
        embed=embed
    )


# ============================================================
# PING
# ============================================================

@bot.command()
async def ping(ctx):

    await ctx.send(
        f"🏓 Pong ! `{round(bot.latency * 1000)}ms`"
    )


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    global vues_chargees

    print(
        f"✅ Connecté en tant que {bot.user}"
    )

    print(
        f"🆔 ID : {bot.user.id}"
    )

    print(
        f"🌐 Serveurs : {len(bot.guilds)}"
    )

    # Charger les données des serveurs
    for guild in bot.guilds:

        config = obtenir_config_serveur(
            guild.id
        )

        classements_par_serveur[
            guild.id
        ] = list(
            config.get(
                "classement",
                []
            )
        )

    # Les Views dynamiques ne doivent pas être
    # enregistrées comme persistent views.
    # Elles sont créées lorsque !config est utilisé.

    if not vues_chargees:
        vues_chargees = True

    print(
        "✅ Configuration chargée."
    )


# ============================================================
# ERREURS COMMANDES
# ============================================================

@bot.event
async def on_command_error(
    ctx,
    error
):

    if isinstance(
        error,
        commands.CommandNotFound
    ):
        return

    if isinstance(
        error,
        commands.MissingPermissions
    ):

        await ctx.send(
            "❌ Tu n'as pas la permission d'utiliser cette commande.",
            delete_after=6
        )

        return

    if isinstance(
        error,
        commands.MissingRequiredArgument
    ):

        await ctx.send(
            "❌ Il manque un argument à la commande.",
            delete_after=6
        )

        return

    if isinstance(
        error,
        commands.MemberNotFound
    ):

        await ctx.send(
            "❌ Je ne trouve pas ce membre.",
            delete_after=6
        )

        return

    print(
        f"\n❌ ERREUR COMMANDE : {ctx.command}"
    )

    traceback.print_exception(
        type(error),
        error,
        error.__traceback__
    )

    try:

        await ctx.send(
            f"❌ Une erreur est survenue : `{error}`",
            delete_after=10
        )

    except Exception:
        pass


# ============================================================
# ERREURS GLOBALES
# ============================================================

@bot.event
async def on_error(
    event,
    *args,
    **kwargs
):

    print(
        f"\n❌ ERREUR EVENT : {event}"
    )

    traceback.print_exc()


# ============================================================
# LANCEMENT DU BOT
# ============================================================

if __name__ == "__main__":

    charger_configs()

    keep_alive()

    TOKEN = os.environ.get(
        "DISCORD_TOKEN"
    )

    if not TOKEN:

        raise RuntimeError(
            "❌ La variable DISCORD_TOKEN n'est pas configurée."
        )

    print(
        "🚀 Démarrage du bot..."
    )

    bot.run(
        TOKEN
    )
