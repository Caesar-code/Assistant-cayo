import discord
from discord.ext import commands
from discord import app_commands
import datetime
import os
from dotenv import load_dotenv
from datetime import timezone
from keep_alive import keep_alive

# Chargement du token
load_dotenv()
TOKEN = os.getenv("TOKEN")

# Configuration des intents
intents = discord.Intents.default()
intents.message_content = True

# Initialisation du bot
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Connecté en tant que {bot.user}")

# Vue avec bouton de suppression
class DeleteButtonView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=None)
        self.author_id = author_id

    @discord.ui.button(label="Supprimer", style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("🚫 Tu ne peux pas supprimer ce message.", ephemeral=True)
            return
        await interaction.message.delete()
        await interaction.response.send_message("🗑️ Message supprimé.", ephemeral=True)

# Commande /med
@tree.command(name="med", description="Faire une mise en détention (MED)")
@app_commands.describe(
    nom_prenom="Nom et prénom du détenu",
    identifiant="ID de la personne",
    temps_prison="Temps de prison (ex: 30 minutes)",
    raison="Raison de l’arrestation"
)
async def med(interaction: discord.Interaction, nom_prenom: str, identifiant: str, temps_prison: str, raison: str):
    now = datetime.datetime.now().strftime("%d/%m/%Y à %Hh%M")

    embed = discord.Embed(
        title="🟥 Mise en Détention",
        description="Une mise en détention vient d’être enregistrée.",
        color=discord.Color.dark_red()
    )
    embed.add_field(name="👤 Détenu", value=nom_prenom, inline=False)
    embed.add_field(name="🆔 Identifiant", value=identifiant, inline=True)
    embed.add_field(name="⏱️ Durée", value=temps_prison, inline=True)
    embed.add_field(name="📄 Raison", value=raison, inline=False)
    embed.add_field(name="🕒 Heure", value=now, inline=False)
    embed.add_field(name="👮‍♂️ Agent", value=interaction.user.mention, inline=False)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.set_footer(text="Mise en détention enregistrée - Cayo Perico PD")

    # Recherche de la dernière image envoyée dans les 10 dernières minutes
    image_attachment = None
    async for msg in interaction.channel.history(limit=100):
        if msg.attachments:
            for att in msg.attachments:
                if att.content_type and att.content_type.startswith("image/"):
                    delta = discord.utils.utcnow().replace(tzinfo=timezone.utc) - msg.created_at
                    if delta.total_seconds() <= 600:
                        image_attachment = att
                        break
        if image_attachment:
            break

    view = DeleteButtonView(author_id=interaction.user.id)

    if image_attachment:
        file = await image_attachment.to_file()
        embed.set_image(url=f"attachment://{file.filename}")
        await interaction.response.send_message(embed=embed, file=file, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view)

# Commande /service
@tree.command(name="service", description="Démarrer un service policier")
@app_commands.describe(
    heure_debut="Heure de début du service (HHhMM, ex: 22h30)",
    heure_fin="Heure de fin du service (HHhMM, ex: 06h15)"
)
async def service(interaction: discord.Interaction, heure_debut: str, heure_fin: str):
    def parse_hhmm(time_str: str) -> datetime.time:
        parts = time_str.lower().split('h')
        if len(parts) != 2:
            raise ValueError("Format incorrect, utilisez HHhMM (ex: 22h30)")
        h, m = map(int, parts)
        if not (0 <= h < 24 and 0 <= m < 60):
            raise ValueError("Heure ou minute hors plage")
        return datetime.time(h, m)

    try:
        debut = parse_hhmm(heure_debut)
        fin = parse_hhmm(heure_fin)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)
        return

    debut_dt = datetime.datetime.combine(datetime.date.today(), debut)
    fin_dt = datetime.datetime.combine(datetime.date.today(), fin)
    if fin_dt <= debut_dt:
        fin_dt += datetime.timedelta(days=1)

    duree = fin_dt - debut_dt
    heures = duree.seconds // 3600
    minutes = (duree.seconds % 3600) // 60

    embed = discord.Embed(
        title="🚔 Service Policier",
        description=f"Service démarré de {heure_debut} à {heure_fin}",
        color=discord.Color.blue()
    )
    embed.add_field(name="🕒 Heure de début", value=heure_debut, inline=True)
    embed.add_field(name="🕒 Heure de fin", value=heure_fin, inline=True)
    embed.add_field(name="⏳ Durée totale", value=f"{heures}h{minutes:02d}min", inline=False)
    embed.add_field(name="👮 Agent", value=interaction.user.mention, inline=False)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.set_footer(text="Service policier enregistré - Cayo Perico PD")

    file = discord.File("cayo.png", filename="cayo.png")
    embed.set_image(url="attachment://cayo.png")

    view = DeleteButtonView(author_id=interaction.user.id)
    await interaction.response.send_message(embed=embed, file=file, view=view)

# Commande /recherche
@tree.command(name="recherche", description="🔎 Recherche une mise en détention par ID dans ce salon")
@app_commands.describe(
    identifiant="ID de la personne recherchée"
)
async def recherche(interaction: discord.Interaction, identifiant: str):
    await interaction.response.defer(ephemeral=True, thinking=True)

    salon_courant = interaction.channel
    if not isinstance(salon_courant, discord.TextChannel):
        await interaction.followup.send("❌ Cette commande doit être utilisée dans un salon textuel.", ephemeral=True)
        return

    results = []

    async for msg in salon_courant.history(limit=1000):
        if msg.embeds:
            for embed in msg.embeds:
                id_match = False
                raison = None
                for field in embed.fields:
                    if field.name == "🆔 Identifiant" and field.value.strip() == identifiant:
                        id_match = True
                    if field.name == "📄 Raison":
                        raison = field.value

                if id_match:
                    results.append({
                        "raison": raison or "Non spécifiée",
                        "lien": msg.jump_url
                    })

    if not results:
        await interaction.followup.send(f"❌ Aucun MED trouvé pour l'identifiant `{identifiant}` dans ce salon.", ephemeral=True)
        return

    count = len(results)
    description = f"✅ **{count} mise(s) en détention** trouvée(s) pour l'ID `{identifiant}` dans ce salon :\n\n"
    for i, r in enumerate(results, start=1):
        description += f"**{i}.** 📄 Raison : `{r['raison']}`\n🔗 [Voir le message original]({r['lien']})\n\n"

    embed = discord.Embed(
        title=f"🔎 Résultats pour l'identifiant {identifiant}",
        description=description,
        color=discord.Color.orange()
    )
    embed.set_footer(text="Recherche de mise en détention - Cayo Perico PD")

    await interaction.followup.send(embed=embed, ephemeral=True)

# Lancement du bot
keep_alive()
bot.run(TOKEN)
