import discord
from discord.ext import commands
import asyncio
from flask import Flask
from threading import Thread
import os
import json

# ============================================================
# KEEP-ALIVE WEB SERVER
# ============================================================

app = Flask('')


@app.route('/')
def home():
    return "Bot de classement actif !"


def run_web_server():
    app.run(host='0.0.0.0', port=10000)


def keep_alive():
    Thread(target=run_web_server, daemon=True).start()


# ============================================================
# BOT CONFIGURATION
# ============================================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# ============================================================
# DONNÉES
# ============================================================

classements_par_serveur = {}
id_messages_principaux = {}
id_salons_principaux = {}
config_serveurs = {}

FICHIER_CONFIG = "config_serveurs.json"


# ============================================================
# CONFIGURATION SERVEUR
# ============================================================

def charger_config_globale():
    if not os.path.exists(FICHIER_CONFIG):
        try:
            with open(FICHIER_CONFIG, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=4)

            return {}

        except Exception:
            return {}

    try:
        with open(FICHIER_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return {}


def enregistrer_config_globale(data):
    try:
        with open(FICHIER_CONFIG, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=4
            )

    except Exception:
        pass


# ============================================================
# CONFIGURATION PAR DÉFAUT
# ============================================================

def configuration_par_defaut():

    teams = {}

    # Team 1 à Team 3 par défaut
    for i in range(1, 4):

        if i == 1:
            nom_salon = "🏅𝐌𝐀𝐈𝐍 𝐑𝐎𝐒𝐓𝐄𝐑🏅"
            nom_role = "Main Roster"

        elif i == 2:
            nom_salon = "🥈︱𝐓𝐄𝐀𝐌-𝟐🥈"
            nom_role = "Team 2"

        else:
            nom_salon = f"🥉︱𝐓𝐄𝐀𝐌-𝟑🥉"
            nom_role = "Team 3"

        teams[str(i)] = {
            "nom": nom_salon,
            "role": nom_role,
            "max": 5
        }

    return {
        "role_admin_id": 1529373902969770094,
        "teams": teams,
        "motifs_tickets": [
            "Admin",
            "Test Team",
            "Tryout"
        ]
    }


# ============================================================
# MIGRATION ANCIENNE CONFIG
# ============================================================

def migrer_ancienne_configuration(config):
    """
    Transforme automatiquement l'ancienne configuration :

    noms_salons
    noms_roles
    taille_team

    vers :

    teams = {
        "1": {
            "nom": "...",
            "role": "...",
            "max": 5
        }
    }
    """

    if "teams" in config:
        return config

    ancienne_taille = int(
        config.get("taille_team", 5)
    )

    anciens_salons = config.get(
        "noms_salons",
        {}
    )

    anciens_roles = config.get(
        "noms_roles",
        {}
    )

    teams = {}

    nombres_equipes = max(
        len(anciens_salons),
        len(anciens_roles),
        3
    )

    for i in range(1, nombres_equipes + 1):

        numero = str(i)

        nom_salon = anciens_salons.get(
            numero,
            f"💫︱𝐓𝐄𝐀𝐌-{i}💫"
        )

        nom_role = anciens_roles.get(
            numero,
            f"Team {i}"
        )

        teams[numero] = {
            "nom": nom_salon,
            "role": nom_role,
            "max": ancienne_taille
        }

    nouvelle_config = {
        "role_admin_id": config.get(
            "role_admin_id",
            1529373902969770094
        ),
        "teams": teams,
        "motifs_tickets": config.get(
            "motifs_tickets",
            ["Admin", "Test Team", "Tryout"]
        )
    }

    return nouvelle_config


def obtenir_config_serveur(guild_id):

    global config_serveurs

    gid_str = str(guild_id)

    configs = charger_config_globale()

    if gid_str not in configs:

        configs[gid_str] = configuration_par_defaut()

        enregistrer_config_globale(
            configs
        )

    else:

        ancienne = configs[gid_str]

        nouvelle = migrer_ancienne_configuration(
            ancienne
        )

        configs[gid_str] = nouvelle

        if nouvelle != ancienne:
            enregistrer_config_globale(
                configs
            )

    config_serveurs[guild_id] = configs[gid_str]

    return configs[gid_str]


def mettre_a_jour_config_serveur(
    guild_id,
    cle,
    valeur
):

    configs = charger_config_globale()

    gid_str = str(guild_id)

    if gid_str not in configs:
        configs[gid_str] = configuration_par_defaut()

    configs[gid_str][cle] = valeur

    enregistrer_config_globale(
        configs
    )

    config_serveurs[guild_id] = configs[gid_str]


# ============================================================
# GESTION DYNAMIQUE DES TEAMS
# ============================================================

def obtenir_teams(guild_id):

    conf = obtenir_config_serveur(
        guild_id
    )

    return conf.get(
        "teams",
        {}
    )


def obtenir_team(guild_id, numero):

    teams = obtenir_teams(
        guild_id
    )

    return teams.get(
        str(numero)
    )


def obtenir_nom_salon_team(
    guild,
    numero
):

    team = obtenir_team(
        guild.id,
        numero
    )

    if team:
        return team.get(
            "nom",
            f"💫︱𝐓𝐄𝐀𝐌-{numero}💫"
        )

    return f"💫︱𝐓𝐄𝐀𝐌-{numero}💫"


def obtenir_nom_role_team(
    guild,
    numero
):

    team = obtenir_team(
        guild.id,
        numero
    )

    if team:
        return team.get(
            "role",
            f"Team {numero}"
        )

    return f"Team {numero}"


def obtenir_max_team(
    guild_id,
    numero
):

    team = obtenir_team(
        guild_id,
        numero
    )

    if team:
        try:
            return max(
                1,
                int(team.get("max", 5))
            )
        except Exception:
            return 5

    return 5


def obtenir_nombre_teams(
    guild_id
):

    teams = obtenir_teams(
        guild_id
    )

    if not teams:
        return 0

    return max(
        int(numero)
        for numero in teams.keys()
        if str(numero).isdigit()
    )


def obtenir_equipe_et_salon_dynamique(
    guild_id,
    position
):

    if position <= 0:
        return 1

    teams = obtenir_teams(
        guild_id
    )

    if not teams:
        return 1

    reste = position

    numeros = sorted(
        [
            int(x)
            for x in teams.keys()
            if str(x).isdigit()
        ]
    )

    for numero in numeros:

        capacite = obtenir_max_team(
            guild_id,
            numero
        )

        if reste <= capacite:
            return numero

        reste -= capacite

    return numeros[-1]


def normaliser_nom_salon(nom):

    return (
        nom.lower()
        .replace("-", "")
        .replace(" ", "")
        .replace("\ufe0f", "")
    )


# ============================================================
# AJOUTER UNE TEAM
# ============================================================

def ajouter_nouvelle_team(
    guild_id
):

    configs = charger_config_globale()

    gid_str = str(guild_id)

    if gid_str not in configs:
        configs[gid_str] = configuration_par_defaut()

    configs[gid_str] = migrer_ancienne_configuration(
        configs[gid_str]
    )

    teams = configs[gid_str]["teams"]

    numeros = [
        int(x)
        for x in teams.keys()
        if str(x).isdigit()
    ]

    nouveau_numero = (
        max(numeros) + 1
        if numeros
        else 1
    )

    teams[str(nouveau_numero)] = {
        "nom": f"💫︱𝐓𝐄𝐀𝐌-{nouveau_numero}💫",
        "role": f"Team {nouveau_numero}",
        "max": 5
    }

    configs[gid_str]["teams"] = teams

    enregistrer_config_globale(
        configs
    )

    config_serveurs[guild_id] = configs[gid_str]

    return nouveau_numero


# ============================================================
# PANEL DE CONFIGURATION
# ============================================================

class VuePanelConfig(discord.ui.View):

    def __init__(self, guild_id):

        super().__init__(
            timeout=120
        )

        self.add_item(
            MenuDeroulantConfiguration(
                guild_id
            )
        )


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
                label="Personnaliser les Teams",
                description="Modifier les Teams, rôles et limites.",
                emoji="✏️",
                value="custom_team"
            ),

            discord.SelectOption(
                label="Lier le Rôle Admin",
                description="Associer le rôle administrateur.",
                emoji="🛡️",
                value="role_admin"
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
        interaction: discord.Interaction
    ):

        choix = self.values[0]

        if choix == "custom_team":

            await interaction.response.send_message(
                embed=creer_embed_configuration_teams(
                    self.guild_id,
                    0
                ),
                view=VueConfigurationTeams(
                    self.guild_id,
                    0
                ),
                ephemeral=True
            )

        elif choix == "role_admin":

            await interaction.response.send_modal(
                ModalRoleAdmin()
            )

        elif choix == "motifs":

            await interaction.response.send_modal(
                ModalMotifsTickets()
            )


