# __________                  __             __     ________             .___ 
# \______   \  ____    ____  |  | __  ____ _/  |_  /  _____/   ____    __| _/ 
#  |       _/ /  _ \ _/ ___\ |  |/ /_/ __ \\   __\/   \  ___  /  _ \  / __ |  
#  |    |   \(  <_> )\  \___ |    < \  ___/ |  |  \    \_\  \(  <_> )/ /_/ |  
#  |____|_  / \____/  \___  >|__|_ \ \___  >|__|   \______  / \____/ \____ |  
#         \/              \/      \/     \/               \/              \/  
#
# Paste Search Discord Bot by RocketGod
# https://github.com/RocketGod-git/paste-search-discord-bot

import json
import logging
import discord
import aiohttp
from discord import Embed
from discord import File
import os
import asyncio

logging.basicConfig(level=logging.DEBUG)

def load_config():
    try:
        with open('config.json', 'r') as file:
            return json.load(file)
    except Exception as e:
        logging.error(f"Error loading configuration: {e}")
        return None

class aclient(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=discord.Intents.default())
        self.tree = discord.app_commands.CommandTree(self)
        self.activity = discord.Activity(type=discord.ActivityType.watching, name="/pastes")
        self.discord_message_limit = 2000

    async def send_split_messages(self, interaction, message: str, require_response=True):
        if not message.strip():
            logging.warning("Attempted to send an empty message.")
            return

        lines = message.split("\n")
        chunks = []
        current_chunk = ""

        for line in lines:
            if len(current_chunk) + len(line) + 1 > self.discord_message_limit:
                chunks.append(current_chunk)
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"

        if current_chunk:
            chunks.append(current_chunk)

        if not chunks:
            logging.warning("No chunks generated from the message.")
            return

        if require_response and not interaction.response.is_done():
            await interaction.response.defer(ephemeral=False)

        for chunk in chunks:
            try:
                await interaction.followup.send(content=chunk, ephemeral=False)
            except Exception as e:
                logging.error(f"Failed to send a message chunk to the channel. Error: {e}")

    async def fetch_psbdmp_data(self, search_term):
        """Fetch the psbdmp data for the given search term"""
        URL = f"https://psbdmp.ws/api/v3/search/{search_term}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(URL) as response:
                response_text = await response.text()
                logging.debug(f"API Raw Response: {response_text}")

                if response.status != 200:
                    logging.error(f"API returned non-200 status code: {response.status}. Response text: {response_text}")
                    return None

                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    logging.error(f"Failed to decode API response. Response text: {response_text}")
                    return None

    async def send_via_bot(self, channel, content: str, raw_data: str):
        # Create a temporary file to store the content
        temp_filename = "temp_paste.txt"
        with open(temp_filename, 'w', encoding='utf-8') as f:
            f.write(raw_data)
        
        # Send the message and file attachment
        await channel.send(content=content, file=File(temp_filename, filename="results.txt"))
        
        # Clean up the temporary file
        os.remove(temp_filename)

    async def handle_errors(self, interaction, error_message=None):
        user_friendly_message = "An error occurred while processing your request. Please try again later."
        logging.error(f"Error: {error_message if error_message else 'Unknown error'}")
        if error_message:
            user_friendly_message += f"\n\nDetails: {error_message}"

        if not interaction.response.is_done():
            await interaction.response.send_message(user_friendly_message, ephemeral=True)
        else:
            await interaction.followup.send(user_friendly_message, ephemeral=True)

def run_discord_bot(token):
    client = aclient()

    @client.event
    async def on_ready():
        await client.tree.sync()
        logging.info(f'{client.user} is online.')

    @client.tree.command(name="pastes", description="Search for a term on Pastebin.com")
    async def pastes(interaction: discord.Interaction, query: str):
        await interaction.response.defer(ephemeral=False)
        
        logging.info(f"User {interaction.user} from {interaction.guild if interaction.guild else 'DM'} executed '/pastes' with query '{query}'.") 

        try:
            data = await client.fetch_psbdmp_data(query)

            logging.debug(f"API Response: {data}")

            message = ""
            full_message = ""

            for idx, entry in enumerate(data):
                text_sample = entry['text'].split("\n", 3)
                initial_text = "\n".join(text_sample[:3]) if len(text_sample) > 3 else "\n".join(text_sample)

                formatted_data = (
                    f"id     : {entry['id']}\n"
                    f"tags   : {entry.get('tags', 'none')}\n"
                    f"length : {entry['length']}\n"
                    f"time   : {entry['time']}\n"
                    f"text   :\n\n{initial_text}\n\n"
                    f"link   : https://pastebin.com/{entry['id']}\n\n"
                )
                
                full_message += formatted_data  # Add every entry to full_message

                # Only add the first 20 entries to the 'message' that will be directly shown
                if idx < 20:
                    message += formatted_data

            if not message:
                message = "No data found for the given query."

            await client.send_split_messages(interaction, f"Here are the top 20 results for {query}:")
            await client.send_split_messages(interaction, message)

            # Now send the full_message as a .txt file
            if full_message:
                await client.send_via_bot(interaction.channel, "Here's the full formatted response:", full_message)

        except Exception as e:
            await client.handle_errors(interaction, str(e))

    client.run(token) 
        
if __name__ == "__main__":
    config = load_config()
    if config:
        run_discord_bot(config.get("discord_bot_token"))
