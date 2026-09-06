import discord
from discord.ext import commands
import asyncio
from flask import Flask
from threading import Thread
import os
import json
import base64

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

# Cloisonnement des données et configurations par ID de serveur
classements_par_serveur = {}      # {guild_id: [liste_joueurs]}
id_messages_principaux = {}       # {guild_id: id_message}
id_salons_principaux = {}         # {guild_id: id_salon}
config_serveurs = {}              # {guild_id: {options_de_config}}

FICHIER_CONFIG = "config_serveurs.json"

# --- SYSTEME DE CONFIGURATION ---
def charger_config_globale():
    if not os.path.exists(FICHIER_CONFIG): return {}
    try:
        with open(FICHIER_CONFIG, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def enregistrer_config_globale(data):
    with open(FICHIER_CONFIG, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def obtenir_config_serveur(guild_id):
    global config_serveurs
    gid_str = str(guild_id)
    configs = charger_config_globale()
    
    if gid_str not in configs:
        configs[gid_str] = {
            "role_admin_id": 1529373902969770094,
            "taille_team": 5,
            "noms_salons": {
                "1": "🏅𝐌𝐀𝐈𝐍 𝐑𝐎𝐒𝐓𝐄𝐑🏅", "2": "🥈︱𝐓𝐄𝐀𝐌-𝟐🥈", "3": "🥉︱𝐓𝐄𝐀𝐌-𝟑🥉",
                "4": "🎖︱𝐓𝐄𝐀𝐌-𝟒🎖", "5": "🏆︱𝐓𝐄𝐀𝐌-𝟓🏆", "6": "🎗︱𝐓𝐄𝐀𝐌-𝟔🎗",
                "7": "✨︱𝐓𝐄𝐀𝐌-𝟕✨", "8": "🎫︱𝐓𝐄𝐀𝐌-𝟖🎫"
            },
            "noms_roles": {
                "1": "Main Roster", "2": "Team 2", "3": "Team 3", "4": "Team 4",
                "5": "Team 5", "6": "Team 6", "7": "Team 7", "8": "Team 8"
            },
            "motifs_tickets": ["Admin", "Test Team", "Tryout"]
        }
        enregistrer_config_globale(configs)
    
    config_serveurs[guild_id] = configs[gid_str]
    return configs[gid_str]

def mettre_a_jour_config_serveur(guild_id, cle, valeur):
    configs = charger_config_globale()
    gid_str = str(guild_id)
    if gid_str not in configs: obtenir_config_serveur(guild_id)
    configs[gid_str][cle] = valeur
    enregistrer_config_globale(configs)
    config_serveurs[guild_id] = configs[gid_str]

def obtenir_nom_salon_team(guild, num_team):
    conf = obtenir_config_serveur(guild.id)
    return conf["noms_salons"].get(str(num_team), f"💫︱𝐓𝐄𝐀𝐌-{num_team}💫")

def obtenir_nom_role_team(guild, num_team):
    conf = obtenir_config_serveur(guild.id)
    return conf["noms_roles"].get(str(num_team), f"Team {num_team}")

def obtenir_equipe_et_salon_dynamique(guild_id, position):
    conf = obtenir_config_serveur(guild_id)
    taille = int(conf.get("taille_team", 5))
    if position <= taille: return 1
    return 2 + (position - (taille + 1)) // 6

def normaliser_nom_salon(nom):
    return nom.lower().replace("-", "").replace(" ", "").replace("\ufe0f", "")
# --- LOGIQUE DE SAUVEGARDE PAR COPIER-COLLER (ANTI-RESET RENDER) ---
class VueDataOptions(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="GÉNÉRER UN CODE TEXTE 💾", style=discord.ButtonStyle.success)
    async def btn_generer_code(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = interaction.guild_id
        top_actuel = classements_par_serveur.get(gid, [])
        
        if not top_actuel:
            await interaction.response.send_message("⚠️ Le classement actuel est vide. Impossible de générer un code.", ephemeral=True)
            return
            
        # Conversion de la liste en code texte sécurisé et compact
        data_str = json.dumps(top_actuel)
        code_bytes = base64.b64encode(data_str.encode('utf-8'))
        code_securise = f"GT_DATA_{code_bytes.decode('utf-8')}"
        
        await interaction.response.send_message(
            content=(
                "💾 **Code de Sauvegarde permanent généré avec succès !**\n"
                "Copiez l'intégralité du texte ci-dessous et gardez-le précieusement dans vos notes ou un salon privé. "
                "Il vous permettra de restaurer ce classement à n'importe quel moment, même si le bot redémarre :\n\n"
                f"`{code_securise}`"
            ),
            ephemeral=True
        )

    @discord.ui.button(label="RESTAURER VIA UN CODE 🔄", style=discord.ButtonStyle.danger)
    async def btn_restaurer_code(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FenetreCollerCode())

class FenetreNomSauvegarde(discord.ui.Modal, title="Nommer l'enregistrement"):
    nom_save = discord.ui.TextInput(label="Nom de la sauvegarde", placeholder="Ex: Fin_Semaine_1")
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("❌ Option désactivée : Utilisez le bouton 'GÉNÉRER UN CODE TEXTE' pour sauvegarder de manière permanente.", ephemeral=True)

class FenetreCollerCode(discord.ui.Modal, title="Coller votre code"):
    code_entre = discord.ui.TextInput(label="Collez le code de sauvegarde complet ici", placeholder="Ex: GT_DATA_...", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        global classements_par_serveur
        brut = self.code_entre.value.strip()
        
        if not brut.startswith("GT_DATA_"):
            await interaction.response.send_message("❌ Code invalide. Le format doit commencer par `GT_DATA_`.", ephemeral=True)
            return
            
        try:
            await interaction.response.defer(ephemeral=True)
            code_propre = brut.replace("GT_DATA_", "")
            decoded_bytes = base64.b64decode(code_propre.encode('utf-8'))
            liste_restauree = json.loads(decoded_bytes.decode('utf-8'))
            
            if isinstance(liste_restauree, list):
                classements_par_serveur[interaction.guild_id] = list(liste_restauree)
                await interaction.followup.send("✅ **Restauration effectuée !** Le classement a été reconstruit à partir de votre code.", ephemeral=True)
                await rafraichir_partout(interaction.guild)
            else:
                await interaction.followup.send("❌ Structure de données corrompue dans le code.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Impossible de lire ce code de sauvegarde : `{e}`", ephemeral=True)
# --- PANEL DE CONFIGURATION DYNAMIQUE ---
class VuePanelConfig(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=120)
        self.guild_id = guild_id

    @discord.ui.button(label="Taille Équipe 👥", style=discord.ButtonStyle.primary, row=0)
    async def btn_taille(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalTailleTeam())

    @discord.ui.button(label="Rôle Admin 🛡️", style=discord.ButtonStyle.primary, row=0)
    async def btn_role_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalRoleAdmin())

    @discord.ui.button(label="Nom Équipe (Salon/Rôle) ✏️", style=discord.ButtonStyle.primary, row=1)
    async def btn_custom_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalNomTeam())

    @discord.ui.button(label="Raisons des Tickets 🎫", style=discord.ButtonStyle.primary, row=1)
    async def btn_motifs(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalMotifsTickets())

class ModalTailleTeam(discord.ui.Modal, title="Modifier le nombre de joueurs"):
    taille = discord.ui.TextInput(label="Nombre de joueurs max dans le Main Roster", placeholder="Ex: 5 ou 6")
    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.taille.value.strip())
            mettre_a_jour_config_serveur(interaction.guild_id, "taille_team", val)
            await interaction.response.send_message(f"✅ La taille maximale du Main Roster est passée à **{val} joueurs** !", ephemeral=True)
        except: await interaction.response.send_message("❌ Entrez un nombre valide.", ephemeral=True)

class ModalRoleAdmin(discord.ui.Modal, title="Lier le rôle Admin"):
    rid = discord.ui.TextInput(label="ID Numérique du rôle Admin autorisé", placeholder="Copiez l'ID du rôle ici")
    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.rid.value.strip())
            mettre_a_jour_config_serveur(interaction.guild_id, "role_admin_id", val)
            await interaction.response.send_message(f"✅ Le rôle de gestion Admin a été lié à l'ID : `{val}` !", ephemeral=True)
        except: await interaction.response.send_message("❌ ID numérique invalide.", ephemeral=True)

