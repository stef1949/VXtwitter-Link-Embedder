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

# User preferences for emulation (True = emulate user, False = post as bot)
user_emulation_preferences = {}  # Maps user ID to boolean preference
DEFAULT_EMULATION = True  # Default to emulating users

# Slash command: /status
@tree.command(name="status", description="Check the bot's status")
async def status(interaction: discord.Interaction):
    logger.info(f"Received /status command from {interaction.user} in guild {interaction.guild}")
    try:
        await interaction.response.send_message("Bot is running!", ephemeral=True)
    except discord.errors.NotFound:
        logger.warning(f"Interaction timed out for status command from {interaction.user}")
    except Exception as e:
        logger.error(f"Error responding to status command: {e}")

# Slash command: /help
@tree.command(name="help", description="Show help information about the bot")
async def help_command(interaction: discord.Interaction):
    logger.info(f"Received /help command from {interaction.user} in guild {interaction.guild}")
    # Defer the response to avoid timeout
    await interaction.response.defer(ephemeral=True)
    
    help_text = (
        "This bot replaces `twitter.com` or `x.com` links with `vxtwitter.com` and provides a delete button "
        "for the original poster to delete the message.\n\n"
        "**Commands:**\n"
        "`/status` - Check if the bot is running.\n"
        "`/help` - Show this help message.\n"
        "`/emulate` - Choose whether the bot posts links as you or as itself.\n\n"
        "Just send a message containing a Twitter/X link, and the bot will take care of the rest."
    )
    
    try:
        await interaction.followup.send(help_text, ephemeral=True)
    except Exception as e:
        logger.error(f"Error responding to help command: {e}")

# Slash command: /emulate
@tree.command(name="emulate", description="Choose whether the bot should emulate your identity when posting links")
async def emulate(interaction: discord.Interaction, enable: bool):
    """Set whether the bot should post as you or as itself.
    
    Parameters:
    -----------
    enable: bool
        True to have the bot post links with your name and avatar, False to have it post as itself.
    """
    logger.info(f"Received /emulate command from {interaction.user} with value {enable}")
    
    # Defer the response to avoid timeout
    await interaction.response.defer(ephemeral=True)
    
    user_emulation_preferences[interaction.user.id] = enable
    
    if enable:
        message = "The bot will now post Twitter/X links with your name and avatar."
    else:
        message = "The bot will now post Twitter/X links as itself and mention you."
    
    try:
        await interaction.followup.send(message, ephemeral=True)
    except Exception as e:
        logger.error(f"Error responding to emulate command: {e}")

# Create a view with a button that allows only the original poster to delete the message.
class DeleteButtonView(discord.ui.View):
    def __init__(self, original_author_id: int, timeout: float = 604800):  # 7 days instead of 24 hours
        super().__init__(timeout=timeout)
        self.original_author_id = original_author_id
        
    async def on_timeout(self):
        """Handle the view timeout by modifying the message if possible"""
        try:
            # Try to disable the button when it times out
            for item in self.children:
                item.disabled = True
                
            # Update the message with disabled buttons if it still exists
            if hasattr(self, "message") and self.message:
                await self.message.edit(view=self)
        except Exception as e:
            logger.error(f"Error handling view timeout: {e}")
            # Fail silently if the message was deleted or there's another issue

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

        # Check the user's emulation preference
        should_emulate = user_emulation_preferences.get(message.author.id, DEFAULT_EMULATION)
        
        if should_emulate:
            # Try sending the modified message via a webhook to mimic the user's profile.
            try:
                webhook = await message.channel.create_webhook(name="TempWebhook")
                logger.info(f"Created temporary webhook in channel {message.channel} for message {message.id}")

                sent_message = await webhook.send(
                    content=response,
                    username=message.author.display_name,
                    avatar_url=message.author.display_avatar.url,
                    view=view
                )
                view.message = sent_message
                logger.info(f"Sent modified message via webhook for message {message.id}")
                await webhook.delete()
                logger.info(f"Deleted temporary webhook for message {message.id}")
            except Exception as e:
                logger.error(f"Webhook error for message {message.id}: {e}")
                # Fallback: send as the bot if webhook fails.
                try:
                    sent_message = await message.channel.send(f"**Link shared by {message.author.display_name}:** {response}", view=view)
                    view.message = sent_message
                    logger.info(f"Sent modified message via bot fallback for message {message.id}")
                except Exception as e2:
                    logger.error(f"Failed to send fallback message for message {message.id}: {e2}")
        else:
            # Send as the bot directly, with attribution to the original user
            try:
                sent_message = await message.channel.send(f"**Link shared by {message.author.display_name}:** {response}", view=view)
                view.message = sent_message
                logger.info(f"Sent modified message as bot (per user preference) for message {message.id}")
            except Exception as e:
                logger.error(f"Failed to send message as bot for message {message.id}: {e}")

client.run(TOKEN)