import asyncio
import os.path
import random

import discord
import feedparser
import requests
import yaml
from discord import app_commands, PartialEmoji
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

        self.target_message_id = None
        self.webhook = None
        self.target_guild = None
        self.member_role = None
        self.pass_role = None
        self.fail_role = None
        self.challenge_channel: discord.TextChannel = None

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

        # sets up new member dictionary
        # this is strictly reserved for users who have made NO attempts yet
        # member ID (string) to task
        self.new_members = dict()

    async def setup_hook(self) -> None:
        self.fetch_hypixel_task.start()

        # load config file
        configfile = open('config.yml', 'r')
        config = yaml.safe_load(configfile)

        self.target_message_id = config['message-id']
        self.webhook = config['url']
        self.target_guild = await self.fetch_guild(config['guild-id'])
        self.member_role = self.target_guild.get_role(config['member-role-id'])
        self.pass_role = self.target_guild.get_role(config['pass-role-id'])
        self.fail_role = self.target_guild.get_role(config['fail-role-id'])
        self.challenge_channel = await self.target_guild.fetch_channel(config['challenge-channel-id'])
        configfile.close()

    async def on_ready(self):
        await tree.sync()
        print(f'Logged in as {self.user}')
        await self.loop.create_task(list_servers(self))

    async def on_member_join(self, member: discord.Member):
        # only track users in the target server
        if member.guild.id == self.target_guild.id:
            print(f"{member.name} with id {member.id} joined!")
            task = self.loop.create_task(delay(
                remove_member_from_new_members(self, member),
                60))

            self.new_members[member.id] = task

    async def on_member_remove(self, member: discord.Member):
        if member.id in self.new_members:
            self.new_members[member.id].cancel()
            del self.new_members[member.id]

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.message_id == self.target_message_id and payload.event_type == 'REACTION_ADD':
            emoji = payload.emoji
            member = payload.member

            if emoji.is_unicode_emoji() and ord(emoji.name) == 127881:
                if member.id in self.new_members:
                    # there is no need for this task anymore
                    self.new_members[member.id].cancel()

                    del self.new_members[member.id]
                    await member.add_roles(self.pass_role, self.member_role,
                                           reason="Passed the entry challenge as a new member")
                    await member.send("**Welcome to the Pit Community Discord Server!**\n"
                                      "Congratulations on passing the #read-me challenge first try!\n"
                                      "You have been given a special role as a bonus!\n"
                                      "**You may now access the rest of the server!**")
                    print(f"{member.name} PASSED the challenge as a NEW user.")
                else:
                    # grant member role even though carl-bot will likely do it
                    print(f"{member.name} PASSED the challenge as a REGULAR user.")
                    await member.add_roles(self.member_role, reason="Passed the entry challenge")
            else:
                if member.id in self.new_members:
                    # remove from dictionary, but do not cancel the task
                    del self.new_members[member.id]
                    await member.add_roles(self.fail_role, reason="Failed the entry challenge")
                    message = await self.challenge_channel.send(f"{member.mention}, "
                                                                f"It looks like you did something wrong. **Pay "
                                                                f"attention**, then try again.")
                    await message.delete(delay=10)
                    print(f"{member.name} failed the challenge as a NEW user.\n"
                          f"They used the {emoji.name} emoji.")
                else:
                    message = await self.challenge_channel.send(f"{member.mention}, "
                                                                f"It looks like you did something wrong. **Pay "
                                                                f"attention**, then try again.")
                    await message.delete(delay=10)
                    print(f"{member.name} failed the challenge as a REGULAR user.\n"
                          f"They used the {emoji.name} emoji.")

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
            post_new_thread(self, rss, guid_to_entry[target_guid])
            self.best_guid = target_guid
            print(f"New best guid is {self.best_guid}. Writing to disk.")
            if len(guids) > 1:
                print(f"There are {len(guids) - 1} thread(s) in queue. They will be addressed in the next cycle.")
            save_new_guid(self.best_guid)
        else:
            print("No new threads found!")
        print("------------")


async def delay(coro, seconds):
    await asyncio.sleep(seconds)
    await coro


async def remove_member_from_new_members(client, member: discord.Member):
    # If this method is called, it means that the challenge was not solved.

    # Make sure the user doesn't have preexisting roles
    if client.member_role in member.roles:
        print(f"{member.name} had a timer ticking, but they already have the Member role.")
        if member.id in client.new_members:
            del client.new_members[member.id]
        return

    # Grant member the member role regardless of what happens
    await member.add_roles(client.member_role)

    # If the member is still in client.new_members, no attempt was made.
    if member.id in client.new_members:
        del client.new_members[member.id]
        await member.add_roles(client.fail_role)
        await member.send("**Welcome to the Pit Community Discord Server!**\n"
                          "You did not make an attempt to complete the #read-me challenge within 15 minutes.\n"
                          "You have been given a special role as a bonus!\n"
                          "**You may now access the rest of the server!**")
    else:
        # The member made an attempt but did not pass within the time limit
        await member.send("**Welcome to the Pit Community Discord Server!**\n"
                          "I noticed that you attempted the #read-me challenge, but you never finished.\n"
                          "**You may now access the rest of the server!**\n"
                          "You have been given a special role as a bonus!")



def post_new_thread(client, rss, thread_entry):
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
        print(f"There was an error posting the latest thread. guid: {thread_guid}")
    else:
        print(f"Successfully posted: {forum_title}\n{title}\n{link}\n{creator}\n{timestamp}\nguid: {thread_guid}")


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


@tree.command(name='random',
              description="Gives a random number from 1 to 1000")
async def rand(interaction: discord.Interaction):
    my_num = random.randint(1, 1000)
    await interaction.response.send_message(my_num)


client.run(token)