class ModalNomTeam(discord.ui.Modal, title="Renommer une Équipe"):
    num = discord.ui.TextInput(label="Numéro de l'équipe à changer (Ex: 1)", placeholder="Ex: 1")
    nom_s = discord.ui.TextInput(label="Nouveau nom du Salon textuel", placeholder="Ex: 🏅𝐌𝐀𝐈𝐍 𝐑𝐎𝐒𝐓𝐄𝐑🏅")
    nom_r = discord.ui.TextInput(label="Nouveau nom du Rôle Discord", placeholder="Ex: Main Roster")
    async def on_submit(self, interaction: discord.Interaction):
        conf = obtenir_config_serveur(interaction.guild_id)
        n = self.num.value.strip()
        conf["noms_salons"][n] = self.nom_s.value.strip()
        conf["noms_roles"][n] = self.nom_r.value.strip()
        mettre_a_jour_config_serveur(interaction.guild_id, "noms_salons", conf["noms_salons"])
        mettre_a_jour_config_serveur(interaction.guild_id, "noms_roles", conf["noms_roles"])
        await interaction.response.send_message(f"✅ L'Équipe {n} a été renommée avec succès !", ephemeral=True)

class ModalMotifsTickets(discord.ui.Modal, title="Modifier les motifs de tickets"):
    motifs = discord.ui.TextInput(label="Raisons séparées par des virgules", placeholder="Ex: Admin, Recrutement, Plainte")
    async def on_submit(self, interaction: discord.Interaction):
        liste = [m.strip() for m in self.motifs.value.split(",") if m.strip()]
        if not liste:
            await interaction.response.send_message("❌ Liste invalide.", ephemeral=True)
            return
        mettre_a_jour_config_serveur(interaction.guild_id, "motifs_tickets", liste)
        await interaction.response.send_message(f"✅ Les motifs de tickets mis à jour : `{', '.join(liste)}` !", ephemeral=True)

