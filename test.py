import os.path
import random

import discord
import feedparser
import requests
import yaml
from discord import app_commands
from discord.ext import tasks

from utils import hypixel_date_to_timestamp, save_new_guid, save_default_config

# check if the config file exists
path = './config.yml'
if not os.path.isfile(path):
    save_default_config()

# load config file
file = open('config.yml', 'r')
config = yaml.safe_load(file)

token = config['token']
message_id = config['message-id']
url = config['url']

file.close()

# check if the last guid file exists
path = './bestguid.txt'
if not os.path.isfile(path):
    raise Exception("No bestguid.txt file found in the same directory!")


class Client(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)

        # load bestguid
        guid_file = open('bestguid.txt', 'r')
        self.best_guid = int(guid_file.readlines()[0])
        guid_file.close()

    async def setup_hook(self) -> None:
        self.fetch_hypixel_task.start()

    async def on_ready(self):
        await tree.sync()
        print(f'Logged in as {client.user}')
        await client.loop.create_task(list_servers())

    async def on_member_join(self):
        pass

    @tasks.loop(seconds=60)
    async def fetch_hypixel_task(self):
        print(f"Fetching from Hypixel RSS!")
        rss = feedparser.parse("https://hypixel.net/the-pit/index.rss")
        entries = rss.entries
        print(f"Current best guid is {self.best_guid}")
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
            post_new_thread(rss, guid_to_entry[target_guid])
            self.best_guid = target_guid
            print(f"New best guid is {self.best_guid}. Writing to disk.")
            if len(guids) > 1:
                print(f"There are {len(guids) - 1} thread(s) in queue. They will be addressed in the next cycle.")
            save_new_guid(self.best_guid)
        else:
            print("No new threads found!")
        print("------------")


def post_new_thread(rss, thread_entry):
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
    r = requests.post(url=url, json=json)
    if r.status_code != 204:
        print(f"There was an error posting the latest thread. guid: {thread_guid}")
    else:
        print(f"Successfully posted: {forum_title}\n{title}\n{link}\n{creator}\n{timestamp}\nguid: {thread_guid}")


async def list_servers():
    await client.wait_until_ready()
    print("Current servers:")
    for server in client.guilds:
        print(server.name)


# intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

client = Client()
tree = app_commands.CommandTree(client)
generalID = 1112913686626054188


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


@tree.command(name='random',
              description="Gives a random number from 1 to 1000")
async def rand(interaction: discord.Interaction):
    my_num = random.randint(1, 1000)
    await interaction.response.send_message(my_num)


client.run(token)
