import discord
from discord.ext import commands
import asyncio
from flask import Flask
from threading import Thread
import os
import json

# --- SERVER WEB KEEP-ALIVE ---
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

ROLE_ADMIN_ID = 1529373902969770094
FICHIER_SAUVEGARDE = "sauvegardes_top.json"

def charger_sauvegardes():
    if not os.path.exists(FICHIER_SAUVEGARDE):
        return {}
    try:
        with open(FICHIER_SAUVEGARDE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def enregistrer_sauvegardes(data):
    with open(FICHIER_SAUVEGARDE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def obtenir_nom_salon_team(num_team):
    noms_speciaux = {
        1: "🏅𝐌𝐀𝐈𝐍 𝐑𝐎𝐒𝐓𝐄𝐑🏅",
        2: "🥈︱𝐓𝐄𝐀𝐌-𝟐🥈",
        3: "🥉︱𝐓𝐄𝐀𝐌-𝟑🥉",
        4: "🎖︱𝐓𝐄𝐀𝐌-𝟒🎖",
        5: "🏆︱𝐓𝐄𝐀𝐌-𝟓🏆",
        6: "🎗︱𝐓𝐄𝐀𝐌-𝟔🎗",
        7: "✨︱𝐓𝐄𝐀𝐌-𝟕✨",
        8: "🎫︱𝐓𝐄𝐀𝐌-𝟖🎫"
    }
    return noms_speciaux.get(num_team, f"💫︱𝐓𝐄𝐀𝐌-{num_team}💫")

def obtenir_nom_role_team(num_team):
    if num_team == 1:
        return "Main Roster"
    return f"Team {num_team}"

def obtenir_equipe_et_salon(position):
    if position <= 5: 
        return 1
    return 2 + (position - 6) // 6

def normaliser_nom_salon(nom):
    return nom.lower().replace("-", "").replace(" ", "").replace("\ufe0f", "")

# --- LOGIQUE DE SAUVEGARDE & RESTAURATION DATA ---
class VueDataOptions(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="ENREGISTRER 💾", style=discord.ButtonStyle.success)
    async def btn_enregistrer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FenetreNomSauvegarde())

    @discord.ui.button(label="BASE DONNÉE 📂", style=discord.ButtonStyle.primary)
    async def btn_base_donnee(self, interaction: discord.Interaction, button: discord.ui.Button):
        sauvegardes = charger_sauvegardes()
        if not sauvegardes:
            await interaction.response.send_message("ℹ️ Aucune sauvegarde enregistrée.", ephemeral=True)
            return
        await interaction.response.send_message("📂 Sélectionnez une sauvegarde :", view=VueListeSauvegardes(sauvegardes), ephemeral=True)

class FenetreNomSauvegarde(discord.ui.Modal, title="Nommer l'enregistrement"):
    nom_save = discord.ui.TextInput(label="Nom de la sauvegarde", placeholder="Ex: Fin_Semaine_1")

    async def on_submit(self, interaction: discord.Interaction):
        global classement_top
        nom = self.nom_save.value.strip().replace(" ", "_")
        if not nom:
            await interaction.response.send_message("❌ Nom invalide.", ephemeral=True)
            return
        sauvegardes = charger_sauvegardes()
        sauvegardes[nom] = list(classement_top)
        enregistrer_sauvegardes(sauvegardes)
        await interaction.response.send_message(f"💾 Enregistré sous : `{nom}`", ephemeral=True)

class VueListeSauvegardes(discord.ui.View):
    def __init__(self, sauvegardes):
        super().__init__(timeout=60)
        options = [discord.SelectOption(label=nom, description=f"{len(liste)} joueurs", value=nom) for nom, liste in sauvegardes.items()]
        self.add_item(MenuDeroulantSauvegardes(options))

class MenuDeroulantSauvegardes(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Choisissez une sauvegarde...", options=options)

    async def callback(self, interaction: discord.Interaction):
        nom_selectionne = self.values
        await interaction.response.send_message(content=f"⚙️ Options pour `{nom_selectionne}`", view=VueActionSauvegarde(nom_selectionne), ephemeral=True)

class VueActionSauvegarde(discord.ui.View):
    def __init__(self, nom_sauvegarde):
        super().__init__(timeout=60)
        self.nom_sauvegarde = nom_sauvegarde

    @discord.ui.button(label="RESTAURER 🔄", style=discord.ButtonStyle.danger)
    async def btn_restaurer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(content=f"⚠️ Charger `{self.nom_sauvegarde}` ? Écrase le Top actuel.", view=VueConfirmationRestauration(self.nom_sauvegarde), ephemeral=True)

    @discord.ui.button(label="SUPPRIMER 🗑️", style=discord.ButtonStyle.secondary)
    async def btn_supprimer_save(self, interaction: discord.Interaction, button: discord.ui.Button):
        sauvegardes = charger_sauvegardes()
        if self.nom_sauvegarde in sauvegardes:
            del sauvegardes[self.nom_sauvegarde]
            enregistrer_sauvegardes(sauvegardes)
            await interaction.response.send_message(f"🗑️ `{self.nom_sauvegarde}` supprimé.", ephemeral=True)

class VueConfirmationRestauration(discord.ui.View):
    def __init__(self, nom_sauvegarde):
        super().__init__(timeout=30)
        self.nom_sauvegarde = nom_sauvegarde

    @discord.ui.button(label="OUI, ACCEPTER 🛠️", style=discord.ButtonStyle.danger)
    async def btn_oui(self, interaction: discord.Interaction, button: discord.ui.Button):
        global classement_top
        sauvegardes = charger_sauvegardes()
        if self.nom_sauvegarde in sauvegardes:
            classement_top = list(sauvegardes[self.nom_sauvegarde])
            await interaction.response.send_message(f"✅ Configuration `{self.nom_sauvegarde}` active !", ephemeral=True)
            await rafraichir_partout(interaction.guild)
        else:
            await interaction.response.send_message("❌ Sauvegarde introuvable.", ephemeral=True)

    @discord.ui.button(label="NON, ANNULER ❌", style=discord.ButtonStyle.secondary)
    async def btn_non(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Annulé.", ephemeral=True)

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

    @discord.ui.button(label="DATA 🗄️", style=discord.ButtonStyle.danger, custom_id="btn_data_panel")
    async def bouton_data_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        role_verif = discord.utils.get(interaction.user.roles, id=ROLE_ADMIN_ID)
        if not role_verif and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Accès refusé. Rôle ADMIN requis.", ephemeral=True)
            return
        await interaction.response.send_message(content="🗄️ **Gestion de la Base de Données**", view=VueDataOptions(), ephemeral=True)

    @discord.ui.button(label="Liste des Commandes ❓", style=discord.ButtonStyle.success, custom_id="btn_help")
    async def bouton_aide(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🤖 Guide des commandes", color=discord.Color.gold())
        embed.add_field(name="🛠️ Commandes Admin", value="`!setup`, `!add @membre`, `!addmany @m1 @m2...`, `!remove @membre`, `!tstart`, `!twin`, `!setup_ticket`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# --- SYSTÈME DE TICKETS DYNAMIQUE ET MULTI-SERVEUR ---
class VueCreationTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Créer un ticket 🎫", style=discord.ButtonStyle.primary, custom_id="btn_creer_ticket")
    async def bouton_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(content="📋 **Sélectionnez le motif de votre ticket :**", view=VueChoixMotifTicket(), ephemeral=True)

class VueChoixMotifTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        options = [
            discord.SelectOption(label="Parler à un Admin 👑", value="Admin"),
            discord.SelectOption(label="Test Team ⚔️", value="Test Team"),
            discord.SelectOption(label="Tryout 🐒", value="Tryout")
        ]
        self.add_item(MenuDeroulantMotif(options))

class MenuDeroulantMotif(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Choisissez la raison du ticket...", options=options)

    async def callback(self, interaction: discord.Interaction):
        motif_selectionne = self.values[0] # Extraction textuelle sécurisée multi-serveur
        guild = interaction.guild
        
        # RECHERCHE OU CRÉATION AUTOMATIQUE DE LA CATÉGORIE DU SERVEUR
        categorie = discord.utils.find(lambda c: c.name.upper() == "🎫 𝙏𝙄𝘾𝙆𝙀𝙏" and isinstance(c, discord.CategoryChannel), guild.channels)
        if not categorie:
            try:
                categorie = await guild.create_category(name="🎫 𝙏𝙄𝘾𝙆𝙀𝙏")
            except Exception as e:
                await interaction.response.send_message(f"❌ Impossible de créer la catégorie automatique : `{e}`", ephemeral=True)
                return

        membre_createur = interaction.user
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False, view_channel=False),
            membre_createur: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, view_channel=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, view_channel=True)
        }
        
        # Liaison dynamique : cherche par rôle ID si présent, sinon ajoute le créateur et l'administrateur système du serveur courant
        role_admin = guild.get_role(ROLE_ADMIN_ID)
        if role_admin: 
            overwrites[role_admin] = discord.PermissionOverwrite(read_messages=True, send_messages=True, view_channel=True)

        nom_salon = f"🎫-{motif_selectionne.lower().replace(' ', '-')}-{interaction.user.name}"
        try:
            salon_ticket = await guild.create_text_channel(name=nom_salon, category=categorie, overwrites=overwrites)
            await interaction.response.send_message(f"✅ Ticket ouvert dans {salon_ticket.mention} !", ephemeral=True)

            embed = discord.Embed(
                title=f"🎫 Ticket - {motif_selectionne}",
                description=f"Bonjour {interaction.user.mention},\n\nMerci d'avoir ouvert un ticket pour : **{motif_selectionne}**.\nL'équipe administrative va vous prendre en charge. Veuillez décrire votre demande.",
                color=discord.Color.blue()
            )
            await salon_ticket.send(embed=embed, view=VueFermetureTicket())
        except Exception as e:
            await interaction.response.send_message(f"❌ Échec de création du salon : `{e}`", ephemeral=True)

class VueFermetureTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fermer le ticket 🔒", style=discord.ButtonStyle.danger, custom_id="btn_fermer_ticket")
    async def bouton_fermer(self, interaction: discord.Interaction, button: discord.ui.Button):
        role_verif = discord.utils.get(interaction.user.roles, id=ROLE_ADMIN_ID)
        if not role_verif and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Seul un administrateur peut fermer ce ticket.", ephemeral=True)
            return
        await interaction.response.send_message("🔒 **Fermeture et suppression du salon dans 5 secondes.**")
        await asyncio.sleep(5)
        await interaction.channel.delete()

async def rafraichir_partout(guild):
    global id_message_principal, id_salon_principal
    if not id_salon_principal: return

    total_joueurs = len(classement_top)
    max_team = obtenir_equipe_et_salon(total_joueurs) if total_joueurs > 0 else 1

    for member in guild.members:
        if member.id not in classement_top:
            roles_mauvais = [r for r in member.roles if r.name.startswith("Team ") or r.name == "Main Roster"]
            if roles_mauvais: 
                try: await member.remove_roles(*roles_mauvais)
                except: pass

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

    for index, user_id in enumerate(classement_top):
        pos = index + 1
        team_cible = obtenir_equipe_et_salon(pos)
        try: member = await guild.fetch_member(user_id)
        except: member = None
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

    salon_top = guild.get_channel(id_salon_principal)
    if salon_top:
        texte_top = "🏆 **CLASSEMENT GÉNÉRAL COMPLET** 🏆\n\n"
        if not classement_top: texte_top += "*Aucun joueur dans le top pour le moment.*"
        for index, u_id in enumerate(classement_top): texte_top += f"**Top {index + 1}** : <@{u_id}>\n"
        
        if id_message_principal:
            try:
                msg = await salon_top.fetch_message(id_message_principal)
                await msg.edit(content=texte_top, view=VueControleTop())
            except:
                msg = await salon_top.send(content=texte_top, view=VueControleTop())
                id_message_principal = msg.id
        else:
            msg = await salon_top.send(content=texte_top, view=VueControleTop())
            id_message_principal = msg.id

    for num_team in range(1, max_team + 1):
        nom_salon_stylise = obtenir_nom_salon_team(num_team)
        salon_team = discord.utils.find(lambda c: normaliser_nom_salon(c.name) == normaliser_nom_salon(nom_salon_stylise), guild.channels)
        if salon_team:
            try: await salon_team.purge(limit=50)
            except: pass
            lignes = [f"**Top {i+1}** : <@{uid}>" for i, uid in enumerate(classement_top) if obtenir_equipe_et_salon(i+1) == num_team]
            titre_affichage = "MAIN ROSTER" if num_team == 1 else f"Team {num_team}"
            try:
                if lignes: await salon_team.send(f"🏆 **Membres - {titre_affichage}** 🏆\n\n" + "\n".join(lignes))
                else: await salon_team.send(f"Aucun joueur assigné au {titre_affichage} actuellement.")
            except: pass

# --- LOGIQUE DU MODE TOURNOI FLASH ---
tournoi_inscrits, tournoi_etape, tournoi_matchs, tournoi_vainqueurs = [], "ferme", {}, {}
id_message_tournoi, id_salon_tournoi = None, None

def generer_affichage_tournoi():
    global tournoi_etape, tournoi_matchs, tournoi_vainqueurs
    texte = "⚔️ ─── **TOURNOI FLASH AUTOMATIQUE** ─── ⚔️\n\n"
    if tournoi_etape == "inscriptions":
        texte += f"📌 **Inscriptions ouvertes : {len(tournoi_inscrits)} / 8**\n\n"
        for index, u_id in enumerate(tournoi_inscrits): texte += f"{index + 1}. <@{u_id}>\n"
        return texte
    texte += "◽ **QUARTS DE FINALE** ◽\n"
    for m in range(1, 5):
        p1 = f"<@{tournoi_matchs[f'Q{m}'][0]}>" if f'Q{m}' in tournoi_matchs and len(tournoi_matchs[f'Q{m}']) > 0 else "À définir"
        p2 = f"<@{tournoi_matchs[f'Q{m}'][1]}>" if f'Q{m}' in tournoi_matchs and len(tournoi_matchs[f'Q{m}']) > 1 else "À définir"
        v = f"🏅 Vainqueur : <@{tournoi_vainqueurs[f'Q{m}']}>" if f'Q{m}' in tournoi_vainqueurs else "En attente..."
        texte += f"🔹 Match Q{m} : {p1} VS {p2}\n   └─ {v}\n"
    return texte

class VueInscriptionTournoi(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="S'inscrire ⚔️", style=discord.ButtonStyle.success, custom_id="btn_join_tournoi")
    async def bouton_inscription(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournoi_inscrits, tournoi_etape, tournoi_matchs
        if tournoi_etape != "inscriptions": return
        if interaction.user.id in tournoi_inscrits: return
        tournoi_inscrits.append(interaction.user.id)
        if len(tournoi_inscrits) == 8:
            tournoi_etape = "quarts"
            for m in range(1, 5): tournoi_matchs[f'Q{m}'] = [tournoi_inscrits[(m-1)*2], tournoi_inscrits[(m-1)*2+1]]
            await interaction.message.edit(content=generer_affichage_tournoi(), view=None)
        else: await interaction.message.edit(content=generer_affichage_tournoi(), view=self)
        await interaction.response.defer()

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
    if membre.id not in classement_top: classement_top.append(membre.id)
    await ctx.message.delete()
    await rafraichir_partout(ctx.guild)

@bot.command(name="addmany")
@commands.has_permissions(administrator=True)
async def ajouter_plusieurs_joueurs(ctx, *membres: discord.Member):
    global classement_top
    for membre in membres:
        if membre.id not in classement_top: classement_top.append(membre.id)
    await ctx.message.delete()
    await rafraichir_partout(ctx.guild)

@bot.command(name="remove")
@commands.has_permissions(administrator=True)
async def supprimer_joueur_txt(ctx, membre: discord.Member):
    global classement_top
    if membre.id in classement_top: classement_top.remove(membre.id)
    await ctx.message.delete()
    await rafraichir_partout(ctx.guild)

@bot.command(name="tstart")
@commands.has_permissions(administrator=True)
async def lancer_inscriptions_tournoi(ctx):
    global tournoi_inscrits, tournoi_etape, tournoi_matchs, tournoi_vainqueurs, id_message_tournoi, id_salon_tournoi
    tournoi_inscrits, tournoi_matchs, tournoi_vainqueurs = [], {}, {}
    tournoi_etape = "inscriptions"
    id_salon_tournoi = ctx.channel.id
    await ctx.message.delete()
    msg = await ctx.send(content=generer_affichage_tournoi(), view=VueInscriptionTournoi())
    id_message_tournoi = msg.id

@bot.command(name="twin")
@commands.has_permissions(administrator=True)
async def valider_gagnant_match(ctx, code_match: str, membre: discord.Member):
    global tournoi_matchs, tournoi_vainqueurs, id_message_tournoi, id_salon_tournoi
    code_match = code_match.upper()
    tournoi_vainqueurs[code_match] = membre.id
    await ctx.message.delete()
    salon = bot.get_channel(id_salon_tournoi)
    if salon:
        try:
            msg = await salon.fetch_message(id_message_tournoi)
            await msg.edit(content=generer_affichage_tournoi())
        except: pass

@bot.command(name="setup_ticket")
@commands.has_permissions(administrator=True)
async def envoyer_panneau_ticket(ctx):
    await ctx.message.delete()
    embed = discord.Embed(title="🎫 Support & Recrutement - Système de Tickets", description="Cliquez ci-dessous pour ouvrir un salon d'assistance privé et choisir votre motif.", color=discord.Color.green())
    await ctx.send(embed=embed, view=VueCreationTicket())

@bot.event
async def on_ready():
    bot.add_view(VueControleTop())
    bot.add_view(VueCreationTicket())
    bot.add_view(VueFermetureTicket())
    print(f"Bot en ligne : {bot.user.name}")

keep_alive()
bot.run(os.environ.get("DISCORD_TOKEN"))