# --- INTERFACES DES POPUPS CLASSEMENT ---
class FenetreDeplacement(discord.ui.Modal, title="Changer la place (Décaler)"):
    pos_depart = discord.ui.TextInput(label="Position actuelle", placeholder="Ex: 5")
    pos_arrivee = discord.ui.TextInput(label="Nouvelle position", placeholder="Ex: 2")
    async def on_submit(self, interaction: discord.Interaction):
        global classements_par_serveur
        gid = interaction.guild_id
        if gid not in classements_par_serveur: classements_par_serveur[gid] = []
        try:
            p_dep = int(self.pos_depart.value) - 1
            p_arr = int(self.pos_arrivee.value) - 1
            if p_dep < 0 or p_arr < 0 or p_dep >= len(classements_par_serveur[gid]) or p_arr >= len(classements_par_serveur[gid]): return
            await interaction.response.defer(ephemeral=True)
            joueur_id = classements_par_serveur[gid].pop(p_dep)
            classements_par_serveur[gid].insert(p_arr, joueur_id)
            await interaction.followup.send("📈 Déplacement effectué !", ephemeral=True)
            await rafraichir_partout(interaction.guild)
        except: pass

class FenetreEchange(discord.ui.Modal, title="Échanger 2 places"):
    pos1 = discord.ui.TextInput(label="Position 1er joueur", placeholder="Ex: 2")
    pos2 = discord.ui.TextInput(label="Position 2ème joueur", placeholder="Ex: 5")
    async def on_submit(self, interaction: discord.Interaction):
        global classements_par_serveur
        gid = interaction.guild_id
        try:
            p1 = int(self.pos1.value) - 1
            p2 = int(self.pos2.value) - 1
            await interaction.response.defer(ephemeral=True)
            classements_par_serveur[gid][p1], classements_par_serveur[gid][p2] = classements_par_serveur[gid][p2], classements_par_serveur[gid][p1]
            await interaction.followup.send("🔄 Échange effectué !", ephemeral=True)
            await rafraichir_partout(interaction.guild)
        except: pass

