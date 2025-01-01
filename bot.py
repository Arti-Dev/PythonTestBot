import asyncio
import os.path
import random

import discord
import feedparser
import requests
import yaml
from discord import app_commands
from discord.ext import tasks

from utils import hypixel_date_to_timestamp, save_new_guid, save_default_config

# check if the last guid file exists
path = './bestguid.txt'
if not os.path.isfile(path):
    raise Exception("No bestguid.txt file found in the same directory!")

# check if the config file exists
path = './config.yml'
if not os.path.isfile(path):
    save_default_config()

# load token
file = open('config.yml', 'r')
token = yaml.safe_load(file)['token']
file.close()


class Client(discord.Client):
    def __init__(self):
        self.webhook = None
        self.target_guild = None
        self.log_channel: discord.TextChannel = None

        # intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True

        super().__init__(intents=intents)

        # load best_guid
        guid_file = open('bestguid.txt', 'r')
        self.best_guid = int(guid_file.readlines()[0])
        guid_file.close()

    async def setup_hook(self) -> None:

        # load config file
        configfile = open('config.yml', 'r')
        config = yaml.safe_load(configfile)

        self.webhook = config['url']
        self.target_guild = await self.fetch_guild(config['guild-id'])
        self.log_channel = await self.target_guild.fetch_channel(config['log-channel-id'])
        configfile.close()

        self.fetch_hypixel_task.start()
        await self.send_log_message("Starting up!")

    async def on_ready(self):
        await tree.sync()
        print(f'Logged in as {self.user}')
        await self.loop.create_task(list_servers(self))

    @tasks.loop(seconds=60)
    async def fetch_hypixel_task(self):
        # print(f"Fetching from Hypixel RSS!")
        rss = feedparser.parse("https://hypixel.net/the-pit/index.rss")
        entries = rss.entries
        # print(f"Current best guid is {self.best_guid}")
        guid_to_entry = dict()
        for entry in entries:
            guid = int(entry.guid)
            if guid > self.best_guid:
                guid_to_entry[int(entry.guid)] = entry

        guids = list(guid_to_entry.keys())
        guids.sort()

        # post only the first thread that is newer than the previous posted thread
        if len(guids) > 0:
            target_guid = guids[0]
            await post_new_thread(self, rss, guid_to_entry[target_guid])
            self.best_guid = target_guid
            await self.send_log_message(f"New best guid is {self.best_guid}. Writing to disk.")
            if len(guids) > 1:
                await self.send_log_message(f"There are {len(guids) - 1} thread(s) in queue. They will be addressed "
                                            f"in the next cycle.")
            save_new_guid(self.best_guid)
        else:
            pass
            # print("No new threads found!")
        # print("------------")

    async def send_log_message(self, message: str):
        await self.log_channel.send(message)


async def delay(coro, seconds):
    await asyncio.sleep(seconds)
    await coro


async def post_new_thread(client, rss, thread_entry):
    forum_title = rss.feed.title
    title = thread_entry.title
    link = thread_entry.link
    creator = thread_entry.author
    timestamp = hypixel_date_to_timestamp(thread_entry.published)
    thread_guid = thread_entry.guid
    json = {
        "content": f"New thread posted <t:{timestamp}:R>",
        "embeds": [
            {"title": forum_title,
             "color": 10246582,
             "description": f'[{title}]({link})',
             "footer": {
                 "text": f'Thread by {creator}'
             }}
        ]}
    r = requests.post(url=client.webhook, json=json)
    if r.status_code != 204:
        await client.send_log_message(f"There was an error posting the latest thread. guid: {thread_guid}")
    else:
        await client.send_log_message(f"Successfully posted: {forum_title}\n{title}\n{link}\n{creator}\n{timestamp}\nguid: {thread_guid}")


async def list_servers(client):
    await client.wait_until_ready()
    print("Current servers:")
    for server in client.guilds:
        print(server.name)


client = Client()
tree = app_commands.CommandTree(client)


@tree.command(name='square',
              description="Squares a number for you", )
async def square(interaction: discord.Interaction, number: float):
    await interaction.response.send_message(str(number) + " squared is " +
                                            str(number ** 2) + ", " + interaction.user.mention)


@tree.command(name='squareroot',
              description="Square-roots a number for you")
async def square(interaction: discord.Interaction, number: float):
    await interaction.response.send_message(
        f"The square root of {number} is {number ** 0.5}, {interaction.user.mention}")


@tree.command(name='say',
              description="Repeats-after-you")
async def say(interaction: discord.Interaction, string: str):
    await interaction.channel.send(string)
    await interaction.response.send_message("Sent!", ephemeral=True, delete_after=5)


@tree.command(name='spamarti',
              description="all of these commands start with s")
async def spamarti(interaction: discord.Interaction, string: str):
    user = client.get_user(306570665694199809)
    await user.send(string)
    await interaction.response.send_message(f"Sent '{string}' to Arti_Creep!")

@tree.command(name='planetpit',
              description="Send the Planet Pit invite in chat\n(for those who don't know how to do research")
async def planetpit(interaction: discord.Interation):
    await interaction.channel.send("here's the invite to Planet Pit, you ungrateful whelp\nhttps://discord.gg/pit")
    await interaction.response.send_message("Sent Planet Pit invite in chat!")


@tree.command(name='random',
              description="Gives a random number from 1 to 1000")
async def rand(interaction: discord.Interaction):
    my_num = random.randint(1, 1000)
    await interaction.response.send_message(my_num)


client.run(token)
