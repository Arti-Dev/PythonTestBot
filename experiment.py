import asyncio
import datetime
import os.path

import discord
import yaml
from discord import app_commands
from discord.ext import tasks

from utils import save_default_config, update_experiment_stats, \
    fetch_experiment_stats

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
        self.target_guild = None
        self.member_role = None
        self.pass_role = None
        self.fail_role = None
        self.challenge_channel: discord.TextChannel = None
        self.log_channel: discord.TextChannel = None
        self.stats_channel: discord.TextChannel = None
        self.stats_message: discord.Message = None

        # intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True

        super().__init__(intents=intents)

        # sets up new member dictionary
        # this is strictly reserved for users who have made NO attempts yet
        # member ID (string) to task
        self.new_members = dict()

    async def setup_hook(self) -> None:

        # load config file
        configfile = open('config.yml', 'r')
        config = yaml.safe_load(configfile)

        self.target_message_id = config['message-id']
        self.target_guild = await self.fetch_guild(config['guild-id'])
        self.member_role = self.target_guild.get_role(config['member-role-id'])
        self.pass_role = self.target_guild.get_role(config['pass-role-id'])
        self.fail_role = self.target_guild.get_role(config['fail-role-id'])
        self.challenge_channel = await self.target_guild.fetch_channel(config['challenge-channel-id'])
        self.log_channel = await self.target_guild.fetch_channel(config['log-channel-id'])
        self.stats_channel = await self.target_guild.fetch_channel(config['stats-channel-id'])
        self.stats_message = await self.stats_channel.fetch_message(config['stats-message-id'])
        configfile.close()

        self.update_experiment_embed.start()

    async def on_ready(self):
        await tree.sync()
        print(f'Logged in as {self.user}')
        await self.loop.create_task(list_servers(self))

    async def on_member_join(self, member: discord.Member):
        # only track users in the target server
        if member.guild.id == self.target_guild.id:
            await self.log_channel.send(f"{member.mention} with id {member.id} joined!")
            task = self.loop.create_task(delay(
                remove_member_from_new_members(self, member),
                60 * 15))

            self.new_members[member.id] = task

    async def on_member_remove(self, member: discord.Member):
        if member.id in self.new_members:
            await self.log_channel.send(f"{member.mention} with id {member.id} left before they could pass the challenge!")
            self.new_members[member.id].cancel()
            del self.new_members[member.id]

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.message_id == self.target_message_id and payload.event_type == 'REACTION_ADD':
            emoji = payload.emoji
            member = payload.member

            # todo this is hotfix code
            code = None
            try:
                code = ord(emoji.name)
            except TypeError:
                code = 1

            if (emoji.is_unicode_emoji() and code == 127881) or (emoji.name == 'tada'):
                if member.id in self.new_members:
                    await self.pass_new(member, emoji)
                else:
                    await self.pass_regular(member, emoji)
            else:
                if member.id in self.new_members:
                    await self.fail_new(member, emoji)
                else:
                    await self.fail_regular(member, emoji)

    async def pass_new(self, member, emoji):
        # there is no need for this task anymore
        self.new_members[member.id].cancel()
        del self.new_members[member.id]

        # if they already have the stupid role, do not count this towards stats
        if self.fail_role in member.roles:
            await self.pass_regular(member, emoji)
            return

        await member.add_roles(self.pass_role, self.member_role,
                               reason="Passed the entry challenge as a new member")
        await member.send("**Welcome to the Pit Community Discord Server!**\n"
                          "Congratulations on passing the #read-me challenge first try!\n"
                          "You have been given a special role as a bonus!\n"
                          "**You may now access the rest of the server!**")
        update_experiment_stats(True)
        await self.log_channel.send(f"{member.mention} PASSED the challenge as a NEW user.\n"
                                    f"They used the {emoji.name} emoji.")

    async def pass_regular(self, member, emoji):
        # grant member role even though carl-bot will likely do it
        await member.add_roles(self.member_role, reason="Passed the entry challenge")
        await self.log_channel.send(f"{member.mention} PASSED the challenge as a REGULAR user.\n"
                                    f"They used the {emoji.name} emoji.")

    async def fail_new(self, member, emoji):
        # remove from dictionary, but do not cancel the task
        del self.new_members[member.id]

        # if they already have the stupid role, do not count this towards stats
        if self.fail_role in member.roles:
            await self.fail_regular(member, emoji)
            return

        await member.add_roles(self.fail_role, reason="Failed the entry challenge")
        message = await self.challenge_channel.send(f"{member.mention}, "
                                                    f"It looks like you did something wrong. **Pay "
                                                    f"attention**, then try again.")
        await message.delete(delay=10)
        update_experiment_stats(False)
        await self.log_channel.send(f"{member.mention} failed the challenge as a NEW user.\n"
                                    f"They used the {emoji.name} emoji.")

    async def fail_regular(self, member, emoji):
        message = await self.challenge_channel.send(
            f"{member.mention}, It looks like you did something wrong. **Pay "f"attention**, then try again.")
        await message.delete(delay=10)
        await self.log_channel.send(f"{member.mention} failed the challenge as a REGULAR user.\n"
                                    f"They used the {emoji.name} emoji.")

    @tasks.loop(seconds=1800)
    async def update_experiment_embed(self):
        stats = fetch_experiment_stats()

        current_time = datetime.datetime.now()
        embed = discord.Embed(title="#read-me challenge stats", color=10246582, timestamp=current_time)
        embed.add_field(name="Passed", value=stats['passed'])
        embed.add_field(name="Failed", value=stats['failed'])
        embed.add_field(name='No response', value=stats['timedout'])

        await self.stats_message.edit(content="", embed=embed)


async def delay(coro, seconds):
    await asyncio.sleep(seconds)
    await coro


async def remove_member_from_new_members(client, member: discord.Member):
    if not client.enable_experiment: return
    # If this method is called, it means that the challenge was not solved.

    # Make sure the user doesn't have preexisting roles
    if client.member_role in member.roles:
        if member.id in client.new_members:
            await client.log_channel.send(
                f"{member.mention} ran out of time, but they seem to already have the Member role.")
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
        update_experiment_stats(None, timed_out=True)
        await client.log_channel.send(f"{member.mention} did not attempt the challenge within 15 minutes.")
    else:
        # The member made an attempt but did not pass within the time limit
        await member.send("**Welcome to the Pit Community Discord Server!**\n"
                          "I noticed that you attempted the #read-me challenge, but you never finished.\n"
                          "**You may now access the rest of the server!**\n"
                          "You have been given a special role as a bonus!")
        await client.log_channel.send(f"{member.mention} attempted the challenge, but did not pass within 15 minutes.")

async def list_servers(client):
    await client.wait_until_ready()
    print("Current servers:")
    for server in client.guilds:
        print(server.name)


client = Client()
tree = app_commands.CommandTree(client)

client.run(token)
