import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import os


# =========================
# SERVEUR WEB KEEP-ALIVE
# =========================

app = Flask("")


@app.route("/")
def home():
    return "Bot de classement actif !"


def run_web_server():
    app.run(host="0.0.0.0", port=10000)


def keep_alive():
    Thread(target=run_web_server, daemon=True).start()


# =========================
# CONFIGURATION DU BOT
# =========================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# =========================
# STOCKAGE DES DONNÉES
# =========================

classement_top = []
id_message_principal = None
id_salon_principal = None


# =========================
# NOMS DES SALONS
# =========================

def obtenir_nom_salon_team(num_team):
    noms_speciaux = {
        1: "𝐌𝐀𝐈𝐍 𝐑𝐎𝐒𝐓𝐄𝐑",
        2: "︱𝐓𝐄𝐀𝐌-𝟐",
        3: "︱𝐓𝐄𝐀𝐌-𝟑",
        4: "︱𝐓𝐄𝐀𝐌-𝟒",
        5: "︱𝐓𝐄𝐀𝐌-𝟓",
        6: "︱𝐓𝐄𝐀𝐌-𝟔",
        7: "︱𝐓𝐄𝐀𝐌-𝟕",
        8: "︱𝐓𝐄𝐀𝐌-𝟖",
    }

    return noms_speciaux.get(
        num_team,
        f"︱𝐓𝐄𝐀𝐌-{num_team}"
    )


def obtenir_equipe_et_salon(position):
    if position <= 5:
        return 1

    return 2 + (position - 6) // 6


# =========================
# RAFRAÎCHISSEMENT COMPLET
# =========================

async def rafraichir_partout(guild):
    global id_message_principal, id_salon_principal

    if not id_salon_principal:
        return

    total_joueurs = len(classement_top)

    max_team = (
        obtenir_equipe_et_salon(total_joueurs)
        if total_joueurs > 0
        else 1
    )

    # -------------------------
    # 1. Nettoyage des rôles
    # -------------------------

    for member in guild.members:
        if member.id not in classement_top:
            roles_mauvais = [
                role
                for role in member.roles
                if role.name.startswith("Team ")
            ]

            if roles_mauvais:
                try:
                    await member.remove_roles(*roles_mauvais)
                except discord.Forbidden:
                    pass

    # -------------------------
    # 2. Création des rôles
    #    et salons manquants
    # -------------------------

    for num_team in range(1, max_team + 1):
        nom_role = f"Team {num_team}"
        nom_salon_stylise = obtenir_nom_salon_team(num_team)

        role = discord.utils.get(
            guild.roles,
            name=nom_role
        )

        if role is None:
            try:
                await guild.create_role(name=nom_role)
            except discord.Forbidden:
                pass

        salon_existe = any(
            channel.name.casefold() == nom_salon_stylise.casefold()
            for channel in guild.channels
        )

        if not salon_existe:
            try:
                await guild.create_text_channel(
                    name=nom_salon_stylise
                )
            except discord.Forbidden:
                pass

    # -------------------------
    # 3. Mise à jour des rôles
    # -------------------------

    for index, user_id in enumerate(classement_top):
        position = index + 1
        team_cible = obtenir_equipe_et_salon(position)

        member = guild.get_member(user_id)

        if member is None:
            continue

        role_bon = discord.utils.get(
            guild.roles,
            name=f"Team {team_cible}"
        )

        roles_mauvais = [
            role
            for role in member.roles
            if role.name.startswith("Team ")
            and role != role_bon
        ]

        if roles_mauvais:
            try:
                await member.remove_roles(*roles_mauvais)
            except discord.Forbidden:
                pass

        if role_bon and role_bon not in member.roles:
            try:
                await member.add_roles(role_bon)
            except discord.Forbidden:
                pass

    # -------------------------
    # 4. Mise à jour du classement général
    # -------------------------

    salon_top = guild.get_channel(id_salon_principal)

    if salon_top:
        texte_top = "🏆 **CLASSEMENT GÉNÉRAL COMPLET** 🏆\n\n"

        if not classement_top:
            texte_top += "Aucun joueur dans le top pour le moment."
        else:
            for index, user_id in enumerate(classement_top):
                texte_top += f"**Top {index + 1} :** <@{user_id}>\n"

        view = VueControleTop()

        if id_message_principal:
            try:
                msg = await salon_top.fetch_message(
                    id_message_principal
                )

                await msg.edit(
                    content=texte_top,
                    view=view
                )

            except discord.NotFound:
                msg = await salon_top.send(
                    content=texte_top,
                    view=view
                )

                id_message_principal = msg.id

        else:
            msg = await salon_top.send(
                content=texte_top,
                view=view
            )

            id_message_principal = msg.id

    # -------------------------
    # 5. Mise à jour des salons Teams
    # -------------------------

    for num_team in range(1, max_team + 1):

        nom_salon_stylise = obtenir_nom_salon_team(num_team)

        salon_team = discord.utils.find(
            lambda channel:
                channel.name.casefold()
                == nom_salon_stylise.casefold(),
            guild.channels
        )

        if salon_team is None:
            continue

        try:
            await salon_team.purge(limit=50)
        except (discord.Forbidden, discord.HTTPException):
            pass

        lignes = [
            f"**Top {i + 1} :** <@{uid}>"
            for i, uid in enumerate(classement_top)
            if obtenir_equipe_et_salon(i + 1) == num_team
        ]

        if lignes:
            texte_team = (
                f"👥 **Membres - Team {num_team}**\n\n"
                + "\n".join(lignes)
            )
        else:
            texte_team = (
                f"**Aucun joueur assigné à la Team {num_team} "
                "actuellement.**"
            )

        try:
            await salon_team.send(texte_team)
        except discord.Forbidden:
            pass