class FenetreSuppression(discord.ui.Modal, title="Retirer un joueur"):
    pos_suppr = discord.ui.TextInput(label="Position à supprimer", placeholder="Ex: 3")
    async def on_submit(self, interaction: discord.Interaction):
        global classements_par_serveur
        gid = interaction.guild_id
        try:
            p = int(self.pos_suppr.value) - 1
            await interaction.response.defer(ephemeral=True)
            classements_par_serveur[gid].pop(p)
            await interaction.followup.send("❌ Retiré !", ephemeral=True)
            await rafraichir_partout(interaction.guild)
        except: pass

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
        conf = obtenir_config_serveur(interaction.guild_id)
        role_verif = discord.utils.get(interaction.user.roles, id=int(conf["role_admin_id"]))
        if not role_verif and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Accès refusé. Rôle ADMIN requis.", ephemeral=True)
            return
        await interaction.response.send_message(content="🗄️ **Gestion de la Base de Données (Permanent)**", view=VueDataOptions(), ephemeral=True)

    @discord.ui.button(label="Liste des Commandes ❓", style=discord.ButtonStyle.success, custom_id="btn_help")
    async def bouton_aide(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🤖 Guide des commandes", color=discord.Color.gold())
        embed.add_field(name="🛠️ Commandes Admin", value="`!setup`, `!add @membre`, `!addmany @m1 @m2...`, `!remove @membre`, `!tstart`, `!twin`, `!setup_ticket`, `!config`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
# --- SECURE TICKET SYSTEM ---
class VueCreationTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Créer un ticket 🎫", style=discord.ButtonStyle.primary, custom_id="btn_creer_ticket")
    async def bouton_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(content="📋 **Sélectionnez le motif de votre ticket :**", view=VueChoixMotifTicket(interaction.guild_id), ephemeral=True)

class VueChoixMotifTicket(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=60)
        conf = obtenir_config_serveur(guild_id)
        options = [discord.SelectOption(label=m, value=m) for m in conf["motifs_tickets"]]
        self.add_item(MenuDeroulantMotif(options))

class MenuDeroulantMotif(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Choisissez la raison du ticket...", options=options)

    async def callback(self, interaction: discord.Interaction):
        motif_selectionne = self.values if isinstance(self.values, list) else self.values
        guild = interaction.guild
        conf = obtenir_config_serveur(guild.id)
        
        categorie = discord.utils.find(lambda c: c.name == "🎫 𝙏Ｉ𝘾𝙆𝙀𝙏" and isinstance(c, discord.CategoryChannel), guild.channels)
        if not categorie:
            try: categorie = await guild.create_category(name="🎫 𝙏Ｉ𝘾𝙆𝙀𝙏")
            except: return

        membre_createur = interaction.user
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False, view_channel=False),
            membre_createur: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, view_channel=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, view_channel=True)
        }
        
        role_admin = guild.get_role(int(conf["role_admin_id"]))
        if role_admin: overwrites[role_admin] = discord.PermissionOverwrite(read_messages=True, send_messages=True, view_channel=True)

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
            await interaction.response.send_message(f"❌ Échec de création : `{e}`", ephemeral=True)

class VueFermetureTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fermer le ticket 🔒", style=discord.ButtonStyle.danger, custom_id="btn_fermer_ticket")
    async def bouton_fermer(self, interaction: discord.Interaction, button: discord.ui.Button):
        conf = obtenir_config_serveur(interaction.guild_id)
        role_verif = discord.utils.get(interaction.user.roles, id=int(conf["role_admin_id"]))
        if not role_verif and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Seul un admin peut fermer ce ticket.", ephemeral=True)
            return
        await interaction.response.send_message("🔒 **Fermeture et suppression du salon dans 5 secondes.**")
        await asyncio.sleep(5)
        await interaction.channel.delete()
