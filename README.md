<h1 align="center">
vxtwitter Link Bot
</h1>

<p align="center">
<img src="https://github.com/stef1949/Vxtwitter-Link-Embedder/blob/main/38CD6CE0-EFF2-48DE-9487-75D414D104E8.png?raw=true " width="200">
<p/>

This Discord bot looks for Twitter/X links in messages and automatically replaces them with `vxtwitter.com` links. It also provides a delete button so that the original user can remove the bot's transformed message.

## Features

- **URL Replacement:** Finds URLs containing `twitter.com` or `x.com` and replaces them with `vxtwitter.com`.
- **Delete Button:** Adds an interactive button for the original message sender to delete the bot's response.
- **Slash Commands:**  
  - `/status` - Check if the bot is running.
  - `/help` - Show help information about the bot.

## Prerequisites

- Python 3.8+
- A Discord bot token

## Setup

1. **Clone the repository**

2. **Install dependencies:**  
   Run the following command to install required packages from [requirements.txt](requirements.txt):

   ```sh
   pip install -r requirements.txt
   ```

3. **Set up your environment variables:**  
   Make sure to set your Discord bot token in your environment variables.

   ```python
   # TOKEN = os.getenv("DISCORD_TOKEN")
   ```
4. **Run the bot:**
   Launch the bot by running:
   ```sh
   python embedbot.py
   ```
## Logging
The bot logs messages with timestamps, logger names, and levels. Check your console/output for detailed logging information.

## Contributing
Feel free to fork this repository and open issues or pull requests with improvements.

## License
This project is provided as-is under the terms in the LICENSE file.