# =========================
# MODAL : DÉPLACER UN JOUEUR
# =========================

class FenetreDeplacement(
    discord.ui.Modal,
    title="Changer la place (Décaler)"
):

    pos_depart = discord.ui.TextInput(
        label="Position actuelle du joueur",
        placeholder="Ex: 5"
    )

    pos_arrivee = discord.ui.TextInput(
        label="Sa nouvelle position voulue",
        placeholder="Ex: 2"
    )

    async def on_submit(self, interaction: discord.Interaction):
        global classement_top

        try:
            p_dep = int(self.pos_depart.value) - 1
            p_arr = int(self.pos_arrivee.value) - 1

            if (
                p_dep < 0
                or p_arr < 0
                or p_dep >= len(classement_top)
                or p_arr >= len(classement_top)
            ):
                await interaction.response.send_message(
                    "❌ Positions invalides.",
                    ephemeral=True
                )
                return

            joueur_id = classement_top.pop(p_dep)
            classement_top.insert(p_arr, joueur_id)

            await interaction.response.send_message(
                "✅ Déplacement effectué !",
                ephemeral=True
            )

            await rafraichir_partout(interaction.guild)

        except ValueError:
            await interaction.response.send_message(
                "❌ Veuillez entrer des nombres entiers.",
                ephemeral=True
            )


# =========================
# MODAL : ÉCHANGER 2 JOUEURS
# =========================

class FenetreEchange(
    discord.ui.Modal,
    title="Échanger 2 places (Permuter)"
):

    pos1 = discord.ui.TextInput(
        label="Position du 1er joueur",
        placeholder="Ex: 2"
    )

    pos2 = discord.ui.TextInput(
        label="Position du 2ème joueur",
        placeholder="Ex: 5"
    )

    async def on_submit(self, interaction: discord.Interaction):
        global classement_top

        try:
            p1 = int(self.pos1.value) - 1
            p2 = int(self.pos2.value) - 1

            if (
                p1 < 0
                or p2 < 0
                or p1 >= len(classement_top)
                or p2 >= len(classement_top)
            ):
                await interaction.response.send_message(
                    "❌ Positions invalides.",
                    ephemeral=True
                )
                return

            classement_top[p1], classement_top[p2] = (
                classement_top[p2],
                classement_top[p1]
            )

            await interaction.response.send_message(
                "✅ Échange effectué !",
                ephemeral=True
            )

            await rafraichir_partout(interaction.guild)

        except ValueError:
            await interaction.response.send_message(
                "❌ Veuillez entrer des nombres entiers.",
                ephemeral=True
            )


# =========================
# MODAL : SUPPRIMER UN JOUEUR
# =========================

class FenetreSuppression(
    discord.ui.Modal,
    title="Retirer un joueur du Top"
):

    pos_suppr = discord.ui.TextInput(
        label="Position du joueur à supprimer",
        placeholder="Ex: 3"
    )

    async def on_submit(self, interaction: discord.Interaction):
        global classement_top

        try:
            position = int(self.pos_suppr.value) - 1

            if position < 0 or position >= len(classement_top):
                await interaction.response.send_message(
                    "❌ Position invalide.",
                    ephemeral=True
                )
                return

            classement_top.pop(position)

            await interaction.response.send_message(
                "✅ Joueur retiré avec succès !",
                ephemeral=True
            )

            await rafraichir_partout(interaction.guild)

        except ValueError:
            await interaction.response.send_message(
                "❌ Veuillez entrer un nombre valide.",
                ephemeral=True
            )