# --- REFRESH ET RÔLES DYNAMIQUES PAR SERVEUR (SÉCURISÉ CONTRE LES CRASHS) ---
async def rafraichir_partout(guild):
    global id_messages_principaux, id_salons_principaux, classements_par_serveur
    gid = guild.id
    if gid not in id_salons_principaux or not id_salons_principaux[gid]: return
    if gid not in classements_par_serveur: classements_par_serveur[gid] = []

    total_joueurs = len(classements_par_serveur[gid])
    max_team = obtenir_equipe_et_salon_dynamique(gid, total_joueurs) if total_joueurs > 0 else 1

    # Nettoyage sécurisé des rôles
    for member in guild.members:
        if member.id not in classements_par_serveur[gid]:
            roles_mauvais = [r for r in member.roles if r.name.startswith("Team ") or r.name == "Main Roster" or r.name in [obtenir_nom_role_team(guild, i) for i in range(1, 9)]]
            if roles_mauvais: 
                try: await member.remove_roles(*roles_mauvais)
                except: pass

    # Création des rôles/salons manquants
    for num_team in range(1, max_team + 1):
        nom_role = obtenir_nom_role_team(guild, num_team)
        nom_salon_stylise = obtenir_nom_salon_team(guild, num_team)
        if not discord.utils.get(guild.roles, name=nom_role):
            try: await guild.create_role(name=nom_role)
            except: pass
        salon_existe = any(normaliser_nom_salon(c.name) == normaliser_nom_salon(nom_salon_stylise) for c in guild.channels)
        if not salon_existe:
            try: await guild.create_text_channel(name=nom_salon_stylise)
            except: pass

    # Attribution sécurisée des rôles
    for index, user_id in enumerate(classements_par_serveur[gid]):
        pos = index + 1
        team_cible = obtenir_equipe_et_salon_dynamique(gid, pos)
        try: member = await guild.fetch_member(user_id)
        except: member = None
        if member:
            nom_role_cible = obtenir_nom_role_team(guild, team_cible)
            role_bon = discord.utils.get(guild.roles, name=nom_role_cible)
            if role_bon and role_bon not in member.roles:
                try: await member.add_roles(role_bon)
                except: pass

    # Envoi du message du tableau général
    salon_top = guild.get_channel(id_salons_principaux[gid])
    if salon_top:
        texte_top = "🏆 **CLASSEMENT GÉNÉRAL COMPLET** 🏆\n\n"
        if not classements_par_serveur[gid]: texte_top += "*Aucun joueur dans le top pour le moment.*"
        for index, u_id in enumerate(classements_par_serveur[gid]): texte_top += f"**Top {index + 1}** : <@{u_id}>\n"
        
        msg_envoye = False
        if gid in id_messages_principaux and id_messages_principaux[gid]:
            try:
                msg = await salon_top.fetch_message(id_messages_principaux[gid])
                await msg.edit(content=texte_top, view=VueControleTop())
                msg_envoye = True
            except: pass
                
        if not msg_envoye:
            msg = await salon_top.send(content=texte_top, view=VueControleTop())
            id_messages_principaux[gid] = msg.id

    # Remplissage des salons d'équipes respectifs
    for num_team in range(1, max_team + 1):
        nom_salon_stylise = obtenir_nom_salon_team(guild, num_team)
        salon_team = discord.utils.find(lambda c: normaliser_nom_salon(c.name) == normaliser_nom_salon(nom_salon_stylise), guild.channels)
        if salon_team:
            try: await salon_team.purge(limit=50)
            except: pass
            lignes = [f"**Top {i+1}** : <@{uid}>" for i, uid in enumerate(classements_par_serveur[gid]) if obtenir_equipe_et_salon_dynamique(gid, i+1) == num_team]
            titre_affichage = obtenir_nom_role_team(guild, num_team).upper()
            try:
                if lignes: await salon_team.send(f"🏆 **Membres - {titre_affichage}** 🏆\n\n" + "\n".join(lignes))
                else: await salon_team.send(f"Aucun joueur assigné au {titre_affichage} actuellement.")
            except: pass
# --- LOGIQUE DU MODE TOURNOI FLASH ---
tournois_par_serveur = {}

def generer_affichage_tournoi(gid):
    t = tournois_par_serveur.get(gid, {"inscrits": [], "etape": "ferme", "matchs": {}, "vainqueurs": {}})
    texte = "⚔️ ─── **TOURNOI FLASH AUTOMATIQUE** ─── ⚔️\n\n"
    if t["etape"] == "inscriptions":
        texte += f"📌 **Inscriptions ouvertes : {len(t['inscrits'])} / 8**\n\n"
        for index, u_id in enumerate(t["inscrits"]): texte += f"{index + 1}. <@{u_id}>\n"
        return texte
    texte += "◽ **QUARTS DE FINALE** ◽\n"
    for m in range(1, 5):
        p1 = f"<@{t['matchs'][f'Q{m}']}>" if f'Q{m}' in t['matchs'] and len(t['matchs'][f'Q{m}']) > 0 else "À définir"
        p2 = f"<@{t['matchs'][f'Q{m}']}>" if f'Q{m}' in t['matchs'] and len(t['matchs'][f'Q{m}']) > 1 else "À définir"
        v = f"🏅 Vainqueur : <@{t['vainqueurs'][f'Q{m}']}>" if f'Q{m}' in t['vainqueurs'] else "En attente..."
        texte += f"🔹 Match Q{m} : {p1} VS {p2}\n   └─ {v}\n"
    return texte

class VueInscriptionTournoi(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="S'inscrire ⚔️", style=discord.ButtonStyle.success, custom_id="btn_join_tournoi")
    async def bouton_inscription(self, interaction: discord.Interaction, button: discord.ui.Button):
        global tournois_par_serveur
        gid = interaction.guild_id
        if gid not in tournois_par_serveur: return
        t = tournois_par_serveur[gid]
        if t["etape"] != "inscriptions" or interaction.user.id in t["inscrits"]: return
        t["inscrits"].append(interaction.user.id)
        if len(t["inscrits"]) == 8:
            t["etape"] = "quarts"
            for m in range(1, 5): t["matchs"][f'Q{m}'] = [t["inscrits"][(m-1)*2], t["inscrits"][(m-1)*2+1]]
            await interaction.message.edit(content=generer_affichage_tournoi(gid), view=None)
        else: await interaction.message.edit(content=generer_affichage_tournoi(gid), view=self)
        await interaction.response.defer()