# ============================================================
# EMBED DES TEAMS
# ============================================================

def creer_embed_configuration_teams(
    guild_id,
    page=0
):

    teams = obtenir_teams(
        guild_id
    )

    numeros = sorted(
        teams.keys(),
        key=lambda x: int(x)
    )

    # 3 teams par page
    total_pages = max(
        1,
        (len(numeros) + 2) // 3
    )

    page = max(
        0,
        min(
            page,
            total_pages - 1
        )
    )

    debut = page * 3

    numeros_page = numeros[
        debut:debut + 3
    ]

    embed = discord.Embed(
        title="✏️ Personnalisation des Teams",
        description=(
            "Configurez chaque équipe individuellement.\n\n"
            "Chaque Team possède son propre :\n"
            "• numéro\n"
            "• nom du salon\n"
            "• nom du rôle\n"
            "• nombre maximum de joueurs\n\n"
            "Utilisez **Ajouter une Team** pour créer "
            "une nouvelle équipe.\n\n"
            f"📄 **Page {page + 1}/{total_pages}**\n"
            f"👥 **{len(numeros)} Teams configurées**"
        ),
        color=discord.Color.blue()
    )

    for numero in numeros_page:

        team = teams[numero]

        nom = team.get(
            "nom",
            f"Team {numero}"
        )

        role = team.get(
            "role",
            f"Team {numero}"
        )

        maximum = team.get(
            "max",
            5
        )

        embed.add_field(
            name=f"👥 TEAM {numero}",
            value=(
                f"**Numéro :** `{numero}`\n"
                f"**Nom du salon :** `{nom}`\n"
                f"**Nom du rôle :** `{role}`\n"
                f"**Maximum :** `{maximum} joueurs`"
            ),
            inline=False
        )

    return embed


# ============================================================
# VUE DES TEAMS
# ============================================================

class VueConfigurationTeams(
    discord.ui.View
):

    def __init__(
        self,
        guild_id,
        page=0
    ):

        super().__init__(
            timeout=180
        )

        self.guild_id = guild_id
        self.page = page

        self.reconstruire_menu()

    def reconstruire_menu(self):

        self.clear_items()

        teams = obtenir_teams(
            self.guild_id
        )

        numeros = sorted(
            teams.keys(),
            key=lambda x: int(x)
        )

        # 3 Teams maximum par page
        total_pages = max(
            1,
            (len(numeros) + 2) // 3
        )

        self.page = max(
            0,
            min(
                self.page,
                total_pages - 1
            )
        )

        debut = self.page * 3

        numeros_page = numeros[
            debut:debut + 3
        ]

        # Une ligne par Team
        for row, numero in enumerate(
            numeros_page
        ):

            self.add_item(
                MenuTeam(
                    self.guild_id,
                    int(numero),
                    row=row
                )
            )

        # Bouton ajouter
        self.add_item(
            BoutonAjouterTeam(
                self.guild_id,
                self.page
            )
        )

        # Page précédente
        if self.page > 0:

            self.add_item(
                BoutonPageTeams(
                    self.guild_id,
                    self.page,
                    -1
                )
            )

        # Page suivante
        if self.page < total_pages - 1:

            self.add_item(
                BoutonPageTeams(
                    self.guild_id,
                    self.page,
                    1
                )
            )


