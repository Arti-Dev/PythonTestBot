
# un-cleaned imports
import random
import asyncio
import aiohttp
import json
import discord
from discord import Game
from discord import app_commands
from discord.ext.commands import Bot
import traceback
import sys
from discord.ext import tasks
import threading
import yaml
import os.path


# check if the config file exists
path = './config.yml'
if not os.path.isfile(path):
    file = open('config.yml', 'w')
    yaml.dump({'token': 'your mom',
               'message-id': 1119465976149327892}, file)
    file.close()

# load config file
file = open('config.yml', 'r')
config = yaml.safe_load(file)
token = config['token']
messageid = config['message-id']
file.close()

# intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

# maybe we'll have a task in here?
class Client(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        

client = Client()
tree = app_commands.CommandTree(client)
generalID = 1112913686626054188

@client.event
async def on_ready():
    await tree.sync()
    print(f'Logged in as {client.user}')
    await client.loop.create_task(list_servers())

@tree.command(name='square',
                description="Squares a number for you",)
async def square(interaction: discord.Interaction, number: float):
    await interaction.response.send_message(str(number) + " squared is " +
                    str(number**2) + ", " + interaction.user.mention)

@tree.command(name='squareroot',
              description="Square-roots a number for you")
async def square(interaction: discord.Interaction, number: float):
    await interaction.response.send_message(f"The square root of {number} is {number**0.5}, {interaction.user.mention}")

@tree.command(name='say',
              description="Repeats-after-you")
async def say(interaction: discord.Interaction, string: str):
    await interaction.response.send_message("Sent!", ephemeral=True, delete_after=5)
    await interaction.channel.send(string)

@tree.command(name='spamarti',
              description="all of these commands start with s")
async def spamarti(interaction: discord.Interaction, string: str):
    user = client.get_user(306570665694199809)
    await user.send(string)
    await interaction.response.send_message(f"Sent '{string}' to Arti_Creep!")

@tree.command(name='random',
                description="Gives a random number from 1 to 1000")
async def rand(interaction: discord.Interaction):
    my_num = random.randint(1,1000)
    await interaction.response.send_message(my_num)

async def list_servers():
    await client.wait_until_ready()
    print("Current servers:")
    for server in client.guilds:
        print(server.name)
        
client.run(token)