# --- COMMANDES ADMIN TEXTUELLES ---
@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def initialiser_salon_top(ctx):
    global id_salons_principaux, id_messages_principaux
    id_salons_principaux[ctx.guild.id] = ctx.channel.id
    id_messages_principaux[ctx.guild.id] = None
    await ctx.message.delete()
    await rafraichir_partout(ctx.guild)

@bot.command(name="config")
@commands.has_permissions(administrator=True)
async def ouvrir_menu_config(ctx):
    await ctx.message.delete()
    embed = discord.Embed(
        title="🎛️ Panneau de Configuration Personnalisable",
        description="Cliquez sur les boutons ci-dessous pour modifier la structure du serveur de manière isolée.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=VuePanelConfig(ctx.guild.id), delete_after=60)

@bot.command(name="add")
@commands.has_permissions(administrator=True)
async def ajouter_joueur(ctx, membre: discord.Member):
    global classements_par_serveur
    gid = ctx.guild.id
    if gid not in classements_par_serveur: classements_par_serveur[gid] = []
    if membre.id not in classements_par_serveur[gid]: classements_par_serveur[gid].append(membre.id)
    await ctx.message.delete()
    await rafraichir_partout(ctx.guild)

@bot.command(name="addmany")
@commands.has_permissions(administrator=True)
async def ajouter_plusieurs_joueurs(ctx, *membres: discord.Member):
    global classements_par_serveur
    gid = ctx.guild.id
    if gid not in classements_par_serveur: classements_par_serveur[gid] = []
    for membre in membres:
        if membre.id not in classements_par_serveur[gid]: classements_par_serveur[gid].append(membre.id)
    await ctx.message.delete()
    await rafraichir_partout(ctx.guild)

@bot.command(name="remove")
@commands.has_permissions(administrator=True)
async def supprimer_joueur_txt(ctx, membre: discord.Member):
    global classements_par_serveur
    gid = ctx.guild.id
    if gid in classements_par_serveur and membre.id in classements_par_serveur[gid]:
        classements_par_serveur[gid].remove(membre.id)
    await ctx.message.delete()
    await rafraichir_partout(ctx.guild)

@bot.command(name="tstart")
@commands.has_permissions(administrator=True)
async def lancer_inscriptions_tournoi(ctx):
    global tournois_par_serveur
    gid = ctx.guild.id
    tournois_par_serveur[gid] = {"inscrits": [], "etape": "inscriptions", "matchs": {}, "vainqueurs": {}, "msg_id": None}
    await ctx.message.delete()
    msg = await ctx.send(content=generer_affichage_tournoi(gid), view=VueInscriptionTournoi())
    tournois_par_serveur[gid]["msg_id"] = msg.id

@bot.command(name="twin")
@commands.has_permissions(administrator=True)
async def valider_gagnant_match(ctx, code_match: str, membre: discord.Member):
    global tournois_par_serveur
    gid = ctx.guild.id
    if gid not in tournois_par_serveur: return
    t = tournois_par_serveur[gid]
    code_match = code_match.upper()
    t["vainqueurs"][code_match] = membre.id
    await ctx.message.delete()
    try:
        msg = await ctx.channel.fetch_message(t["msg_id"])
        await msg.edit(content=generer_affichage_tournoi(gid))
    except: pass

@bot.command(name="setup_ticket")
@commands.has_permissions(administrator=True)
async def envoyer_panneau_ticket(ctx):
    await ctx.message.delete()
    embed = discord.Embed(title="🎫 Support & Recrutement - Système de Tickets", description="Cliquez ci-dessous pour ouvrir un salon d'assistance privé.\nLes salons apparaîtront dans la catégorie **🎫 𝙏Ｉ𝘾𝙆𝙀𝙏**.", color=discord.Color.green())
    await ctx.send(embed=embed, view=VueCreationTicket())

@bot.event
async def on_ready():
    bot.add_view(VueControleTop())
    bot.add_view(VueCreationTicket())
    bot.add_view(VueFermetureTicket())
    print(f"Bot en ligne : {bot.user.name}")

keep_alive()
bot.run(os.environ.get("DISCORD_TOKEN"))
