import logging
import discord
import re
import os
import time
import sys
import asyncio
from discord.ext import commands

# Configure logging to show the time, logger name, level, and message.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
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
version = "1.2.2"  # Bot version

# Security settings
GLOBAL_RATE_LIMIT = 30  # Maximum requests per minute across all users
global_request_timestamps = []  # List of timestamps for global rate limiting
BANNED_USERS = set()  # Set of banned user IDs
SERVER_BLACKLIST = set()  # Set of blacklisted server IDs
ADMIN_IDS = set()  # Set of bot admin user IDs

# Server-specific settings
server_settings = {}  # Maps server ID to settings dict

# Utility functions for security
def check_global_rate_limit():
    """Check if the global rate limit has been exceeded"""
    now = time.time()
    # Remove timestamps older than 60 seconds
    global global_request_timestamps
    global_request_timestamps = [ts for ts in global_request_timestamps if now - ts < 60]
    # Check if we've exceeded the global rate limit
    if len(global_request_timestamps) >= GLOBAL_RATE_LIMIT:
        return False
    # Add current timestamp and return True (not rate limited)
    global_request_timestamps.append(now)
    return True

def is_user_banned(user_id):
    """Check if a user is banned from using the bot"""
    return user_id in BANNED_USERS

def is_admin(user_id):
    """Check if a user is a bot admin"""
    # First check if the user is in the admin set
    if user_id in ADMIN_IDS:
        return True
    
    # Return a default value - will be updated on the next is_admin check
    return False

async def refresh_admin_status():
    """Refresh the admin status from application info"""
    try:
        application = await client.application_info()
        
        # Check if the bot is owned by a team
        if application.team:
            # Add all team members as admins
            for team_member in application.team.members:
                ADMIN_IDS.add(team_member.id)
                logger.info(f"Added team member {team_member.id} ({team_member.name}) as admin")
        else:
            # Add owner as admin for non-team bots
            ADMIN_IDS.add(application.owner.id)
    except Exception as e:
        logger.error(f"Failed to refresh admin status: {e}")

async def check_team_membership(user_id):
    """Check if a user is a member of the bot's team"""
    try:
        application = await client.application_info()
        
        # Check if the bot is owned by a team
        if application.team:
            for team_member in application.team.members:
                if team_member.id == user_id:
                    logger.info(f"User {user_id} is a member of team {application.team.name}")
                    return True
        
        # If not a team bot or user not in team
        return False
    except Exception as e:
        logger.error(f"Failed to check team membership: {e}")
        return False

def is_server_blacklisted(server_id):
    """Check if a server is blacklisted"""
    return server_id in SERVER_BLACKLIST

def get_server_setting(server_id, key, default=None):
    """Get a server-specific setting with fallback to default"""
    if server_id not in server_settings:
        server_settings[server_id] = {}
    return server_settings[server_id].get(key, default)

def set_server_setting(server_id, key, value):
    """Set a server-specific setting"""
    if server_id not in server_settings:
        server_settings[server_id] = {}
    server_settings[server_id][key] = value

def sanitize_url(url):
    """Sanitize a URL to prevent potential injection attacks"""
    # Remove any characters that aren't allowed in URLs
    return re.sub(r'[^\w\.\/\:\-\?\&\=\%]', '', url)

