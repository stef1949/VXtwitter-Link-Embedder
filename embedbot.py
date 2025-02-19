import logging
import discord
import re
import os
import time

# Configure logging to show the time, logger name, level, and message.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Retrieve the token from an environment variable
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("No Discord token provided. Please set the DISCORD_TOKEN environment variable.")

# Enable the message content intent (required to read messages)
intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

# Regex to match URLs that start with http(s):// and include twitter.com or x.com
URL_REGEX = re.compile(r'(https?://(?:www\.)?(?:twitter\.com|x\.com)/\S+)', re.IGNORECASE)

# Rate limiting configuration (per user)
RATE_LIMIT_SECONDS = 10
user_rate_limit = {}  # Dictionary mapping user ID to last processed timestamp

# Slash command: /status
@tree.command(name="status", description="Check the bot's status")
async def status(interaction: discord.Interaction):
    logger.info(f"Received /status command from {interaction.user} in guild {interaction.guild}")
    await interaction.response.send_message("Bot is running!", ephemeral=True)

# Slash command: /help
@tree.command(name="help", description="Show help information about the bot")
async def help_command(interaction: discord.Interaction):
    logger.info(f"Received /help command from {interaction.user} in guild {interaction.guild}")
    help_text = (
        "This bot replaces `twitter.com` or `x.com` links with `vxtwitter.com` and provides a delete button "
        "for the original poster to delete the message.\n\n"
        "**Commands:**\n"
        "`/status` - Check if the bot is running.\n"
        "`/help` - Show this help message.\n\n"
        "Just send a message containing a Twitter/X link, and the bot will take care of the rest."
    )
    await interaction.response.send_message(help_text, ephemeral=True)

# Create a view with a button that allows only the original poster to delete the message.
class DeleteButtonView(discord.ui.View):
    def __init__(self, original_author_id: int, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.original_author_id = original_author_id

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"Delete button clicked by {interaction.user} in message {interaction.message.id}")
        # Only allow the original poster to delete the message.
        if interaction.user.id != self.original_author_id:
            logger.warning(f"Unauthorized delete attempt by {interaction.user}")
            await interaction.response.send_message("You are not allowed to delete this message.", ephemeral=True)
            return

        try:
            await interaction.message.delete()
            logger.info(f"Message {interaction.message.id} deleted by {interaction.user}")
            await interaction.response.send_message("Message deleted.", ephemeral=True)
            self.stop()  # Stop listening for further interactions.
        except discord.NotFound:
            logger.error(f"Message {interaction.message.id} not found when trying to delete")
            await interaction.response.send_message("Message already deleted.", ephemeral=True)

@client.event
async def on_ready():
    logger.info(f"Logged in as {client.user}!")
    # Sync the slash commands with Discord.
    try:
        await tree.sync()
        logger.info("Slash commands synced successfully.")
    except Exception as e:
        logger.error(f"Failed to sync slash commands: {e}")

@client.event
async def on_message(message):
    # Avoid processing the bot's own messages.
    if message.author == client.user:
        return

    # Process only messages that contain twitter.com or x.com links.
    urls = URL_REGEX.findall(message.content)
    if urls:
        # Apply per-user rate limiting.
        now = time.time()
        last_time = user_rate_limit.get(message.author.id, 0)
        if now - last_time < RATE_LIMIT_SECONDS:
            logger.info(f"User {message.author} is rate limited. Time since last processing: {now - last_time:.2f} seconds.")
            return
        user_rate_limit[message.author.id] = now

        logger.info(f"Processing message from {message.author} (ID: {message.id}) with URLs: {urls}")

        # Replace twitter.com or x.com with vxtwitter.com.
        modified_urls = [
            re.sub(r'(twitter\.com|x\.com)', 'vxtwitter.com', url, flags=re.IGNORECASE)
            for url in urls
        ]
        response = "\n".join(modified_urls)

        # Attempt to delete the original message.
        try:
            await message.delete()
            logger.info(f"Deleted original message {message.id} from {message.author}")
        except discord.Forbidden:
            logger.warning(f"Missing permissions to delete message {message.id} from {message.author}")
        except discord.HTTPException as e:
            logger.error(f"Failed to delete message {message.id}: {e}")

        # Create a view with the delete button.
        view = DeleteButtonView(message.author.id)

        # Try sending the modified message via a webhook to mimic the user's profile.
        try:
            webhook = await message.channel.create_webhook(name="TempWebhook")
            logger.info(f"Created temporary webhook in channel {message.channel} for message {message.id}")

            await webhook.send(
                content=response,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
                view=view
            )
            logger.info(f"Sent modified message via webhook for message {message.id}")
            await webhook.delete()
            logger.info(f"Deleted temporary webhook for message {message.id}")
        except Exception as e:
            logger.error(f"Webhook error for message {message.id}: {e}")
            # Fallback: send as the bot if webhook fails.
            try:
                await message.channel.send(response, view=view)
                logger.info(f"Sent modified message via bot fallback for message {message.id}")
            except Exception as e2:
                logger.error(f"Failed to send fallback message for message {message.id}: {e2}")

client.run(TOKEN)