<h1 align="center"> vxtwitter Link Bot </h1> <p align="center"> <img src="https://github.com/stef1949/Vxtwitter-Link-Embedder/blob/main/38CD6CE0-EFF2-48DE-9487-75D414D104E8.png?raw=true " width="200"> <p/>

This Discord bot looks for Twitter/X links in messages and automatically replaces them with `vxtwitter.com` links. It includes user identity emulation, interactive buttons, and comprehensive admin controls.

## Features

### Core Functionality
* **URL Replacement:** Finds URLs containing `twitter.com` or `x.com` and replaces them with `vxtwitter.com`
* **User Emulation:** Can post links either as the original user (with their name and avatar) or as the bot with attribution
* **Interactive Buttons:**
   * **Delete Button:** Lets the original message sender remove the bot's response
   * **Toggle Emulation Button:** Allows users to quickly switch their emulation preference
* **Restart-Proof Design:** Buttons continue to work even after the bot restarts

### Security & Administration
* **Rate Limiting:** Per-user and global rate limits to prevent abuse
* **Admin Controls:** Ban users, blacklist servers, and add administrators
* **Server Settings:** Server-specific configuration options
* **Team Support:** Fully compatible with team-owned bots, with all team members recognized as admins
* **Permission Hierarchy:** Server owners, bot admins, and team members all have appropriate permissions
* **Comprehensive Logging:** Detailed logging for troubleshooting and security auditing
* **Webhook Permission Detection:** Automatically detects if emulation is possible in each channel

### Slash Commands
* **User Commands:**
   * `/status` - View detailed bot status information
   * `/help` - Show help information about available commands
   * `/emulate` - Set whether the bot should post as you or as itself
* **Admin Commands:**
   * `/ban` - Ban a user from using the bot
   * `/unban` - Unban a previously banned user
   * `/addadmin` - Add a bot administrator
   * `/listadmins` - List all bot administrators
   * `/server_blacklist` - Add or remove a server from the blacklist
* **Server Admin Commands:**
   * `/server_settings` - Configure bot settings for the server
   * `/channel_whitelist` - Add or remove channels to the whitelist

## Prerequisites
* Python 3.8+
* Discord.py 2.0+
* A Discord bot token

## Setup
1. **Clone the repository**
2. **Install dependencies:** Run the following command to install required packages from requirements.txt:

```sh
pip install -r requirements.txt
```

3. **Set up your environment variables:** Make sure to set your Discord bot token in your environment variables.

```
export DISCORD_TOKEN=your_token_here
```

Or create a `.env` file with:

```
DISCORD_TOKEN=your_token_here
```

4. **Run the bot:** Launch the bot by running:

```sh
python embedbot.py
```

## User Guide

### User Emulation
The bot can post Twitter/X links in two ways:
* **Emulation Enabled:** Posts appear to come from you (with your name and avatar)
* **Emulation Disabled:** Posts come from the bot with a mention of who shared the link

You can toggle your preference with:
* The `/emulate` command
* The "Toggle Emulation" button on any of your posts

**Note:** Emulation requires the bot to have webhook permissions in the channel. The bot will automatically fall back to non-emulation mode if these permissions are missing.

### Managing Posts
Each converted link includes control buttons:
* **Delete:** Removes the post (only works for your own posts or if you're an admin)
* **Toggle Emulation:** Switches your emulation preference for future posts

### Server Administration
Server administrators can:
* Enable/disable the bot for the entire server
* Restrict the bot to specific channels
* Whitelist or blacklist channels

### Bot Administration
Bot administrators (team members and added admins) can:
* Ban/unban users
* Add new administrators
* Blacklist problematic servers
* View all current administrators with `/listadmins`
* Override controls on any message

### Team Ownership Support
When the bot is owned by a Discord team:
* All team members are automatically recognized as bot administrators
* Team members have full access to all admin commands
* Team ownership status is visible in the `/status` command

### Logging
The bot logs to both the console and a `bot.log` file, including:
* Message conversions
* Button interactions
* Security events
* Error information
* Team and permissions info

## Troubleshooting
If button controls aren't working:
* Check that you're the original poster of the message
* Confirm your Discord client is up-to-date
* Server admins and bot owners can always use the controls
* You can always use direct slash commands as an alternative

## Contributing
Feel free to fork this repository and open issues or pull requests with improvements.

## License
This project is provided as-is under the terms in the LICENSE file.