# Security event logging
def log_security_event(event_type, user_id, guild_id=None, details=None):
    """Log security-related events for auditing"""
    logger.warning(f"SECURITY: {event_type} - User: {user_id}, Guild: {guild_id}, Details: {details}")

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
        
        # Check webhook permissions in the current channel
        webhook_perm = "N/A"
        if interaction.channel and isinstance(interaction.channel, discord.TextChannel):
            bot_permissions = interaction.channel.permissions_for(interaction.guild.me)
            webhook_perm = "✅ Yes" if bot_permissions.manage_webhooks else "❌ No"
        
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
        
        # Team and permissions section
        is_team_bot = False
        team_name = "N/A"
        try:
            application = await client.application_info()
            is_team_bot = application.team is not None
            if is_team_bot and application.team:
                team_name = application.team.name
        except Exception as e:
            logger.error(f"Failed to get application info: {e}")
        
        embed.add_field(name="👥 Team Bot", value=f"{'Yes' if is_team_bot else 'No'}", inline=True)
        if is_team_bot:
            embed.add_field(name="🏢 Team Name", value=team_name, inline=True)
        embed.add_field(name="🔐 Can Create Webhooks", value=webhook_perm, inline=True)
        
        # Show admin status
        is_admin = interaction.user.id in ADMIN_IDS
        embed.add_field(name="👑 Admin Status", value="✅ Admin" if is_admin else "❌ Not Admin", inline=True)
        
        # If in a guild, add guild-specific info
        if interaction.guild:
            guild_users_count = len(interaction.guild.members)
            # Check if the user is a server admin
            is_server_admin = False
            if interaction.guild.get_member(interaction.user.id):
                member = interaction.guild.get_member(interaction.user.id)
                is_server_admin = member.guild_permissions.administrator
            
            embed.add_field(
                name="📊 Server Info", 
                value=f"Name: {interaction.guild.name}\nMembers: {guild_users_count}\nYou are{' ' if is_server_admin else ' not '}a server admin", 
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
    
    # Check webhook permissions in this channel
    webhook_permissions = False
    if interaction.channel and isinstance(interaction.channel, discord.TextChannel):
        bot_permissions = interaction.channel.permissions_for(interaction.guild.me)
        webhook_permissions = bot_permissions.manage_webhooks
    
    # Adjust help text based on permissions
    emulation_note = ""
    if not webhook_permissions:
        emulation_note = "\n⚠️ **Note:** User emulation requires webhook permissions, which the bot doesn't have in this channel."
    
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
        f"Just share a Twitter/X link in any channel, and the bot will handle the rest!{emulation_note}"
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
    
    # Check if the bot has webhook permissions in this channel (if enable is True)
    can_use_webhooks = False
    if enable and interaction.channel and isinstance(interaction.channel, discord.TextChannel):
        bot_permissions = interaction.channel.permissions_for(interaction.guild.me)
        can_use_webhooks = bot_permissions.manage_webhooks
    
    user_emulation_preferences[interaction.user.id] = enable
    
    if enable:
        if can_use_webhooks:
            message = "The bot will now post Twitter/X links with your name and avatar."
        else:
            message = ("The bot will try to post Twitter/X links with your name and avatar. However, it may not work in "
                       "some channels due to missing webhook permissions. In those cases, it will mention you instead.")
    else:
        message = "The bot will now post Twitter/X links as itself and mention you."
    
    try:
        await interaction.followup.send(message, ephemeral=True)
    except Exception as e:
        logger.error(f"Error responding to emulate command: {e}")

# Admin only commands
@tree.command(name="listadmins", description="List all bot administrators")
@discord.app_commands.checks.cooldown(1, 5.0)  # 1 use per 5 seconds per user
async def list_admins(interaction: discord.Interaction):
    """List all bot administrators"""
    logger.info(f"Received /listadmins command from {interaction.user}")
    
    # Check if the user is an admin or server owner
    is_bot_admin = is_admin(interaction.user.id)
    is_server_owner = interaction.guild and interaction.guild.owner_id == interaction.user.id
    
    if not (is_bot_admin or is_server_owner):
        log_security_event("UNAUTHORIZED_ADMIN_COMMAND", interaction.user.id, 
                          interaction.guild_id if interaction.guild else None,
                          "Attempted to list admins")
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    # Get admin details
    try:
        admin_details = []
        for admin_id in ADMIN_IDS:
            try:
                user = await client.fetch_user(admin_id)
                admin_details.append(f"• {user.name} (ID: {admin_id})")
            except:
                admin_details.append(f"• Unknown User (ID: {admin_id})")
        
        if admin_details:
            admin_list = "\n".join(admin_details)
            await interaction.response.send_message(f"**Bot Administrators:**\n{admin_list}", ephemeral=True)
        else:
            await interaction.response.send_message("No administrators configured.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error listing admins: {e}")
        await interaction.response.send_message("An error occurred while listing administrators.", ephemeral=True)
@tree.command(name="ban", description="[ADMIN] Ban a user from using the bot")
@discord.app_commands.checks.cooldown(1, 5.0)  # 1 use per 5 seconds per user
async def ban_user(interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided"):
    """Ban a user from using the bot (admin only)"""
    logger.info(f"Received /ban command from {interaction.user} for user {user.id}")
    
    # Only allow admins to use this command
    if not is_admin(interaction.user.id):
        log_security_event("UNAUTHORIZED_ADMIN_COMMAND", interaction.user.id, 
                          interaction.guild_id if interaction.guild else None,
                          f"Attempted to ban user {user.id}")
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    # Add the user to the banned list
    BANNED_USERS.add(user.id)
    log_security_event("USER_BANNED", user.id, 
                      interaction.guild_id if interaction.guild else None,
                      f"Banned by {interaction.user.id}: {reason}")
    
    await interaction.response.send_message(f"User {user.mention} has been banned from using the bot.", ephemeral=True)

@tree.command(name="unban", description="[ADMIN] Unban a user from using the bot")
@discord.app_commands.checks.cooldown(1, 5.0)  # 1 use per 5 seconds per user
async def unban_user(interaction: discord.Interaction, user: discord.User):
    """Unban a user from using the bot (admin only)"""
    logger.info(f"Received /unban command from {interaction.user} for user {user.id}")
    
    # Only allow admins to use this command
    if not is_admin(interaction.user.id):
        log_security_event("UNAUTHORIZED_ADMIN_COMMAND", interaction.user.id, 
                          interaction.guild_id if interaction.guild else None,
                          f"Attempted to unban user {user.id}")
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    # Remove the user from the banned list if they're in it
    if user.id in BANNED_USERS:
        BANNED_USERS.remove(user.id)
        log_security_event("USER_UNBANNED", user.id, 
                          interaction.guild_id if interaction.guild else None,
                          f"Unbanned by {interaction.user.id}")
        await interaction.response.send_message(f"User {user.mention} has been unbanned from using the bot.", ephemeral=True)
    else:
        await interaction.response.send_message(f"User {user.mention} was not banned.", ephemeral=True)

@tree.command(name="addadmin", description="[ADMIN] Add a bot administrator")
@discord.app_commands.checks.cooldown(1, 5.0)  # 1 use per 5 seconds per user
async def add_admin(interaction: discord.Interaction, user: discord.User):
    """Add a bot administrator (admin only)"""
    logger.info(f"Received /addadmin command from {interaction.user} for user {user.id}")
    
    # This command is restricted to existing admins
    if not is_admin(interaction.user.id):
        log_security_event("UNAUTHORIZED_ADMIN_COMMAND", interaction.user.id, 
                          interaction.guild_id if interaction.guild else None,
                          f"Attempted to add admin {user.id}")
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    # Add the user to the admin list
    ADMIN_IDS.add(user.id)
    log_security_event("ADMIN_ADDED", user.id, 
                      interaction.guild_id if interaction.guild else None,
                      f"Added by {interaction.user.id}")
    
    await interaction.response.send_message(f"User {user.mention} has been added as a bot administrator.", ephemeral=True)

@tree.command(name="server_blacklist", description="[ADMIN] Add/remove a server from the blacklist")
@discord.app_commands.checks.cooldown(1, 5.0)  # 1 use per 5 seconds per user
async def server_blacklist(interaction: discord.Interaction, server_id: str, add_to_blacklist: bool):
    """Add or remove a server from the blacklist (admin only)"""
    logger.info(f"Received /server_blacklist command from {interaction.user} for server {server_id}")
    
    # Only allow admins to use this command
    if not is_admin(interaction.user.id):
        log_security_event("UNAUTHORIZED_ADMIN_COMMAND", interaction.user.id, 
                          interaction.guild_id if interaction.guild else None,
                          f"Attempted to modify server blacklist for {server_id}")
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    try:
        # Convert the server ID to an integer
        server_id_int = int(server_id)
        
        if add_to_blacklist:
            SERVER_BLACKLIST.add(server_id_int)
            log_security_event("SERVER_BLACKLISTED", interaction.user.id, server_id_int,
                              f"Server blacklisted by {interaction.user.id}")
            await interaction.response.send_message(f"Server ID {server_id} has been added to the blacklist.", ephemeral=True)
        else:
            if server_id_int in SERVER_BLACKLIST:
                SERVER_BLACKLIST.remove(server_id_int)
                log_security_event("SERVER_UNBLACKLISTED", interaction.user.id, server_id_int,
                                  f"Server removed from blacklist by {interaction.user.id}")
                await interaction.response.send_message(f"Server ID {server_id} has been removed from the blacklist.", ephemeral=True)
            else:
                await interaction.response.send_message(f"Server ID {server_id} was not in the blacklist.", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("Invalid server ID format. Please provide a valid ID.", ephemeral=True)

# Server configuration commands (for server admins)
@tree.command(name="server_settings", description="Configure bot settings for this server (requires Manage Server permission)")
@discord.app_commands.checks.cooldown(1, 5.0)  # 1 use per 5 seconds per user
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def configure_server(interaction: discord.Interaction, enable_bot: bool = None, allowed_channels: bool = None):
    """Configure server-specific settings for the bot"""
    logger.info(f"Received /server_settings command from {interaction.user} in guild {interaction.guild}")
    
    # Make sure this is used in a server
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return
    
    # Initialize server settings if they don't exist
    if interaction.guild.id not in server_settings:
        server_settings[interaction.guild.id] = {
            "enabled": True,
            "restricted_to_channels": False
        }
    
    # Update settings if provided
    settings_updated = False
    if enable_bot is not None:
        set_server_setting(interaction.guild.id, "enabled", enable_bot)
        settings_updated = True
    
    if allowed_channels is not None:
        set_server_setting(interaction.guild.id, "restricted_to_channels", allowed_channels)
        settings_updated = True
    
    # Send current settings
    current_settings = server_settings[interaction.guild.id]
    embed = discord.Embed(
        title=f"Bot Settings for {interaction.guild.name}",
        color=discord.Color.blue(),
        description="Current configuration for this server"
    )
    
    embed.add_field(name="Bot Enabled", value="✅ Yes" if current_settings.get("enabled", True) else "❌ No", inline=True)
    embed.add_field(name="Channel Restriction", value="✅ Enabled" if current_settings.get("restricted_to_channels", False) else "❌ Disabled", inline=True)
    
    # Add additional fields for other settings as needed
    
    await interaction.response.send_message(
        content="Settings updated." if settings_updated else "Current server settings:",
        embed=embed,
        ephemeral=True
    )
    
    # Log the configuration change
    if settings_updated:
        log_security_event("SERVER_SETTINGS_CHANGED", interaction.user.id, interaction.guild.id,
                         f"Settings changed by {interaction.user.id}")

@tree.command(name="channel_whitelist", description="Add/remove channels from the whitelist (requires Manage Server permission)")
@discord.app_commands.checks.cooldown(1, 5.0)  # 1 use per 5 seconds per user
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def channel_whitelist(interaction: discord.Interaction, channel: discord.TextChannel, add_to_whitelist: bool):
    """Add or remove a channel from the server's whitelist"""
    logger.info(f"Received /channel_whitelist command from {interaction.user} for channel {channel.id}")
    
    # Make sure this is used in a server
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return
    
    # Initialize server settings if they don't exist
    if interaction.guild.id not in server_settings:
        server_settings[interaction.guild.id] = {
            "enabled": True,
            "restricted_to_channels": False,
            "whitelisted_channels": set()
        }
    
    # Initialize whitelisted channels if needed
    if "whitelisted_channels" not in server_settings[interaction.guild.id]:
        server_settings[interaction.guild.id]["whitelisted_channels"] = set()
    
    whitelist = server_settings[interaction.guild.id]["whitelisted_channels"]
    
    if add_to_whitelist:
        whitelist.add(channel.id)
        await interaction.response.send_message(f"Channel {channel.mention} has been added to the whitelist.", ephemeral=True)
    else:
        if channel.id in whitelist:
            whitelist.remove(channel.id)
            await interaction.response.send_message(f"Channel {channel.mention} has been removed from the whitelist.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Channel {channel.mention} was not in the whitelist.", ephemeral=True)
    
    # Log the whitelist change
    log_security_event("CHANNEL_WHITELIST_CHANGED", interaction.user.id, interaction.guild.id,
                     f"Channel {channel.id} {'added to' if add_to_whitelist else 'removed from'} whitelist by {interaction.user.id}")

# Create a view with buttons for message management
class MessageControlView(discord.ui.View):
    def __init__(self, timeout: float = 604800):  # 7 days
        super().__init__(timeout=timeout)
        self.message = None  # Will store reference to the message
        self.original_author_id = None  # Will store the original author's ID
        
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

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, custom_id="delete_button")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete button that works even after bot restart by checking the original message"""
        logger.info(f"Delete button clicked by {interaction.user} in message {interaction.message.id}")
        
        # Get the message to find who shared the link
        try:
            message = interaction.message
            
            # First check if we have the original author ID stored in the view
            author_id = None
            if hasattr(self, 'original_author_id') and self.original_author_id:
                author_id = self.original_author_id
                logger.info(f"Using stored original author ID: {author_id}")
            
            # If not, try to extract from message content
            if not author_id:
                # Log message content for debugging
                logger.info(f"Message content for delete: {message.content}")
                
                # Try to find an @mention in the message content with more flexible patterns
                if message.content:
                    # Try different regex patterns to extract user ID
                    mention_patterns = [
                        r'<@!?(\d+)>',  # Standard mention format <@123456789> or <@!123456789>
                        r'by <@!?(\d+)>',  # Matches "by @user"
                        r'by <@!?(\d+)',  # Without closing bracket
                        r'<@!?(\d+)',  # Just the opening of mention
                        r'(\d{17,20})',  # Any 17-20 digit number (likely a user ID)
                    ]
                    
                    for pattern in mention_patterns:
                        mention_match = re.search(pattern, message.content)
                        if mention_match:
                            author_id = int(mention_match.group(1))
                            logger.info(f"Found author ID {author_id} using pattern {pattern}")
                            break
            
            # For messages sent via webhook (user emulation enabled)
            if not author_id and hasattr(message, 'webhook_id') and message.webhook_id:
                # In this case, we can't reliably determine the original author from the message alone
                # Use a fallback check to see if the requesting user is the message author
                logger.info(f"Webhook message detected for delete: {message.webhook_id}")
                if interaction.user.id == message.author.id:
                    author_id = interaction.user.id
                    logger.info(f"Using interaction user ID as author for delete: {author_id}")
            
            # Always allow server admins to delete
            is_admin_in_server = False
            if interaction.guild and interaction.guild.get_member(interaction.user.id):
                member = interaction.guild.get_member(interaction.user.id)
                is_admin_in_server = member.guild_permissions.administrator
                if is_admin_in_server:
                    logger.info(f"User {interaction.user.id} is a server admin, allowing deletion")
            
            # Allow deletion by bot admins too
            is_bot_admin = is_admin(interaction.user.id)
            if is_bot_admin:
                logger.info(f"User {interaction.user.id} is a bot admin, allowing deletion")
            
            # Always allow server owners to delete
            is_server_owner = False
            if interaction.guild and interaction.guild.owner_id == interaction.user.id:
                is_server_owner = True
                logger.info(f"User {interaction.user.id} is server owner, allowing deletion")
        
            # Only allow the original poster or admins to delete the message
            logger.info(f"Delete check - Author: {author_id}, User: {interaction.user.id}, Admin: {is_admin_in_server}, Owner: {is_server_owner}")
            if (author_id and interaction.user.id == author_id) or is_admin_in_server or is_bot_admin or is_server_owner:
                await message.delete()
                logger.info(f"Message {message.id} deleted by {interaction.user}")
                await interaction.response.send_message("Message deleted.", ephemeral=True)
            else:
                logger.warning(f"Unauthorized delete attempt by {interaction.user}")
                await interaction.response.send_message("You are not allowed to delete this message.", ephemeral=True)
                
        except discord.NotFound:
            logger.error(f"Message {interaction.message.id} not found when trying to delete")
            await interaction.response.send_message("Message already deleted.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in delete button: {e}")
            await interaction.response.send_message("Error processing request.", ephemeral=True)
    
    @discord.ui.button(label="Toggle Emulation", style=discord.ButtonStyle.secondary, custom_id="toggle_emulation")
    async def toggle_emulation_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle emulation button that works after restart by extracting user ID from message"""
        logger.info(f"Toggle emulation button clicked by {interaction.user}")
        
        # Extract author ID from the message content if possible
        author_id = None
        message = interaction.message
        
        # Log message content for debugging
        logger.info(f"Message content for toggle: {message.content}")
        
        # Try to find an @mention in the message content with more flexible patterns
        if message.content:
            # Try different regex patterns to extract user ID
            mention_patterns = [
                r'<@!?(\d+)>',  # Standard mention format <@123456789> or <@!123456789>
                r'by <@!?(\d+)>',  # Matches "by @user"
                r'by <@!?(\d+)',  # Without closing bracket
                r'<@!?(\d+)',  # Just the opening of mention
                r'(\d{17,20})',  # Any 17-20 digit number (likely a user ID)
            ]
            
            for pattern in mention_patterns:
                mention_match = re.search(pattern, message.content)
                if mention_match:
                    author_id = int(mention_match.group(1))
                    logger.info(f"Found author ID {author_id} using pattern {pattern}")
                    break
        
        # For messages sent via webhook (user emulation enabled)
        if not author_id and hasattr(message, 'webhook_id') and message.webhook_id:
            logger.info(f"Webhook message detected for toggle: {message.webhook_id}")
            # For webhook messages, always allow the interaction user to modify settings
            # This is a reasonable assumption since mostly only the original poster would try to toggle
            author_id = interaction.user.id
            logger.info(f"Using interaction user ID as author for toggle: {author_id}")
        
        # Always allow server owners to toggle
        is_server_owner = False
        if interaction.guild and interaction.guild.owner_id == interaction.user.id:
            is_server_owner = True
            logger.info(f"User {interaction.user.id} is server owner, allowing toggle")
        
        # Check if user is a bot admin
        is_bot_admin = is_admin(interaction.user.id)
        if is_bot_admin:
            logger.info(f"User {interaction.user.id} is bot admin, allowing toggle")
        
        # Only allow the original poster, server owner, or bot admin to change preference
        logger.info(f"Toggle check - Author: {author_id}, User: {interaction.user.id}, Admin: {is_bot_admin}, Owner: {is_server_owner}")
        if (author_id and interaction.user.id == author_id) or is_server_owner or is_bot_admin:
            # Toggle the user's emulation preference
            user_id_to_toggle = author_id if author_id else interaction.user.id
            current_preference = user_emulation_preferences.get(user_id_to_toggle, DEFAULT_EMULATION)
            new_preference = not current_preference
            user_emulation_preferences[user_id_to_toggle] = new_preference
            
            # Notify the user of the change
            if new_preference:
                msg = "Future posts will use your name and avatar."
            else:
                msg = "Future posts will show as coming from the bot with a mention to you."
            
            if author_id and interaction.user.id != author_id:
                # If admin is changing someone else's preference
                try:
                    user = await client.fetch_user(author_id)
                    username = user.name
                except:
                    username = f"User {author_id}"
                msg = f"Changed {username}'s emulation preference. {msg}"
            
            await interaction.response.send_message(msg, ephemeral=True)
            logger.info(f"User {user_id_to_toggle} emulation preference set to {new_preference} by {interaction.user.id}")
        else:
            logger.warning(f"Unauthorized emulation toggle attempt by {interaction.user}")
            await interaction.response.send_message("You can only change your own emulation preference.", ephemeral=True)

# Error handling for Discord.py
@tree.error
async def on_command_error(interaction: discord.Interaction, error):
    """Handle errors from slash commands"""
    if isinstance(error, discord.app_commands.errors.CommandOnCooldown):
        # Handle cooldown errors
        await interaction.response.send_message(
            f"This command is on cooldown. Please try again in {error.retry_after:.1f} seconds.",
            ephemeral=True
        )
        logger.warning(f"Command cooldown triggered by {interaction.user.id}: {error}")
    elif isinstance(error, discord.app_commands.errors.MissingPermissions):
        # Handle permission errors
        await interaction.response.send_message(
            "You don't have the required permissions to use this command.",
            ephemeral=True
        )
        log_security_event("PERMISSION_ERROR", interaction.user.id, 
                         interaction.guild_id if interaction.guild else None,
                         f"Missing permissions for command: {interaction.command.name}")
    else:
        # Handle other errors
        logger.error(f"Command error: {error}")
        try:
            await interaction.response.send_message(
                "An error occurred while processing this command. Please try again later.",
                ephemeral=True
            )
        except discord.errors.InteractionResponded:
            # If the interaction was already responded to
            pass

# Global exception handler
@client.event
async def on_error(event, *args, **kwargs):
    """Handle global errors"""
    logger.error(f"Discord error in {event}: {sys.exc_info()[1]}")

# Periodic security tasks
async def security_maintenance():
    """Perform periodic security-related maintenance tasks"""
    while True:
        try:
            # Log statistics
            logger.info(f"Bot Stats: {links_processed} links processed, {len(user_emulation_preferences)} user preferences stored")
            logger.info(f"Security: {len(BANNED_USERS)} banned users, {len(SERVER_BLACKLIST)} blacklisted servers")
            
            # Prune old rate limit data
            now = time.time()
            for user_id in list(user_rate_limit.keys()):
                if now - user_rate_limit[user_id] > 3600:  # Remove entries older than 1 hour
                    del user_rate_limit[user_id]
            
            # Wait for 1 hour before the next run
            await asyncio.sleep(3600)
        except Exception as e:
            logger.error(f"Error in security maintenance task: {e}")
            await asyncio.sleep(300)  # Wait for 5 minutes before trying again

@client.event
async def on_ready():
    logger.info(f"Logged in as {client.user}!")
    
    # Initialize admins (bot owner or team members)
    try:
        application = await client.application_info()
        
        # Check if the bot is owned by a team
        if application.team:
            logger.info(f"Bot is owned by team: {application.team.name}")
            # Add all team members as admins
            for team_member in application.team.members:
                ADMIN_IDS.add(team_member.id)
                logger.info(f"Team member {team_member.id} ({team_member.name}) added as admin")
        else:
            # Add owner as admin for non-team bots
            ADMIN_IDS.add(application.owner.id)
            logger.info(f"Bot owner {application.owner.id} ({application.owner.name}) added as admin")
    except Exception as e:
        logger.error(f"Failed to initialize admins: {e}")
    
    # Sync the slash commands with Discord.
    try:
        await tree.sync()
        logger.info("Slash commands synced successfully.")
    except Exception as e:
        logger.error(f"Failed to sync slash commands: {e}")
        
    # Set up bot status
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Twitter/X links"))
    
    # Log startup security information
    logger.info(f"Bot started with {len(ADMIN_IDS)} admin(s), {len(BANNED_USERS)} banned user(s), and {len(SERVER_BLACKLIST)} blacklisted server(s)")
    logger.info(f"Global rate limit set to {GLOBAL_RATE_LIMIT} requests per minute")
    
    # Start background tasks
    client.loop.create_task(security_maintenance())

@client.event
async def on_message(message):
    global links_processed  # Declare global at the start of the function
    # Avoid processing the bot's own messages.
    
    if message.author == client.user:
        return
        
    # Check if the user is banned
    if is_user_banned(message.author.id):
        logger.info(f"Ignoring message from banned user {message.author.id}")
        return
        
    # Check if in a blacklisted server
    if message.guild and is_server_blacklisted(message.guild.id):
        logger.info(f"Ignoring message from blacklisted server {message.guild.id}")
        return
        
    # Check server-specific settings
    if message.guild:
        # Check if the bot is enabled for this server
        if not get_server_setting(message.guild.id, "enabled", True):
            logger.info(f"Bot is disabled in server {message.guild.id}")
            return
            
        # Check if the channel is whitelisted (if channel restriction is enabled)
        if get_server_setting(message.guild.id, "restricted_to_channels", False):
            whitelisted_channels = get_server_setting(message.guild.id, "whitelisted_channels", set())
            if message.channel.id not in whitelisted_channels:
                logger.info(f"Ignoring message in non-whitelisted channel {message.channel.id}")
                return
    
    # Check global rate limit
    if not check_global_rate_limit():
        logger.warning("Global rate limit exceeded, ignoring message")
        return

    # Process only messages that contain twitter.com or x.com links using re.finditer
    matches = list(URL_REGEX.finditer(message.content))
    if matches:
        spoiler_urls = []
        non_spoiler_urls = []
        for match in matches:
            url = match.group(0)
            start_index = match.start()
            end_index = match.end()
            # Check if the URL is wrapped in spoiler tags '||'
            if start_index >= 2 and end_index + 2 <= len(message.content) and \
               message.content[start_index-2:start_index] == "||" and \
               message.content[end_index:end_index+2] == "||":
                spoiler_urls.append(url)
            else:
                non_spoiler_urls.append(url)
        
        if spoiler_urls:
            # Process spoilered URLs automatically with a spoiler embed
            now = time.time()
            last_time = user_rate_limit.get(message.author.id, 0)
            if now - last_time < RATE_LIMIT_SECONDS:
                logger.info(f"User {message.author} is rate limited. Time since last processing: {now - last_time:.2f} seconds.")
                return
            user_rate_limit[message.author.id] = now
            
            logger.info(f"Processing spoilered message from {message.author} (ID: {message.id}) with URLs: {spoiler_urls}")
            
            # Sanitize and convert URLs
            spoiler_urls = [sanitize_url(url) for url in spoiler_urls]
            modified_spoiler_urls = [re.sub(r'(twitter\.com|x\.com)', 'vxtwitter.com', url, flags=re.IGNORECASE) for url in spoiler_urls]
            response = "\n".join(modified_spoiler_urls)
            
            
            links_processed += len(spoiler_urls)
            
            # Attempt to delete the original message
            try:
                await message.delete()
                logger.info(f"Deleted original message {message.id} from {message.author}")
            except discord.Forbidden:
                logger.warning(f"Missing permissions to delete message {message.id} from {message.author}")
            except discord.HTTPException as e:
                logger.error(f"Failed to delete message {message.id}: {e}")
            
            # Create a view with buttons for message control and store the original author ID
            view = MessageControlView(timeout=604800)  # 7 days timeout
            view.original_author_id = message.author.id
            
            # Send a spoiler embed using a placeholder message then edit to include the embed
            placeholder = "||spoiler||"
            msg = await message.channel.send(placeholder)
            embed = discord.Embed(
                title="Spoiler Embed",
                description="This tweet is hidden behind a spoiler. Click to reveal.",
                color=0x1DA1F2
            )
            embed.add_field(name="Link", value=response, inline=False)
            await msg.edit(content=placeholder, embed=embed)
        
        elif non_spoiler_urls:
            # Process non-spoiler URLs as before
            
            now = time.time()
            last_time = user_rate_limit.get(message.author.id, 0)
            if now - last_time < RATE_LIMIT_SECONDS:
                logger.info(f"User {message.author} is rate limited. Time since last processing: {now - last_time:.2f} seconds.")
                return
            user_rate_limit[message.author.id] = now
            
            logger.info(f"Processing message from {message.author} (ID: {message.id}) with URLs: {non_spoiler_urls}")
            non_spoiler_urls = [sanitize_url(url) for url in non_spoiler_urls]
            modified_urls = [re.sub(r'(twitter\.com|x\.com)', 'vxtwitter.com', url, flags=re.IGNORECASE) for url in non_spoiler_urls]
            response = "\n".join(modified_urls)
            
            
            links_processed += len(non_spoiler_urls)
            
            try:
                await message.delete()
                logger.info(f"Deleted original message {message.id} from {message.author}")
            except discord.Forbidden:
                logger.warning(f"Missing permissions to delete message {message.id} from {message.author}")
            except discord.HTTPException as e:
                logger.error(f"Failed to delete message {message.id}: {e}")
            
            view = MessageControlView(timeout=604800)
            view.original_author_id = message.author.id
        
        # Check the user's emulation preference and send the message accordingly.
        should_emulate = user_emulation_preferences.get(message.author.id, DEFAULT_EMULATION)
        view.original_author_id = message.author.id
        
        if should_emulate:
            webhook_permissions = False
            if isinstance(message.channel, discord.TextChannel):
                bot_permissions = message.channel.permissions_for(message.guild.me)
                webhook_permissions = bot_permissions.manage_webhooks
            
            if webhook_permissions:
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
                except discord.Forbidden as e:
                    logger.error(f"Webhook permission error for message {message.id}: {e}")
                    try:
                        user_id_mention = f"<@{message.author.id}>"
                        sent_message = await message.channel.send(f"**Link shared by {user_id_mention}:**\n{response}", view=view)
                        view.message = sent_message
                        logger.info(f"Sent modified message via bot fallback for message {message.id}")
                    except Exception as e2:
                        logger.error(f"Failed to send fallback message for message {message.id}: {e2}")
                except Exception as e:
                    logger.error(f"Webhook error for message {message.id}: {e}")
                    try:
                        user_id_mention = f"<@{message.author.id}>"
                        sent_message = await message.channel.send(f"**Link shared by {user_id_mention}:**\n{response}", view=view)
                        view.message = sent_message
                        logger.info(f"Sent modified message via bot fallback for message {message.id}")
                    except Exception as e2:
                        logger.error(f"Failed to send fallback message for message {message.id}: {e2}")
            else:
                logger.warning(f"No webhook permissions in channel {message.channel.id}, using fallback method")
                try:
                    user_id_mention = f"<@{message.author.id}>"
                    sent_message = await message.channel.send(f"**Link shared by {user_id_mention}:**\n{response}", view=view)
                    view.message = sent_message
                    logger.info(f"Sent modified message as bot due to missing webhook permissions for message {message.id}")
                except Exception as e:
                    logger.error(f"Failed to send message as bot for message {message.id}: {e}")
        else:
            try:
                user_id_mention = f"<@{message.author.id}>"
                sent_message = await message.channel.send(f"**Link shared by {user_id_mention}:**\n{response}", view=view)
                view.message = sent_message
                logger.info(f"Sent modified message as bot (per user preference) for message {message.id}")
            except Exception as e:
                logger.error(f"Failed to send message as bot for message {message.id}: {e}")

# Run the bot
client.run(TOKEN)