class MenuTeam(
    discord.ui.Select
):

    def __init__(
        self,
        guild_id,
        numero,
        row=0
    ):

        self.guild_id = guild_id
        self.numero = numero

        team = obtenir_team(
            guild_id,
            numero
        )

        nom = team.get(
            "nom",
            f"Team {numero}"
        )

        role = team.get(
            "role",
            f"Team {numero}"
        )

        maximum = team.get(
            "max",
            5
        )

        options = [

            discord.SelectOption(
                label=f"Team {numero}",
                description=(
                    f"Numéro {numero} • "
                    f"Max {maximum} joueurs"
                ),
                emoji="👥",
                value="modifier"
            ),

            discord.SelectOption(
                label="Supprimer cette Team",
                description=(
                    f"Supprimer Team {numero}"
                ),
                emoji="🗑️",
                value="supprimer"
            )

        ]

        super().__init__(
            placeholder=(
                f"TEAM {numero} • "
                f"{maximum} joueurs max • "
                f"{role}"
            ),
            min_values=1,
            max_values=1,
            options=options,
            row=row
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        choix = self.values[0]

        if choix == "modifier":

            await interaction.response.send_modal(
                ModalModifierTeam(
                    self.guild_id,
                    self.numero
                )
            )

        elif choix == "supprimer":

            teams = obtenir_teams(
                self.guild_id
            )

            if len(teams) <= 1:

                await interaction.response.send_message(
                    "❌ Vous devez garder au moins une Team.",
                    ephemeral=True
                )

                return

            del teams[str(self.numero)]

            # Réindexation automatique
            anciennes_teams = teams.copy()

            nouvelles_teams = {}

            nouveau_numero = 1

            for ancien_numero in sorted(
                anciennes_teams.keys(),
                key=lambda x: int(x)
            ):

                nouvelles_teams[
                    str(nouveau_numero)
                ] = anciennes_teams[
                    ancien_numero
                ]

                nouveau_numero += 1

            mettre_a_jour_config_serveur(
                self.guild_id,
                "teams",
                nouvelles_teams
            )

            await interaction.response.edit_message(
                embed=creer_embed_configuration_teams(
                    self.guild_id,
                    0
                ),
                view=VueConfigurationTeams(
                    self.guild_id,
                    0
                )
            )

            asyncio.create_task(
                rafraichir_partout(
                    interaction.guild
                )
            )


# ============================================================
# BOUTON NAVIGATION DES TEAMS
# ============================================================

class BoutonPageTeams(
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

        if direction < 0:

            super().__init__(
                label="Page précédente",
                emoji="⬅️",
                style=discord.ButtonStyle.secondary,
                row=4
            )

        else:

            super().__init__(
                label="Page suivante",
                emoji="➡️",
                style=discord.ButtonStyle.secondary,
                row=4
            )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        teams = obtenir_teams(
            self.guild_id
        )

        total_pages = max(
            1,
            (len(teams) + 2) // 3
        )

        nouvelle_page = (
            self.page + self.direction
        )

        nouvelle_page = max(
            0,
            min(
                nouvelle_page,
                total_pages - 1
            )
        )

        await interaction.response.edit_message(
            embed=creer_embed_configuration_teams(
                self.guild_id,
                nouvelle_page
            ),
            view=VueConfigurationTeams(
                self.guild_id,
                nouvelle_page
            )
        )


# ============================================================
# MODIFICATION D'UNE TEAM
# ============================================================

class ModalModifierTeam(
    discord.ui.Modal
):

    def __init__(
        self,
        guild_id,
        numero
    ):

        self.guild_id = guild_id
        self.numero = numero

        team = obtenir_team(
            guild_id,
            numero
        )

        super().__init__(
            title=f"Configuration Team {numero}"
        )

        self.nom_salon = discord.ui.TextInput(
            label="Nom du Salon",
            placeholder="Ex: 🏅︱𝐌𝐀𝐈𝐍-𝐑𝐎𝐒𝐓𝐄𝐑",
            default=team.get(
                "nom",
                f"Team {numero}"
            ),
            max_length=100
        )

        self.nom_role = discord.ui.TextInput(
            label="Nom du Rôle",
            placeholder="Ex: Main Roster",
            default=team.get(
                "role",
                f"Team {numero}"
            ),
            max_length=100
        )

        self.maximum = discord.ui.TextInput(
            label="Nombre maximum de joueurs",
            placeholder="Ex: 5",
            default=str(
                team.get(
                    "max",
                    5
                )
            ),
            min_length=1,
            max_length=4
        )

        self.add_item(
            self.nom_salon
        )

        self.add_item(
            self.nom_role
        )

        self.add_item(
            self.maximum
        )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        try:

            maximum = int(
                self.maximum.value.strip()
            )

            if maximum < 1:
                raise ValueError()

            if maximum > 9999:
                raise ValueError()

        except Exception:

            await interaction.response.send_message(
                "❌ Le nombre maximum doit être compris entre 1 et 9999.",
                ephemeral=True
            )

            return

        teams = obtenir_teams(
            self.guild_id
        )

        numero = str(
            self.numero
        )

        if numero not in teams:

            await interaction.response.send_message(
                "❌ Cette Team n'existe plus.",
                ephemeral=True
            )

            return

        teams[numero] = {
            "nom": self.nom_salon.value.strip(),
            "role": self.nom_role.value.strip(),
            "max": maximum
        }

        mettre_a_jour_config_serveur(
            self.guild_id,
            "teams",
            teams
        )

        await interaction.response.send_message(
            embed=creer_embed_configuration_teams(
                self.guild_id,
                (self.numero - 1) // 3
            ),
            view=VueConfigurationTeams(
                self.guild_id,
                (self.numero - 1) // 3
            ),
            ephemeral=True
        )

        asyncio.create_task(
            rafraichir_partout(
                interaction.guild
            )
        )


# ============================================================
# AJOUTER UNE TEAM
# ============================================================

class BoutonAjouterTeam(
    discord.ui.Button
):

    def __init__(
        self,
        guild_id,
        page=0
    ):

        self.guild_id = guild_id
        self.page = page

        super().__init__(
            label="Ajouter une Team",
            emoji="➕",
            style=discord.ButtonStyle.success,
            row=3
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        nouveau_numero = ajouter_nouvelle_team(
            self.guild_id
        )

        # Aller automatiquement sur la page
        # où se trouve la nouvelle Team
        nouvelle_page = (
            nouveau_numero - 1
        ) // 3

        await interaction.response.edit_message(
            embed=creer_embed_configuration_teams(
                self.guild_id,
                nouvelle_page
            ),
            view=VueConfigurationTeams(
                self.guild_id,
                nouvelle_page
            )
        )

        asyncio.create_task(
            rafraichir_partout(
                interaction.guild
            )
        )


# ============================================================
# ROLE ADMIN
# ============================================================

class ModalRoleAdmin(
    discord.ui.Modal,
    title="Sécurité Staff 🛡️"
):

    rid = discord.ui.TextInput(
        label="ID du rôle autorisé pour les commandes DATA",
        placeholder="Collez l'ID numérique ici"
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        try:

            val = int(
                self.rid.value.strip()
            )

            mettre_a_jour_config_serveur(
                interaction.guild_id,
                "role_admin_id",
                val
            )

            embed = discord.Embed(
                title="⚙️ Configuration Mise à Jour",
                description=(
                    "Le rôle Admin de gestion a été "
                    f"lié avec succès à l'ID : `{val}`."
                ),
                color=discord.Color.green()
            )

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )

        except Exception:

            await interaction.response.send_message(
                "❌ Erreur : ID numérique invalide.",
                ephemeral=True
            )


# ============================================================
# MOTIFS TICKETS
# ============================================================

class ModalMotifsTickets(
    discord.ui.Modal,
    title="Menu des Tickets 🎫"
):

    motifs = discord.ui.TextInput(
        label="Raisons (Séparez chaque choix par une virgule)",
        placeholder="Ex: Admin, Recrutement, Demande Match",
        style=discord.TextStyle.paragraph
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        liste = [
            m.strip()
            for m in self.motifs.value.split(",")
            if m.strip()
        ]

        if not liste:

            await interaction.response.send_message(
                "❌ Erreur : Veuillez entrer au moins un motif valide.",
                ephemeral=True
            )

            return

        mettre_a_jour_config_serveur(
            interaction.guild_id,
            "motifs_tickets",
            liste
        )

        embed = discord.Embed(
            title="⚙️ Configuration Mise à Jour",
            description=(
                "Le menu déroulant des tickets propose désormais : "
                f"`{', '.join(liste)}`."
            ),
            color=discord.Color.green()
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


# ============================================================
# PANEL DATA
# ============================================================

class VueDataOptions(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=60
        )

    @discord.ui.button(
        label="GÉNÉRER UN CODE TEXTE 💾",
        style=discord.ButtonStyle.success
    )
    async def btn_generer_code(
        self,
        interaction,
        button
    ):

        gid = interaction.guild_id

        top_actuel = classements_par_serveur.get(
            gid,
            []
        )

        if not top_actuel:

            await interaction.response.send_message(
                "⚠️ Le classement actuel est vide. Rien à générer.",
                ephemeral=True
            )

            return

        code_ids_bruts = ",".join(
            str(uid)
            for uid in top_actuel
        )

        await interaction.response.send_message(
            content=(
                "💾 **Séquence de Sauvegarde brute générée !**\n"
                "Copiez les IDs ordonnés ci-dessous :\n\n"
                f"`{code_ids_bruts}`"
            ),
            ephemeral=True
        )

    @discord.ui.button(
        label="RESTAURER VIA UN CODE 🔄",
        style=discord.ButtonStyle.danger
    )
    async def btn_restaurer_code(
        self,
        interaction,
        button
    ):

        await interaction.response.send_modal(
            FenetreCollerCode()
        )


class FenetreCollerCode(
    discord.ui.Modal,
    title="Restaurer le classement"
):

    code_entre = discord.ui.TextInput(
        label="Collez la suite d'IDs Discord séparés par des virgules",
        placeholder="Ex: 1529373902969770094,25901653...",
        style=discord.TextStyle.paragraph
    )

    async def on_submit(
        self,
        interaction
    ):

        brut = self.code_entre.value.strip()

        if not brut:

            await interaction.response.send_message(
                "❌ Le champ est vide.",
                ephemeral=True
            )

            return

        try:

            liste_ids = [
                int(uid.strip())
                for uid in brut.split(",")
                if uid.strip().isdigit()
            ]

            if not liste_ids:

                await interaction.response.send_message(
                    "❌ Séquence invalide.",
                    ephemeral=True
                )

                return

            classements_par_serveur[
                interaction.guild_id
            ] = list(liste_ids)

            await interaction.response.send_message(
                "✅ **Séquence acceptée !** Le bot met à jour les salons et les rôles.",
                ephemeral=True
            )

            asyncio.create_task(
                rafraichir_partout(
                    interaction.guild
                )
            )

        except Exception as e:

            await interaction.response.send_message(
                f"❌ Impossible de charger cette séquence : `{e}`",
                ephemeral=True
            )


# ============================================================
# MODALS CLASSEMENT
# ============================================================

class FenetreDeplacement(
    discord.ui.Modal,
    title="Changer la place (Décaler)"
):

    pos_depart = discord.ui.TextInput(
        label="Position actuelle",
        placeholder="Ex: 5"
    )

    pos_arrivee = discord.ui.TextInput(
        label="Nouvelle position",
        placeholder="Ex: 2"
    )

    async def on_submit(
        self,
        interaction
    ):

        gid = interaction.guild_id

        if gid not in classements_par_serveur:
            classements_par_serveur[gid] = []

        try:

            p_dep = int(
                self.pos_depart.value
            ) - 1

            p_arr = int(
                self.pos_arrivee.value
            ) - 1

            liste = classements_par_serveur[gid]

            if (
                p_dep < 0
                or p_arr < 0
                or p_dep >= len(liste)
                or p_arr >= len(liste)
            ):

                await interaction.response.send_message(
                    "❌ Position invalide.",
                    ephemeral=True
                )

                return

            joueur_id = liste.pop(
                p_dep
            )

            liste.insert(
                p_arr,
                joueur_id
            )

            await interaction.response.send_message(
                "📈 Déplacement effectué !",
                ephemeral=True
            )

            asyncio.create_task(
                rafraichir_partout(
                    interaction.guild
                )
            )

        except Exception:

            await interaction.response.send_message(
                "❌ Valeurs invalides.",
                ephemeral=True
            )


class FenetreEchange(
    discord.ui.Modal,
    title="Échanger 2 places"
):

    pos1 = discord.ui.TextInput(
        label="Position 1er joueur",
        placeholder="Ex: 2"
    )

    pos2 = discord.ui.TextInput(
        label="Position 2ème joueur",
        placeholder="Ex: 5"
    )

    async def on_submit(
        self,
        interaction
    ):

        try:

            p1 = int(
                self.pos1.value
            ) - 1

            p2 = int(
                self.pos2.value
            ) - 1

            liste = classements_par_serveur[
                interaction.guild_id
            ]

            liste[p1], liste[p2] = (
                liste[p2],
                liste[p1]
            )

            await interaction.response.send_message(
                "🔄 Échange effectué !",
                ephemeral=True
            )

            asyncio.create_task(
                rafraichir_partout(
                    interaction.guild
                )
            )

        except Exception:

            await interaction.response.send_message(
                "❌ Positions invalides.",
                ephemeral=True
            )


class FenetreSuppression(
    discord.ui.Modal,
    title="Retirer un joueur"
):

    pos_suppr = discord.ui.TextInput(
        label="Position à supprimer",
        placeholder="Ex: 3"
    )

    async def on_submit(
        self,
        interaction
    ):

        try:

            p = int(
                self.pos_suppr.value
            ) - 1

            classements_par_serveur[
                interaction.guild_id
            ].pop(p)

            await interaction.response.send_message(
                "❌ Joueur retiré !",
                ephemeral=True
            )

            asyncio.create_task(
                rafraichir_partout(
                    interaction.guild
                )
            )

        except Exception:

            await interaction.response.send_message(
                "❌ Position invalide.",
                ephemeral=True
            )


# ============================================================
# CONTROLE DU TOP
# ============================================================

class VueControleTop(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Changer de place 📈",
        style=discord.ButtonStyle.primary,
        custom_id="btn_deplace"
    )
    async def bouton_deplace(
        self,
        interaction,
        button
    ):

        if not interaction.user.guild_permissions.administrator:
            return

        await interaction.response.send_modal(
            FenetreDeplacement()
        )

    @discord.ui.button(
        label="Échanger 2 places 🔄",
        style=discord.ButtonStyle.secondary,
        custom_id="btn_echange"
    )
    async def bouton_echange(
        self,
        interaction,
        button
    ):

        if not interaction.user.guild_permissions.administrator:
            return

        await interaction.response.send_modal(
            FenetreEchange()
        )

    @discord.ui.button(
        label="Retirer du Top ❌",
        style=discord.ButtonStyle.danger,
        custom_id="btn_suppr"
    )
    async def bouton_supprime(
        self,
        interaction,
        button
    ):

        if not interaction.user.guild_permissions.administrator:
            return

        await interaction.response.send_modal(
            FenetreSuppression()
        )

    @discord.ui.button(
        label="DATA 🗄️",
        style=discord.ButtonStyle.danger,
        custom_id="btn_data_panel"
    )
    async def bouton_data_panel(
        self,
        interaction,
        button
    ):

        conf = obtenir_config_serveur(
            interaction.guild_id
        )

        role_verif = discord.utils.get(
            interaction.user.roles,
            id=int(
                conf["role_admin_id"]
            )
        )

        if (
            not role_verif
            and not interaction.user.guild_permissions.administrator
        ):

            await interaction.response.send_message(
                "❌ Accès refusé. Rôle ADMIN requis.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            content="🗄️ **Gestion de la Base de Données (Permanent)**",
            view=VueDataOptions(),
            ephemeral=True
        )

    @discord.ui.button(
        label="Liste des Commandes ❓",
        style=discord.ButtonStyle.success,
        custom_id="btn_help"
    )
    async def bouton_aide(
        self,
        interaction,
        button
    ):

        embed = discord.Embed(
            title="🤖 Guide des commandes",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="🛠️ Commandes Admin",
            value=(
                "`!setup`, "
                "`!add @membre`, "
                "`!addmany @m1 @m2...`, "
                "`!remove @membre`, "
                "`!tstart`, "
                "`!twin`, "
                "`!setup_ticket`, "
                "`!config`"
            ),
            inline=False
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


# ============================================================
# TICKETS
# ============================================================

class VueCreationTicket(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Créer un ticket 🎫",
        style=discord.ButtonStyle.primary,
        custom_id="btn_creer_ticket"
    )
    async def bouton_ticket(
        self,
        interaction,
        button
    ):

        await interaction.response.send_message(
            content="📋 **Sélectionnez le motif de votre ticket :**",
            view=VueChoixMotifTicket(
                interaction.guild_id
            ),
            ephemeral=True
        )


class VueChoixMotifTicket(
    discord.ui.View
):

    def __init__(
        self,
        guild_id
    ):

        super().__init__(
            timeout=60
        )

        conf = obtenir_config_serveur(
            guild_id
        )

        options = [
            discord.SelectOption(
                label=m[:100],
                value=m[:100]
            )
            for m in conf["motifs_tickets"][:25]
        ]

        self.add_item(
            MenuDeroulantMotif(
                options
            )
        )


class MenuDeroulantMotif(
    discord.ui.Select
):

    def __init__(
        self,
        options
    ):

        super().__init__(
            placeholder="Choisissez la raison du ticket...",
            options=options
        )

    async def callback(
        self,
        interaction
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        motif_selectionne = self.values[0]

        guild = interaction.guild

        conf = obtenir_config_serveur(
            guild.id
        )

        nom_categorie_propre = "🎫 𝙏𝙄𝘾𝙆𝙀𝙏"

        categorie = discord.utils.find(
            lambda c:
                c.name == nom_categorie_propre
                and isinstance(
                    c,
                    discord.CategoryChannel
                ),
            guild.channels
        )

        if not categorie:

            try:

                categorie = await guild.create_category(
                    name=nom_categorie_propre
                )

            except Exception as e:

                await interaction.followup.send(
                    f"❌ Erreur catégorie : `{e}`",
                    ephemeral=True
                )

                return

        try:

            membre_createur = await guild.fetch_member(
                interaction.user.id
            )

        except Exception:

            membre_createur = interaction.user

        overwrites = {

            guild.default_role:
                discord.PermissionOverwrite(
                    read_messages=False,
                    view_channel=False
                ),

            membre_createur:
                discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    attach_files=True,
                    view_channel=True
                ),

            guild.me:
                discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    view_channel=True
                )
        }

        role_admin = guild.get_role(
            int(
                conf["role_admin_id"]
            )
        )

        if role_admin:

            overwrites[role_admin] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                view_channel=True
            )

        nom_salon = (
            f"🎫-{motif_selectionne.lower().replace(' ', '-')}-"
            f"{interaction.user.name}"
        )

        try:

            salon_ticket = await guild.create_text_channel(
                name=nom_salon[:100],
                category=categorie,
                overwrites=overwrites
            )

            await interaction.followup.send(
                f"✅ Ticket ouvert dans {salon_ticket.mention} !",
                ephemeral=True
            )

            embed = discord.Embed(
                title=f"🎫 Ticket - {motif_selectionne}",
                description=(
                    f"Bonjour {interaction.user.mention},\n\n"
                    "Un membre de l'équipe administrative "
                    "va vous prendre en charge.\n\n"
                    "Décrivez votre demande."
                ),
                color=discord.Color.blue()
            )

            await salon_ticket.send(
                embed=embed,
                view=VueFermetureTicket()
            )

        except Exception as e:

            await interaction.followup.send(
                f"❌ Échec de création : `{e}`",
                ephemeral=True
            )


class VueFermetureTicket(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Fermer le ticket 🔒",
        style=discord.ButtonStyle.danger,
        custom_id="btn_fermer_ticket"
    )
    async def bouton_fermer(
        self,
        interaction,
        button
    ):

        conf = obtenir_config_serveur(
            interaction.guild_id
        )

        role_verif = discord.utils.get(
            interaction.user.roles,
            id=int(
                conf["role_admin_id"]
            )
        )

        if (
            not role_verif
            and not interaction.user.guild_permissions.administrator
        ):

            await interaction.response.send_message(
                "❌ Seul un admin peut fermer ce ticket.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "🔒 **Fermeture et suppression du salon dans 5 secondes.**"
        )

        await asyncio.sleep(5)

        await interaction.channel.delete()


# ============================================================
# REFRESH DYNAMIQUE
# ============================================================

rafraichissement_en_cours = {}


async def rafraichir_partout(
    guild
):

    gid = guild.id

    if rafraichissement_en_cours.get(
        gid,
        False
    ):

        return

    rafraichissement_en_cours[gid] = True

    try:

        if gid not in id_salons_principaux:
            return

        if not id_salons_principaux[gid]:
            return

        if gid not in classements_par_serveur:

            classements_par_serveur[gid] = []

        teams = obtenir_teams(
            gid
        )

        if not teams:
            return

        roles_par_team = {}
        salons_par_team = {}

        for numero in sorted(
            teams.keys(),
            key=lambda x: int(x)
        ):

            num = int(numero)

            nom_role = obtenir_nom_role_team(
                guild,
                num
            )

            nom_salon = obtenir_nom_salon_team(
                guild,
                num
            )

            role = discord.utils.get(
                guild.roles,
                name=nom_role
            )

            if role is None:

                try:

                    role = await guild.create_role(
                        name=nom_role,
                        reason="Classement automatique"
                    )

                except Exception:

                    role = None

            roles_par_team[num] = role

            salon = discord.utils.find(
                lambda c:
                    isinstance(
                        c,
                        discord.TextChannel
                    )
                    and normaliser_nom_salon(
                        c.name
                    )
                    ==
                    normaliser_nom_salon(
                        nom_salon
                    ),
                guild.channels
            )

            if salon is None:

                try:

                    salon = await guild.create_text_channel(
                        name=nom_salon,
                        reason="Classement automatique"
                    )

                except Exception:

                    salon = None

            salons_par_team[num] = salon

        positions_teams = {}

        for index, user_id in enumerate(
            classements_par_serveur[gid]
        ):

            position = index + 1

            team = obtenir_equipe_et_salon_dynamique(
                gid,
                position
            )

            positions_teams[user_id] = team

        tous_les_roles_team = [
            role
            for role in roles_par_team.values()
            if role is not None
        ]

        membres_roster = set(
            positions_teams.keys()
        )

        for role in tous_les_roles_team:

            try:

                for member in list(
                    role.members
                ):

                    if member.id not in membres_roster:

                        try:

                            await member.remove_roles(
                                role,
                                reason="Retrait du classement"
                            )

                        except Exception:
                            pass

            except Exception:
                pass

        for user_id, team in positions_teams.items():

            try:

                member = guild.get_member(
                    user_id
                )

                if member is None:

                    try:

                        member = await guild.fetch_member(
                            user_id
                        )

                    except Exception:

                        continue

                role = roles_par_team.get(
                    team
                )

                if role is None:
                    continue

                mauvais_roles = [
                    r
                    for r in tous_les_roles_team
                    if r != role and r in member.roles
                ]

                if mauvais_roles:

                    try:

                        await member.remove_roles(
                            *mauvais_roles,
                            reason="Changement de Team"
                        )

                    except Exception:
                        pass

                if role not in member.roles:

                    try:

                        await member.add_roles(
                            role,
                            reason="Classement automatique"
                        )

                    except Exception:
                        pass

            except Exception:
                pass

        salon_top = guild.get_channel(
            id_salons_principaux[gid]
        )

        if salon_top:

            texte_top = (
                "🏆 **CLASSEMENT GÉNÉRAL COMPLET** 🏆\n\n"
            )

            if not classements_par_serveur[gid]:

                texte_top += (
                    "*Aucun joueur dans le top pour le moment.*"
                )

            else:

                for index, user_id in enumerate(
                    classements_par_serveur[gid]
                ):

                    texte_top += (
                        f"**Top {index + 1}** : "
                        f"<@{user_id}>\n"
                    )

            message_existe = False

            if id_messages_principaux.get(
                gid
            ):

                try:

                    msg = await salon_top.fetch_message(
                        id_messages_principaux[gid]
                    )

                    await msg.edit(
                        content=texte_top,
                        view=VueControleTop()
                    )

                    message_existe = True

                except Exception:
                    pass

            if not message_existe:

                try:

                    msg = await salon_top.send(
                        content=texte_top,
                        view=VueControleTop()
                    )

                    id_messages_principaux[gid] = msg.id

                except Exception:
                    pass

        for numero in sorted(
            teams.keys(),
            key=lambda x: int(x)
        ):

            num = int(numero)

            salon_team = salons_par_team.get(
                num
            )

            if salon_team is None:
                continue

            try:

                lignes = []

                for index, user_id in enumerate(
                    classements_par_serveur[gid]
                ):

                    position = index + 1

                    team_joueur = (
                        obtenir_equipe_et_salon_dynamique(
                            gid,
                            position
                        )
                    )

                    if team_joueur == num:

                        lignes.append(
                            f"**Top {position}** : "
                            f"<@{user_id}>"
                        )

                titre = obtenir_nom_role_team(
                    guild,
                    num
                ).upper()

                await salon_team.purge(
                    limit=20
                )

                if lignes:

                    texte = (
                        f"🏆 **Membres - {titre}** 🏆\n\n"
                        + "\n".join(lignes)
                    )

                else:

                    texte = (
                        f"Aucun joueur assigné au "
                        f"{titre} actuellement."
                    )

                await salon_team.send(
                    texte
                )

            except Exception:
                pass

    finally:

        rafraichissement_en_cours[gid] = False


# ============================================================
# TOURNOI FLASH
# ============================================================

tournois_par_serveur = {}


def generer_affichage_tournoi(
    gid
):

    t = tournois_par_serveur.get(
        gid,
        {
            "inscrits": [],
            "etape": "ferme",
            "matchs": {},
            "vainqueurs": {}
        }
    )

    texte = (
        "⚔️ ─── **TOURNOI FLASH AUTOMATIQUE** ─── ⚔️\n\n"
    )

    if t["etape"] == "inscriptions":

        texte += (
            f"📌 **Inscriptions ouvertes : "
            f"{len(t['inscrits'])} / 8**\n\n"
        )

        for index, user_id in enumerate(
            t["inscrits"]
        ):

            texte += (
                f"{index + 1}. <@{user_id}>\n"
            )

        return texte

    texte += "◽ **QUARTS DE FINALE** ◽\n"

    for m in range(1, 5):

        joueurs = t["matchs"].get(
            f"Q{m}",
            []
        )

        p1 = (
            f"<@{joueurs[0]}>"
            if len(joueurs) > 0
            else "À définir"
        )

        p2 = (
            f"<@{joueurs[1]}>"
            if len(joueurs) > 1
            else "À définir"
        )

        gagnant = t["vainqueurs"].get(
            f"Q{m}"
        )

        v = (
            f"🏅 Vainqueur : <@{gagnant}>"
            if gagnant
            else "En attente..."
        )

        texte += (
            f"🔹 Match Q{m} : "
            f"{p1} VS {p2}\n"
            f"   └─ {v}\n"
        )

    return texte


class VueInscriptionTournoi(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="S'inscrire ⚔️",
        style=discord.ButtonStyle.success,
        custom_id="btn_join_tournoi"
    )
    async def bouton_inscription(
        self,
        interaction,
        button
    ):

        gid = interaction.guild_id

        if gid not in tournois_par_serveur:
            return

        t = tournois_par_serveur[gid]

        if (
            t["etape"] != "inscriptions"
            or interaction.user.id in t["inscrits"]
        ):
            return

        t["inscrits"].append(
            interaction.user.id
        )

        if len(t["inscrits"]) == 8:

            t["etape"] = "quarts"

            for m in range(1, 5):

                t["matchs"][f"Q{m}"] = [
                    t["inscrits"][
                        (m - 1) * 2
                    ],
                    t["inscrits"][
                        (m - 1) * 2 + 1
                    ]
                ]

            await interaction.message.edit(
                content=generer_affichage_tournoi(
                    gid
                ),
                view=None
            )

        else:

            await interaction.message.edit(
                content=generer_affichage_tournoi(
                    gid
                ),
                view=self
            )

        await interaction.response.defer()


# ============================================================
# COMMANDES
# ============================================================

@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def initialiser_salon_top(
    ctx
):

    gid = ctx.guild.id

    classements_par_serveur[gid] = []

    id_salons_principaux[gid] = (
        ctx.channel.id
    )

    id_messages_principaux[gid] = None

    try:
        await ctx.message.delete()
    except Exception:
        pass

    await rafraichir_partout(
        ctx.guild
    )


@bot.command(name="config")
@commands.has_permissions(administrator=True)
async def ouvrir_menu_config(
    ctx
):

    try:
        await ctx.message.delete()
    except Exception:
        pass

    embed = discord.Embed(
        title="🎛️ Panneau de Configuration Personnalisable",
        description=(
            "Cliquez sur le menu déroulant ci-dessous "
            "pour modifier la structure du serveur."
        ),
        color=discord.Color.blue()
    )

    await ctx.send(
        embed=embed,
        view=VuePanelConfig(
            ctx.guild.id
        ),
        delete_after=120
    )


@bot.command(name="add")
@commands.has_permissions(administrator=True)
async def ajouter_joueur(
    ctx,
    membre: discord.Member
):

    gid = ctx.guild.id

    if gid not in classements_par_serveur:

        classements_par_serveur[gid] = []

    if membre.id not in classements_par_serveur[gid]:

        classements_par_serveur[gid].append(
            membre.id
        )

    try:
        await ctx.message.delete()
    except Exception:
        pass

    await rafraichir_partout(
        ctx.guild
    )


@bot.command(name="addmany")
@commands.has_permissions(administrator=True)
async def ajouter_plusieurs_joueurs(
    ctx,
    *membres: discord.Member
):

    gid = ctx.guild.id

    if gid not in classements_par_serveur:

        classements_par_serveur[gid] = []

    for membre in membres:

        if membre.id not in classements_par_serveur[gid]:

            classements_par_serveur[gid].append(
                membre.id
            )

    try:
        await ctx.message.delete()
    except Exception:
        pass

    await rafraichir_partout(
        ctx.guild
    )


@bot.command(name="remove")
@commands.has_permissions(administrator=True)
async def supprimer_joueur_txt(
    ctx,
    membre: discord.Member
):

    gid = ctx.guild.id

    if (
        gid in classements_par_serveur
        and membre.id in classements_par_serveur[gid]
    ):

        classements_par_serveur[gid].remove(
            membre.id
        )

    try:
        await ctx.message.delete()
    except Exception:
        pass

    await rafraichir_partout(
        ctx.guild
    )


# ============================================================
# TOURNOI
# ============================================================

@bot.command(name="tstart")
@commands.has_permissions(administrator=True)
async def lancer_inscriptions_tournoi(
    ctx
):

    gid = ctx.guild.id

    tournois_par_serveur[gid] = {
        "inscrits": [],
        "etape": "inscriptions",
        "matchs": {},
        "vainqueurs": {},
        "msg_id": None
    }

    try:
        await ctx.message.delete()
    except Exception:
        pass

    msg = await ctx.send(
        content=generer_affichage_tournoi(
            gid
        ),
        view=VueInscriptionTournoi()
    )

    tournois_par_serveur[gid]["msg_id"] = (
        msg.id
    )


@bot.command(name="twin")
@commands.has_permissions(administrator=True)
async def valider_gagnant_match(
    ctx,
    code_match: str,
    membre: discord.Member
):

    gid = ctx.guild.id

    if gid not in tournois_par_serveur:
        return

    t = tournois_par_serveur[gid]

    code_match = code_match.upper()

    t["vainqueurs"][code_match] = (
        membre.id
    )

    try:
        await ctx.message.delete()
    except Exception:
        pass

    try:

        msg = await ctx.channel.fetch_message(
            t["msg_id"]
        )

        await msg.edit(
            content=generer_affichage_tournoi(
                gid
            )
        )

    except Exception:
        pass


# ============================================================
# TICKETS
# ============================================================

@bot.command(name="setup_ticket")
@commands.has_permissions(administrator=True)
async def envoyer_panneau_ticket(
    ctx
):

    try:
        await ctx.message.delete()
    except Exception:
        pass

    embed = discord.Embed(
        title="🎫 Support & Recrutement - Système de Tickets",
        description=(
            "Cliquez ci-dessous pour ouvrir un salon "
            "d'assistance privé.\n"
            "Les salons apparaîtront dans la catégorie "
            "**🎫 𝙏𝙄𝘾𝙆𝙀𝙏**."
        ),
        color=discord.Color.green()
    )

    await ctx.send(
        embed=embed,
        view=VueCreationTicket()
    )


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    bot.add_view(
        VueControleTop()
    )

    bot.add_view(
        VueCreationTicket()
    )

    bot.add_view(
        VueFermetureTicket()
    )

    bot.add_view(
        VueInscriptionTournoi()
    )

    print(
        f"Bot en ligne : {bot.user.name}"
    )


# ============================================================
# LANCEMENT
# ============================================================

keep_alive()

TOKEN = os.environ.get(
    "DISCORD_TOKEN"
)

if not TOKEN:

    print(
        "❌ ERREUR : DISCORD_TOKEN est introuvable."
    )

else:

    bot.run(
        TOKEN
    )