# =========================
# INTERFACE DES BOUTONS
# =========================

class VueControleTop(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Changer de place",
        style=discord.ButtonStyle.primary,
        custom_id="btn_deplace"
    )
    async def bouton_deplace(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
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
        custom_id="btn_echange"
    )
    async def bouton_echange(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
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
        custom_id="btn_suppr"
    )
    async def bouton_supprime(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
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


# =========================
# COMMANDES ADMIN
# =========================

@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def initialiser_salon_top(ctx):
    global id_salon_principal
    global id_message_principal

    id_salon_principal = ctx.channel.id
    id_message_principal = None

    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    await rafraichir_partout(ctx.guild)


@bot.command(name="add")
@commands.has_permissions(administrator=True)
async def ajouter_joueur(
    ctx,
    membre: discord.Member
):
    global classement_top

    if membre.id in classement_top:
        await ctx.send(
            f"⚠️ {membre.mention} est déjà dans le classement.",
            delete_after=4
        )

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        return

    classement_top.append(membre.id)

    await ctx.send(
        f"✅ {membre.mention} ajouté en fin de liste.",
        delete_after=3
    )

    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    await rafraichir_partout(ctx.guild)


# =========================
# NOUVELLE COMMANDE : ADDMANY
# =========================

@bot.command(name="addmany")
@commands.has_permissions(administrator=True)
async def ajouter_plusieurs_joueurs(
    ctx,
    *membres: discord.Member
):
    global classement_top

    if not membres:
        await ctx.send(
            "❌ Tu dois mentionner au moins un joueur.\n\n"
            "Exemple :\n"
            "`!addmany @Joueur1 @Joueur2 @Joueur3`",
            delete_after=6
        )
        return

    ajoutes = []
    deja_presents = []

    for membre in membres:

        if membre.id not in classement_top:
            classement_top.append(membre.id)
            ajoutes.append(membre)
        else:
            deja_presents.append(membre)

    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    message = ""

    if ajoutes:
        mentions_ajoutes = " ".join(
            membre.mention
            for membre in ajoutes
        )

        message += (
            f"✅ **{len(ajoutes)} joueur(s) ajouté(s) :**\n"
            f"{mentions_ajoutes}"
        )

    if deja_presents:
        mentions_existants = " ".join(
            membre.mention
            for membre in deja_presents
        )

        if message:
            message += "\n\n"

        message += (
            f"⚠️ **Déjà dans le classement :**\n"
            f"{mentions_existants}"
        )

    await ctx.send(
        message,
        delete_after=6
    )

    await rafraichir_partout(ctx.guild)


@bot.command(name="remove")
@commands.has_permissions(administrator=True)
async def supprimer_joueur_txt(
    ctx,
    membre: discord.Member
):
    global classement_top

    if membre.id in classement_top:
        classement_top.remove(membre.id)

        await ctx.send(
            f"✅ {membre.mention} retiré.",
            delete_after=3
        )

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        await rafraichir_partout(ctx.guild)

    else:
        await ctx.send(
            "⚠️ Ce joueur n'est pas dans le top.",
            delete_after=3
        )


# =========================
# GESTION DES ERREURS
# =========================

@ajouter_joueur.error
@ajouter_plusieurs_joueurs.error
@supprimer_joueur_txt.error
async def erreur_commande_joueur(
    ctx,
    error
):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            "❌ Tu dois être administrateur pour utiliser cette commande.",
            delete_after=5
        )

    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            "❌ Tu dois mentionner un ou plusieurs joueurs.",
            delete_after=5
        )

    elif isinstance(error, commands.MemberNotFound):
        await ctx.send(
            "❌ Un des joueurs indiqués est introuvable.",
            delete_after=5
        )

    else:
        print(f"Erreur de commande : {error}")


# =========================
# BOT PRÊT
# =========================

@bot.event
async def on_ready():
    print(f"Bot en ligne : {bot.user.name}")
    print(f"ID du bot : {bot.user.id}")


# =========================
# LANCEMENT
# =========================

keep_alive()

token = os.environ.get("DISCORD_TOKEN")

if not token:
    raise RuntimeError(
        "La variable d'environnement DISCORD_TOKEN est introuvable."
    )

bot.run(token)
