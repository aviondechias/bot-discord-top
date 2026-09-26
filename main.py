import discord
from discord.ext import commands
import asyncio
from flask import Flask
from threading import Thread
import os
import json

# --- KEEP-ALIVE WEB SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "Bot de classement actif !"

def run_web_server():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    Thread(target=run_web_server).start()


# --- BOT CONFIGURATION ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# Isolated data structures per server ID
classements_par_serveur = {}      # {guild_id: [liste_joueurs_ids]}
id_messages_principaux = {}       # {guild_id: id_message}
id_salons_principaux = {}         # {guild_id: id_salon}
config_serveurs = {}              # {guild_id: {options_de_config}}

FICHIER_CONFIG = "config_serveurs.json"


# --- SAFELYNED CONFIGURATION LOADER ---
def charger_config_globale():
    if not os.path.exists(FICHIER_CONFIG):
        try:
            with open(FICHIER_CONFIG, "w", encoding="utf-8") as f:
                json.dump({}, f)
            return {}
        except:
            return {}

    try:
        with open(FICHIER_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def enregistrer_config_globale(data):
    try:
        with open(FICHIER_CONFIG, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except:
        pass


# --- SERVER CONFIGURATION ---
def obtenir_config_serveur(guild_id):
    global config_serveurs

    gid_str = str(guild_id)
    configs = charger_config_globale()

    if gid_str not in configs:

        configs[gid_str] = {
            "role_admin_id": 1529373902969770094,

            "teams": {
                "1": {
                    "nom_salon": "🏅𝐌𝐀𝐈𝐍 𝐑𝐎𝐒𝐓𝐄𝐑🏅",
                    "nom_role": "Main Roster",
                    "max_joueurs": 5
                },

                "2": {
                    "nom_salon": "🥈︱𝐓𝐄𝐀𝐌-𝟐🥈",
                    "nom_role": "Team 2",
                    "max_joueurs": 5
                },

                "3": {
                    "nom_salon": "🥉︱𝐓𝐄𝐀𝐌-𝟑🥉",
                    "nom_role": "Team 3",
                    "max_joueurs": 5
                }
            },

            "motifs_tickets": [
                "Admin",
                "Test Team",
                "Tryout"
            ]
        }

        enregistrer_config_globale(configs)

    conf = configs[gid_str]

    # --- MIGRATION AUTOMATIQUE DE L'ANCIEN SYSTEME ---
    if "teams" not in conf:

        anciens_salons = conf.get("noms_salons", {})
        anciens_roles = conf.get("noms_roles", {})

        ancienne_taille = int(
            conf.get("taille_team", 5)
        )

        conf["teams"] = {}

        for i in range(1, 9):

            numero = str(i)

            conf["teams"][numero] = {
                "nom_salon": anciens_salons.get(
                    numero,
                    f"💫︱𝐓𝐄𝐀𝐌-{i}💫"
                ),

                "nom_role": anciens_roles.get(
                    numero,
                    f"Team {i}"
                ),

                "max_joueurs": ancienne_taille
            }

        conf.pop("noms_salons", None)
        conf.pop("noms_roles", None)
        conf.pop("taille_team", None)

        enregistrer_config_globale(configs)

    # --- SECURITE SI CERTAINES OPTIONS MANQUENT ---
    if "teams" not in conf:
        conf["teams"] = {}

    if "motifs_tickets" not in conf:
        conf["motifs_tickets"] = [
            "Admin",
            "Test Team",
            "Tryout"
        ]

    if "role_admin_id" not in conf:
        conf["role_admin_id"] = 1529373902969770094

    config_serveurs[guild_id] = conf

    return conf


def mettre_a_jour_config_serveur(guild_id, cle, valeur):

    configs = charger_config_globale()
    gid_str = str(guild_id)

    if gid_str not in configs:
        obtenir_config_serveur(guild_id)
        configs = charger_config_globale()

    configs[gid_str][cle] = valeur

    enregistrer_config_globale(configs)

    config_serveurs[guild_id] = configs[gid_str]


def obtenir_nom_salon_team(guild, num_team):

    conf = obtenir_config_serveur(guild.id)

    team = conf["teams"].get(str(num_team))

    if team:
        return team.get(
            "nom_salon",
            f"💫︱𝐓𝐄𝐀𝐌-{num_team}💫"
        )

    return f"💫︱𝐓𝐄𝐀𝐌-{num_team}💫"


def obtenir_nom_role_team(guild, num_team):

    conf = obtenir_config_serveur(guild.id)

    team = conf["teams"].get(str(num_team))

    if team:
        return team.get(
            "nom_role",
            f"Team {num_team}"
        )

    return f"Team {num_team}"


def obtenir_equipe_et_salon_dynamique(guild_id, position):

    conf = obtenir_config_serveur(guild_id)

    teams = conf.get("teams", {})

    if not teams:
        return 1

    joueurs_comptes = 0

    for numero in sorted(
        teams.keys(),
        key=lambda x: int(x)
    ):

        max_joueurs = int(
            teams[numero].get(
                "max_joueurs",
                5
            )
        )

        joueurs_comptes += max_joueurs

        if position <= joueurs_comptes:
            return int(numero)

    # Si toutes les teams sont pleines,
    # le joueur est placé dans la dernière team
    return max(
        int(numero)
        for numero in teams.keys()
    )


def normaliser_nom_salon(nom):

    return (
        nom
        .lower()
        .replace("-", "")
        .replace(" ", "")
        .replace("\ufe0f", "")
    )


# ============================================================
# --- PANEL DE CONFIGURATION PREMIUM DYNAMIQUE ---
# ============================================================

class VuePanelConfig(discord.ui.View):

    def __init__(self, guild_id):

        super().__init__(timeout=120)

        self.guild_id = guild_id

        self.add_item(
            MenuDeroulantConfiguration(guild_id)
        )


class MenuDeroulantConfiguration(discord.ui.Select):

    def __init__(self, guild_id):

        self.guild_id = guild_id

        options = [

            discord.SelectOption(
                label="Personnaliser les Teams",
                description="Modifier les équipes, salons, rôles et capacités.",
                emoji="✏️",
                value="custom_team"
            ),

            discord.SelectOption(
                label="Lier le Rôle Admin",
                description="Associer l'ID du rôle de modération de ce serveur.",
                emoji="🛡️",
                value="role_admin"
            ),

            discord.SelectOption(
                label="Raisons des Tickets",
                description="Modifier les choix du menu déroulant des tickets.",
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
                content=(
                    "🏆 **PERSONNALISATION DES TEAMS**\n\n"
                    "Utilisez les menus ci-dessous pour configurer "
                    "chaque équipe individuellement."
                ),
                view=VuePersonnalisationTeams(
                    interaction.guild_id
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
# --- PANEL DE PERSONNALISATION DES TEAMS ---
# ============================================================

class VuePersonnalisationTeams(discord.ui.View):

    def __init__(self, guild_id):

        super().__init__(timeout=180)

        self.guild_id = guild_id

        conf = obtenir_config_serveur(guild_id)

        teams = conf.get(
            "teams",
            {}
        )

        # --- MENU DEROUlant POUR CHAQUE TEAM ---
        for numero in sorted(
            teams.keys(),
            key=lambda x: int(x)
        ):

            self.add_item(
                MenuTeam(
                    guild_id,
                    int(numero)
                )
            )

        # --- BOUTON AJOUTER UNE TEAM ---
        self.add_item(
            BoutonAjouterTeam(guild_id)
        )


class MenuTeam(discord.ui.Select):

    def __init__(
        self,
        guild_id,
        numero_team
    ):

        self.guild_id = guild_id
        self.numero_team = numero_team

        conf = obtenir_config_serveur(
            guild_id
        )

        team = conf["teams"].get(
            str(numero_team),
            {}
        )

        nom_salon = team.get(
            "nom_salon",
            f"Team {numero_team}"
        )

        nom_role = team.get(
            "nom_role",
            f"Team {numero_team}"
        )

        max_joueurs = team.get(
            "max_joueurs",
            5
        )

        options = [

            discord.SelectOption(
                label=f"Numéro : {numero_team}",
                description="Modifier le numéro de la team.",
                emoji="🔢",
                value="numero"
            ),

            discord.SelectOption(
                label="Nom de la team",
                description=f"Actuel : {nom_salon[:90]}",
                emoji="🏆",
                value="nom_salon"
            ),

            discord.SelectOption(
                label="Nom du rôle",
                description=f"Actuel : {nom_role[:90]}",
                emoji="🎭",
                value="nom_role"
            ),

            discord.SelectOption(
                label="Nombre maximum de personnes",
                description=f"Maximum actuel : {max_joueurs}",
                emoji="👥",
                value="max_joueurs"
            )
        ]

        super().__init__(
            placeholder=f"⚙️ TEAM {numero_team}",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        choix = self.values[0]

        if choix == "numero":

            await interaction.response.send_modal(
                ModalModifierTeam(
                    self.guild_id,
                    self.numero_team,
                    "numero"
                )
            )

        elif choix == "nom_salon":

            await interaction.response.send_modal(
                ModalModifierTeam(
                    self.guild_id,
                    self.numero_team,
                    "nom_salon"
                )
            )

        elif choix == "nom_role":

            await interaction.response.send_modal(
                ModalModifierTeam(
                    self.guild_id,
                    self.numero_team,
                    "nom_role"
                )
            )

        elif choix == "max_joueurs":

            await interaction.response.send_modal(
                ModalModifierTeam(
                    self.guild_id,
                    self.numero_team,
                    "max_joueurs"
                )
            )


# ============================================================
# --- MODAL DE MODIFICATION D'UNE TEAM ---
# ============================================================

class ModalModifierTeam(
    discord.ui.Modal,
    title="Personnalisation Équipe ✏️"
):

    valeur = discord.ui.TextInput(
        label="Nouvelle valeur",
        placeholder="Entrez la nouvelle valeur...",
        required=True,
        max_length=100
    )

    def __init__(
        self,
        guild_id,
        numero_team,
        type_modification
    ):

        super().__init__()

        self.guild_id = guild_id
        self.numero_team = numero_team
        self.type_modification = type_modification

        if type_modification == "numero":

            self.valeur.label = "Nouveau numéro de la Team"
            self.valeur.placeholder = "Ex: 4"
            self.valeur.max_length = 2

        elif type_modification == "nom_salon":

            self.valeur.label = "Nouveau nom de la Team"
            self.valeur.placeholder = "Ex: 🏆︱𝐓𝐄𝐀𝐌-𝟒"

        elif type_modification == "nom_role":

            self.valeur.label = "Nouveau nom du Rôle"
            self.valeur.placeholder = "Ex: Team 4"

        elif type_modification == "max_joueurs":

            self.valeur.label = "Nombre maximum de personnes"
            self.valeur.placeholder = "Ex: 5"
            self.valeur.max_length = 3

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        conf = obtenir_config_serveur(
            self.guild_id
        )

        teams = conf["teams"]

        numero = str(
            self.numero_team
        )

        if numero not in teams:

            await interaction.response.send_message(
                "❌ Cette team n'existe plus.",
                ephemeral=True
            )

            return

        valeur = self.valeur.value.strip()

        # --- MODIFIER LE NUMERO ---
        if self.type_modification == "numero":

            try:

                nouveau_numero = int(valeur)

                if nouveau_numero < 1:
                    raise ValueError

                nouveau_numero_str = str(
                    nouveau_numero
                )

                if (
                    nouveau_numero_str != numero
                    and nouveau_numero_str in teams
                ):

                    await interaction.response.send_message(
                        "❌ Une team avec ce numéro existe déjà.",
                        ephemeral=True
                    )

                    return

                teams[nouveau_numero_str] = teams.pop(
                    numero
                )

                mettre_a_jour_config_serveur(
                    self.guild_id,
                    "teams",
                    teams
                )

                await interaction.response.send_message(
                    f"✅ **TEAM {numero}** est maintenant **TEAM {nouveau_numero}**.",
                    ephemeral=True
                )

            except:

                await interaction.response.send_message(
                    "❌ Veuillez entrer un numéro valide.",
                    ephemeral=True
                )

            return

        # --- MODIFIER LE NOM DU SALON ---
        if self.type_modification == "nom_salon":

            if not valeur:

                await interaction.response.send_message(
                    "❌ Le nom ne peut pas être vide.",
                    ephemeral=True
                )

                return

            teams[numero]["nom_salon"] = valeur

        # --- MODIFIER LE NOM DU ROLE ---
        elif self.type_modification == "nom_role":

            if not valeur:

                await interaction.response.send_message(
                    "❌ Le nom du rôle ne peut pas être vide.",
                    ephemeral=True
                )

                return

            teams[numero]["nom_role"] = valeur

        # --- MODIFIER LE MAXIMUM DE JOUEURS ---
        elif self.type_modification == "max_joueurs":

            try:

                maximum = int(valeur)

                if maximum < 1:
                    raise ValueError

                if maximum > 100:

                    await interaction.response.send_message(
                        "❌ Le maximum est de 100 joueurs.",
                        ephemeral=True
                    )

                    return

                teams[numero]["max_joueurs"] = maximum

            except:

                await interaction.response.send_message(
                    "❌ Veuillez entrer un nombre entier valide.",
                    ephemeral=True
                )

                return

        mettre_a_jour_config_serveur(
            self.guild_id,
            "teams",
            teams
        )

        await interaction.response.send_message(
            f"✅ **TEAM {numero}** a été mise à jour avec succès.",
            ephemeral=True
        )


# ============================================================
# --- AJOUTER UNE TEAM ---
# ============================================================

class BoutonAjouterTeam(
    discord.ui.Button
):

    def __init__(self, guild_id):

        self.guild_id = guild_id

        super().__init__(
            label="Ajouter une team",
            emoji="➕",
            style=discord.ButtonStyle.success,
            row=4
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        conf = obtenir_config_serveur(
            self.guild_id
        )

        teams = conf.get(
            "teams",
            {}
        )

        numeros = [
            int(x)
            for x in teams.keys()
            if str(x).isdigit()
        ]

        prochain_numero = (
            max(numeros) + 1
            if numeros
            else 1
        )

        await interaction.response.send_modal(
            ModalAjouterTeam(
                self.guild_id,
                prochain_numero
            )
        )


class ModalAjouterTeam(
    discord.ui.Modal,
    title="Ajouter une Team"
):

    nom_salon = discord.ui.TextInput(
        label="Nom de la Team / Salon",
        placeholder="Ex: 🏆︱𝐓𝐄𝐀𝐌-𝟒",
        required=True,
        max_length=100
    )

    nom_role = discord.ui.TextInput(
        label="Nom du Rôle",
        placeholder="Ex: Team 4",
        required=True,
        max_length=100
    )

    max_joueurs = discord.ui.TextInput(
        label="Nombre maximum de personnes",
        placeholder="Ex: 5",
        required=True,
        max_length=3
    )

    def __init__(
        self,
        guild_id,
        numero
    ):

        super().__init__()

        self.guild_id = guild_id
        self.numero = numero

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        try:

            maximum = int(
                self.max_joueurs.value.strip()
            )

            if maximum < 1 or maximum > 100:
                raise ValueError

        except:

            await interaction.response.send_message(
                "❌ Le maximum doit être un nombre entre 1 et 100.",
                ephemeral=True
            )

            return

        conf = obtenir_config_serveur(
            self.guild_id
        )

        teams = conf["teams"]

        numero = str(
            self.numero
        )

        teams[numero] = {

            "nom_salon":
                self.nom_salon.value.strip(),

            "nom_role":
                self.nom_role.value.strip(),

            "max_joueurs":
                maximum
        }

        mettre_a_jour_config_serveur(
            self.guild_id,
            "teams",
            teams
        )

        await interaction.response.send_message(
            f"✅ **TEAM {numero}** a été ajoutée avec succès !\n\n"
            f"🏆 Nom : **{self.nom_salon.value.strip()}**\n"
            f"🎭 Rôle : **{self.nom_role.value.strip()}**\n"
            f"👥 Maximum : **{maximum} joueurs**",
            ephemeral=True
        )


# ============================================================
# --- PANEL DE SAUVEGARDE EN SEQUENCE D'IDS ---
# ============================================================

class VueDataOptions(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=60)

    @discord.ui.button(
        label="GÉNÉRER UN CODE TEXTE 💾",
        style=discord.ButtonStyle.success
    )
    async def btn_generer_code(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
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
        interaction: discord.Interaction,
        button: discord.ui.Button
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
        interaction: discord.Interaction
    ):

        global classements_par_serveur

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

            if liste_ids:

                classements_par_serveur[
                    interaction.guild_id
                ] = list(liste_ids)

                await interaction.response.send_message(
                    "✅ **Séquence acceptée !** "
                    "Le bot met à jour les salons et les rôles en arrière-plan...",
                    ephemeral=True
                )

                asyncio.create_task(
                    rafraichir_partout(
                        interaction.guild
                    )
                )

            else:

                await interaction.response.send_message(
                    "❌ Séquence invalide. Aucun ID numérique trouvé.",
                    ephemeral=True
                )

        except Exception as e:

            await interaction.response.send_message(
                f"❌ Impossible de charger cette séquence : `{e}`",
                ephemeral=True
            )


# ============================================================
# --- INTERFACES DES POPUPS CLASSEMENT ---
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
        interaction: discord.Interaction
    ):

        global classements_par_serveur

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

            if (
                p_dep < 0
                or p_arr < 0
                or p_dep >= len(
                    classements_par_serveur[gid]
                )
                or p_arr >= len(
                    classements_par_serveur[gid]
                )
            ):
                return

            await interaction.response.defer(
                ephemeral=True
            )

            joueur_id = classements_par_serveur[gid].pop(
                p_dep
            )

            classements_par_serveur[gid].insert(
                p_arr,
                joueur_id
            )

            await interaction.followup.send(
                "📈 Déplacement effectué !",
                ephemeral=True
            )

            asyncio.create_task(
                rafraichir_partout(
                    interaction.guild
                )
            )

        except:
            pass


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
        interaction: discord.Interaction
    ):

        global classements_par_serveur

        gid = interaction.guild_id

        try:

            p1 = int(
                self.pos1.value
            ) - 1

            p2 = int(
                self.pos2.value
            ) - 1

            await interaction.response.defer(
                ephemeral=True
            )

            classements_par_serveur[gid][p1], \
            classements_par_serveur[gid][p2] = \
            classements_par_serveur[gid][p2], \
            classements_par_serveur[gid][p1]

            await interaction.followup.send(
                "🔄 Échange effectué !",
                ephemeral=True
            )

            asyncio.create_task(
                rafraichir_partout(
                    interaction.guild
                )
            )

        except:
            pass


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
        interaction: discord.Interaction
    ):

        global classements_par_serveur

        gid = interaction.guild_id

        try:

            p = int(
                self.pos_suppr.value
            ) - 1

            await interaction.response.defer(
                ephemeral=True
            )

            classements_par_serveur[gid].pop(p)

            await interaction.followup.send(
                "❌ Retiré !",
                ephemeral=True
            )

            asyncio.create_task(
                rafraichir_partout(
                    interaction.guild
                )
            )

        except:
            pass


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
        interaction: discord.Interaction,
        button: discord.ui.Button
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
        interaction: discord.Interaction,
        button: discord.ui.Button
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
        interaction: discord.Interaction,
        button: discord.ui.Button
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
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        conf = obtenir_config_serveur(
            interaction.guild_id
        )

        role_verif = discord.utils.get(
            interaction.user.roles,
            id=int(conf["role_admin_id"])
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
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        embed = discord.Embed(
            title="🤖 Guide des commandes",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="🛠️ Commandes Admin",
            value=(
                "`!setup`, `!add @membre`, "
                "`!addmany @m1 @m2...`, `!remove @membre`, "
                "`!tstart`, `!twin`, `!setup_ticket`, `!config`"
            ),
            inline=False
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


# ============================================================
# --- SECURE TICKET SYSTEM ---
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
        interaction: discord.Interaction,
        button: discord.ui.Button
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

    def __init__(self, guild_id):

        super().__init__(
            timeout=60
        )

        conf = obtenir_config_serveur(
            guild_id
        )

        options = [
            discord.SelectOption(
                label=m,
                value=m
            )
            for m in conf["motifs_tickets"]
        ]

        self.add_item(
            MenuDeroulantMotif(options)
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
        interaction: discord.Interaction
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

        except:

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
            int(conf["role_admin_id"])
        )

        if role_admin:

            overwrites[role_admin] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                view_channel=True
            )

        nom_salon = (
            f"🎫-"
            f"{motif_selectionne.lower().replace(' ', '-')}"
            f"-{interaction.user.name}"
        )

        try:

            salon_ticket = await guild.create_text_channel(
                name=nom_salon,
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
                    "Membres de l'équipe administrative va vous "
                    "prendre en charge. Décrivez votre demande."
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
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        conf = obtenir_config_serveur(
            interaction.guild_id
        )

        role_verif = discord.utils.get(
            interaction.user.roles,
            id=int(conf["role_admin_id"])
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
# --- REFRESH ET RÔLES DYNAMIQUES PAR SERVEUR ---
# ============================================================

async def rafraichir_partout(guild):

    global id_messages_principaux
    global id_salons_principaux
    global classements_par_serveur

    gid = guild.id

    if (
        gid not in id_salons_principaux
        or not id_salons_principaux[gid]
    ):
        return

    if gid not in classements_par_serveur:
        classements_par_serveur[gid] = []

    conf = obtenir_config_serveur(gid)

    teams = conf.get(
        "teams",
        {}
    )

    if not teams:
        return

    total_joueurs = len(
        classements_par_serveur[gid]
    )

    max_team = max(
        int(numero)
        for numero in teams.keys()
    )

    # ========================================================
    # --- RETIRER LES ANCIENS ROLES DES JOUEURS ---
    # ========================================================

    roles_a_gerer = []

    for numero in teams.keys():

        nom_role = obtenir_nom_role_team(
            guild,
            int(numero)
        )

        role = discord.utils.get(
            guild.roles,
            name=nom_role
        )

        if role:
            roles_a_gerer.append(role)

    for member in guild.members:

        if member.id not in classements_par_serveur[gid]:

            roles_mauvais = [
                role
                for role in member.roles
                if role in roles_a_gerer
            ]

            if roles_mauvais:

                try:

                    await member.remove_roles(
                        *roles_mauvais
                    )

                except:

                    pass

    # ========================================================
    # --- CREATION DES ROLES ET SALONS ---
    # ========================================================

    for num_team in range(
        1,
        max_team + 1
    ):

        if str(num_team) not in teams:
            continue

        nom_role = obtenir_nom_role_team(
            guild,
            num_team
        )

        nom_salon_stylise = obtenir_nom_salon_team(
            guild,
            num_team
        )

        if not discord.utils.get(
            guild.roles,
            name=nom_role
        ):

            try:

                await guild.create_role(
                    name=nom_role
                )

            except:

                pass

        salon_existe = any(
            normaliser_nom_salon(c.name)
            ==
            normaliser_nom_salon(
                nom_salon_stylise
            )
            for c in guild.channels
        )

        if not salon_existe:

            try:

                await guild.create_text_channel(
                    name=nom_salon_stylise
                )

            except:

                pass

    # ========================================================
    # --- ATTRIBUTION DES ROLES ---
    # ========================================================

    for index, user_id in enumerate(
        classements_par_serveur[gid]
    ):

        pos = index + 1

        team_cible = obtenir_equipe_et_salon_dynamique(
            gid,
            pos
        )

        try:

            member = await guild.fetch_member(
                user_id
            )

        except:

            member = None

        if member:

            # --- RETIRER TOUS LES ROLES TEAM ACTUELS ---
            for numero in teams.keys():

                ancien_nom_role = obtenir_nom_role_team(
                    guild,
                    int(numero)
                )

                ancien_role = discord.utils.get(
                    guild.roles,
                    name=ancien_nom_role
                )

                if (
                    ancien_role
                    and ancien_role in member.roles
                    and int(numero) != team_cible
                ):

                    try:

                        await member.remove_roles(
                            ancien_role
                        )

                    except:

                        pass

            # --- AJOUTER LE BON ROLE ---
            nom_role_cible = obtenir_nom_role_team(
                guild,
                team_cible
            )

            role_bon = discord.utils.get(
                guild.roles,
                name=nom_role_cible
            )

            if role_bon and role_bon not in member.roles:

                try:

                    await member.add_roles(
                        role_bon
                    )

                except:

                    pass

    # ========================================================
    # --- AFFICHAGE DU CLASSEMENT GENERAL ---
    # ========================================================

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

            for index, u_id in enumerate(
                classements_par_serveur[gid]
            ):

                texte_top += (
                    f"**Top {index + 1}** : "
                    f"<@{u_id}>\n"
                )

        msg_envoye = False

        if (
            gid in id_messages_principaux
            and id_messages_principaux[gid]
        ):

            try:

                msg = await salon_top.fetch_message(
                    id_messages_principaux[gid]
                )

                await msg.edit(
                    content=texte_top,
                    view=VueControleTop()
                )

                msg_envoye = True

            except:

                pass

        if not msg_envoye:

            msg = await salon_top.send(
                content=texte_top,
                view=VueControleTop()
            )

            id_messages_principaux[gid] = msg.id

    # ========================================================
    # --- AFFICHAGE DES TEAMS ---
    # ========================================================

    for num_team in range(
        1,
        max_team + 1
    ):

        if str(num_team) not in teams:
            continue

        nom_salon_stylise = obtenir_nom_salon_team(
            guild,
            num_team
        )

        salon_team = discord.utils.find(
            lambda c:
                normaliser_nom_salon(c.name)
                ==
                normaliser_nom_salon(
                    nom_salon_stylise
                ),
            guild.channels
        )

        if salon_team:

            try:

                await salon_team.purge(
                    limit=50
                )

            except:

                pass

            lignes = []

            for i, uid in enumerate(
                classements_par_serveur[gid]
            ):

                if (
                    obtenir_equipe_et_salon_dynamique(
                        gid,
                        i + 1
                    )
                    == num_team
                ):

                    lignes.append(
                        f"**Top {i + 1}** : <@{uid}>"
                    )

            titre_affichage = obtenir_nom_role_team(
                guild,
                num_team
            ).upper()

            try:

                if lignes:

                    await salon_team.send(
                        f"🏆 **Membres - {titre_affichage}** 🏆\n\n"
                        + "\n".join(lignes)
                    )

                else:

                    await salon_team.send(
                        f"Aucun joueur assigné au "
                        f"{titre_affichage} actuellement."
                    )

            except:

                pass


# ============================================================
# --- LOGIQUE DU MODE TOURNOI FLASH ---
# ============================================================

tournois_par_serveur = {}


def generer_affichage_tournoi(gid):

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

        for index, u_id in enumerate(
            t["inscrits"]
        ):

            texte += (
                f"{index + 1}. <@{u_id}>\n"
            )

        return texte

    texte += (
        "◽ **QUARTS DE FINALE** ◽\n"
    )

    for m in range(1, 5):

        if (
            f"Q{m}" in t["matchs"]
            and len(
                t["matchs"][f"Q{m}"]
            ) > 0
        ):

            p1 = (
                f"<@{t['matchs'][f'Q{m}'][0]}>"
            )

        else:

            p1 = "À définir"

        if (
            f"Q{m}" in t["matchs"]
            and len(
                t["matchs"][f"Q{m}"]
            ) > 1
        ):

            p2 = (
                f"<@{t['matchs'][f'Q{m}'][1]}>"
            )

        else:

            p2 = "À définir"

        if f"Q{m}" in t["vainqueurs"]:

            v = (
                f"🏅 Vainqueur : "
                f"<@{t['vainqueurs'][f'Q{m}']}>"
            )

        else:

            v = "En attente..."

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
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        global tournois_par_serveur

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
                    t["inscrits"][(m - 1) * 2],
                    t["inscrits"][(m - 1) * 2 + 1]
                ]

            await interaction.message.edit(
                content=generer_affichage_tournoi(gid),
                view=None
            )

        else:

            await interaction.message.edit(
                content=generer_affichage_tournoi(gid),
                view=self
            )

        await interaction.response.defer()


# ============================================================
# --- COMMANDES ADMIN ---
# ============================================================

@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def initialiser_salon_top(ctx):

    global id_salons_principaux
    global id_messages_principaux
    global classements_par_serveur

    classements_par_serveur[
        ctx.guild.id
    ] = []

    id_salons_principaux[
        ctx.guild.id
    ] = ctx.channel.id

    id_messages_principaux[
        ctx.guild.id
    ] = None

    await ctx.message.delete()

    await rafraichir_partout(
        ctx.guild
    )


@bot.command(name="config")
@commands.has_permissions(administrator=True)
async def ouvrir_menu_config(ctx):

    await ctx.message.delete()

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

    global classements_par_serveur

    gid = ctx.guild.id

    if gid not in classements_par_serveur:

        classements_par_serveur[gid] = []

    if membre.id not in classements_par_serveur[gid]:

        classements_par_serveur[gid].append(
            membre.id
        )

    await ctx.message.delete()

    await rafraichir_partout(
        ctx.guild
    )


@bot.command(name="addmany")
@commands.has_permissions(administrator=True)
async def ajouter_plusieurs_joueurs(
    ctx,
    *membres: discord.Member
):

    global classements_par_serveur

    gid = ctx.guild.id

    if gid not in classements_par_serveur:

        classements_par_serveur[gid] = []

    for membre in membres:

        if membre.id not in classements_par_serveur[gid]:

            classements_par_serveur[gid].append(
                membre.id
            )

    await ctx.message.delete()

    await rafraichir_partout(
        ctx.guild
    )


@bot.command(name="remove")
@commands.has_permissions(administrator=True)
async def supprimer_joueur_txt(
    ctx,
    membre: discord.Member
):

    global classements_par_serveur

    gid = ctx.guild.id

    if (
        gid in classements_par_serveur
        and membre.id in classements_par_serveur[gid]
    ):

        classements_par_serveur[gid].remove(
            membre.id
        )

    await ctx.message.delete()

    await rafraichir_partout(
        ctx.guild
    )


@bot.command(name="tstart")
@commands.has_permissions(administrator=True)
async def lancer_inscriptions_tournoi(ctx):

    global tournois_par_serveur

    gid = ctx.guild.id

    tournois_par_serveur[gid] = {
        "inscrits": [],
        "etape": "inscriptions",
        "matchs": {},
        "vainqueurs": {},
        "msg_id": None
    }

    await ctx.message.delete()

    msg = await ctx.send(
        content=generer_affichage_tournoi(gid),
        view=VueInscriptionTournoi()
    )

    tournois_par_serveur[gid]["msg_id"] = msg.id


@bot.command(name="twin")
@commands.has_permissions(administrator=True)
async def valider_gagnant_match(
    ctx,
    code_match: str,
    membre: discord.Member
):

    global tournois_par_serveur

    gid = ctx.guild.id

    if gid not in tournois_par_serveur:
        return

    t = tournois_par_serveur[gid]

    code_match = code_match.upper()

    t["vainqueurs"][code_match] = membre.id

    await ctx.message.delete()

    try:

        msg = await ctx.channel.fetch_message(
            t["msg_id"]
        )

        await msg.edit(
            content=generer_affichage_tournoi(gid)
        )

    except:

        pass


@bot.command(name="setup_ticket")
@commands.has_permissions(administrator=True)
async def envoyer_panneau_ticket(ctx):

    await ctx.message.delete()

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
# --- BOT READY ---
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

    print(
        f"Bot en ligne : {bot.user.name}"
    )


# ============================================================
# --- START BOT ---
# ============================================================

keep_alive()

bot.run(
    os.environ.get("DISCORD_TOKEN")
)
