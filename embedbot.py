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

# Bot statistics
bot_start_time = time.time()
links_processed = 0
version = "1.1.1"  # Bot version

# Slash command: /status
@tree.command(name="status", description="View detailed bot status information")
async def status(interaction: discord.Interaction):
    logger.info(f"Received /status command from {interaction.user} in guild {interaction.guild}")
    
    # Defer the response to avoid timeout
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Calculate uptime
        uptime_seconds = int(time.time() - bot_start_time)
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        
        # Get server count
        server_count = len(client.guilds)
        
        # Format the status embed
        embed = discord.Embed(
            title="VXTwitter Bot Status",
            description="Transforms Twitter/X links for better embeds",
            color=0x1DA1F2,  # Twitter blue color
            timestamp=discord.utils.utcnow()
        )
        
        # Bot info section
        embed.add_field(name="🤖 Bot Version", value=version, inline=True)
        embed.add_field(name="⏱️ Uptime", value=uptime_str, inline=True)
        embed.add_field(name="⚡ Status", value="Online", inline=True)
        
        # Statistics section
        embed.add_field(name="🔄 Links Processed", value=links_processed, inline=True)
        embed.add_field(name="🏠 Servers", value=server_count, inline=True)
        embed.add_field(name="⏳ Rate Limit", value=f"{RATE_LIMIT_SECONDS} seconds", inline=True)
        
        # If in a guild, add guild-specific info
        if interaction.guild:
            guild_users_count = len(interaction.guild.members)
            embed.add_field(
                name="📊 Server Info", 
                value=f"Name: {interaction.guild.name}\nMembers: {guild_users_count}", 
                inline=False
            )
        
        # Set footer with command help reminder
        embed.set_footer(text="Use /help for available commands")
        
        # Send the embed
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        logger.error(f"Error generating status: {e}")
        await interaction.followup.send("Error generating status information. Please try again later.", ephemeral=True)

# Slash command: /help
@tree.command(name="help", description="Show help information about the bot")
async def help_command(interaction: discord.Interaction):
    logger.info(f"Received /help command from {interaction.user} in guild {interaction.guild}")
    # Defer the response to avoid timeout
    await interaction.response.defer(ephemeral=True)
    
    help_text = (
        "This bot replaces `twitter.com` or `x.com` links with `vxtwitter.com` for better embeds.\n\n"
        "**Commands:**\n"
        "`/status` - Check bot status and statistics.\n"
        "`/help` - Show this help message.\n"
        "`/emulate` - Choose whether the bot posts links as you or as itself.\n\n"
        "**Post Controls:**\n"
        "When you share a Twitter/X link, it will be automatically converted, and you'll see:\n"
        "- A `Delete` button - Remove your posted link\n"
        "- A `Toggle Emulation` button - Quickly switch between posting styles\n\n"
        "Just share a Twitter/X link in any channel, and the bot will handle the rest!"
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

# Create a view with buttons for message management
class MessageControlView(discord.ui.View):
    def __init__(self, original_author_id: int, timeout: float = 604800):  # 7 days
        super().__init__(timeout=timeout)
        self.original_author_id = original_author_id
        self.message = None  # Will store reference to the message
        
    async def on_timeout(self):
        """Handle the view timeout by modifying the message if possible"""
        try:
            # Try to disable the buttons when they time out
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
        # Only allow the original poster to delete the message
        if interaction.user.id != self.original_author_id:
            logger.warning(f"Unauthorized delete attempt by {interaction.user}")
            await interaction.response.send_message("You are not allowed to delete this message.", ephemeral=True)
            return

        try:
            await interaction.message.delete()
            logger.info(f"Message {interaction.message.id} deleted by {interaction.user}")
            await interaction.response.send_message("Message deleted.", ephemeral=True)
            self.stop()  # Stop listening for further interactions
        except discord.NotFound:
            logger.error(f"Message {interaction.message.id} not found when trying to delete")
            await interaction.response.send_message("Message already deleted.", ephemeral=True)
    
    @discord.ui.button(label="Toggle User Emulation", style=discord.ButtonStyle.secondary)
    async def toggle_emulation_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"Toggle User emulation button clicked by {interaction.user}")
        # Only allow the original poster to change their preference
        if interaction.user.id != self.original_author_id:
            logger.warning(f"Unauthorized emulation toggle attempt by {interaction.user}")
            await interaction.response.send_message("You can only change your own emulation preference.", ephemeral=True)
            return
        
        # Toggle the user's emulation preference
        current_preference = user_emulation_preferences.get(interaction.user.id, DEFAULT_EMULATION)
        new_preference = not current_preference
        user_emulation_preferences[interaction.user.id] = new_preference
        
        # Notify the user of the change
        if new_preference:
            message = "Future posts will use your name and avatar."
        else:
            message = "Future posts will show as coming from the bot with a link to your profile."
        
        await interaction.response.send_message(message, ephemeral=True)
        logger.info(f"User {interaction.user} set emulation preference to {new_preference}")

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
        
        # Update statistics
        global links_processed
        links_processed += len(urls)

        # Attempt to delete the original message.
        try:
            await message.delete()
            logger.info(f"Deleted original message {message.id} from {message.author}")
        except discord.Forbidden:
            logger.warning(f"Missing permissions to delete message {message.id} from {message.author}")
        except discord.HTTPException as e:
            logger.error(f"Failed to delete message {message.id}: {e}")

        # Create a view with buttons for message control
        view = MessageControlView(message.author.id)

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
                    # Create a clickable link to the user's profile
                    user_link = f"[{message.author.display_name}](https://discord.com/users/{message.author.id})"
                    sent_message = await message.channel.send(f"**Link shared by {user_link}:** {response}", view=view)
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