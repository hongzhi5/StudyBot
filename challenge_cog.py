import datetime
import uuid
from abc import ABC
from typing import List

import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ext.commands import hybrid_command



async def send_message_to_challenge_channel(channel, duration, members):
    # Create an embed message
    embed = discord.Embed(
        title="📚🚀 Study Challenge Started! 🚀📚",
        description="🎯 The study challenge will end in {} minutes. Good luck! 🍀".format(duration),
        color=0x3498db
    )
    embed.add_field(name="📖 Channel 📖", value=channel.mention)
    embed.add_field(name="⏱️ Duration ⏱️", value="{} minutes".format(duration))
    embed.add_field(name="👥 Participants 👥", value=", ".join(member.mention for member in members))
    embed.add_field(name="📝 Study Tips 📝",
                    value="1️⃣ Set clear goals for this study session.\n2️⃣ Avoid distractions - put your phone "
                          "away!\n3️⃣ Take short breaks if needed.\n4️⃣ Stay hydrated and have a healthy snack if "
                          "you're hungry.\n5️⃣ Remember, quality over quantity. Focus is key! 🗝️",
                    inline=False)
    embed.set_footer(text="🔥 Let's get this study party started! 🔥")

    # Send the embed message in the channel
    await channel.send(embed=embed)


async def send_message_to_original_channel(ctx, channel, duration, members):
    # Create an embed message for the channel
    embed = discord.Embed(
        title="📚🚀 Study Challenge Started! 🚀📚",
        description=f"🎯 The study challenge will end in {duration} minutes. Good luck! 🍀",
        color=0x3498db
    )
    embed.add_field(name="📖 Channel 📖", value=channel.mention)
    embed.add_field(name="⏱️ Duration ⏱️", value=f"{duration} minutes")
    embed.add_field(name="👥 Participants 👥", value=", ".join(member.mention for member in members))
    embed.set_footer(text="🔥 Let's get this study party started! 🔥")

    # Send the embed message in the channel
    message = await ctx.send(embed=embed)
    return message


async def update_challenge_complete(challenge, message):
    # Create a new embed message
    embed = discord.Embed(
        title="🎉🎉🎉 Study Challenge Completed! 🎉🎉🎉",
        description="👏 Congratulations on completing the study challenge! You should be proud of your "
                    "hard work. Remember, every minute you spend studying brings you one step closer to "
                    "your goals. Keep up the great work! 🌟",
        color=0x2ecc71
    )
    # Mention the participants in the embed
    participants = " ".join(f"<@{user_id}>" for user_id in challenge["participants"])
    embed.add_field(name="🏆 Participants 🏆", value=participants or "No participants")
    embed.set_footer(text="🔥 Keep the fire of learning burning! 🔥")
    # Edit the original message with the new embed
    await message.edit(embed=embed)


class MemberList:
    def __init__(self):
        self.member_list = []

    def add_member(self, member_id: str):
        self.member_list.append(member_id)


class MemberListTransformer(app_commands.Transformer, ABC):
    async def transform(self, interaction: discord.Interaction, members: str) -> MemberList:
        ml = MemberList()
        for m in members.split(" "):
            ml.member_list.append(m)
        return ml


class ChallengeCog(commands.Cog, name="Challenge Commands"):
    def __init__(self, bot, challenge_collection, study_times_collection):
        self.bot = bot
        self.challenge_collection = challenge_collection
        self.study_times_collection = study_times_collection
        self.check_challenges.start()
        self.converter = commands.MemberConverter()

    @hybrid_command(aliases=["sc"],
                    description="Initiates a time-limited study challenge in a private channel")
    @app_commands.describe(duration="challenge duration in minutes", members="who you want to challenge")
    async def study_challenge(
            self,
            ctx,
            duration: int,
            members: app_commands.Transform[MemberList, MemberListTransformer]):

        discord_member_list = []
        for member_id in members.member_list:
            member = await self.converter.convert(ctx, member_id)
            discord_member_list.append(member)
            print(f"member: {member} type:{type(member)}")
            if self.challenge_collection.find_one({"participants": member.id}):
                await ctx.send(f"{member.mention} is already in a study challenge.")
                return

        # Create a new text channel
        channel_name = "study-challenge-" + str(uuid.uuid4())
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        for member in discord_member_list:
            overwrites[member] = discord.PermissionOverwrite(read_messages=True)
        channel = await ctx.guild.create_text_channel(channel_name, overwrites=overwrites)

        # Send an invitation to the channel for each member
        invite = await channel.create_invite()
        for member in discord_member_list:
            if member.bot:
                continue
            await member.send(f"You've been invited to a study challenge! Join here: {invite.url}")
            await self.auto_check_in_participants(ctx, member)

        message = await send_message_to_original_channel(ctx, channel, duration, discord_member_list)
        await send_message_to_challenge_channel(channel, duration, discord_member_list)

        await self.update_challenge_in_db(channel, ctx, duration, discord_member_list, message)

    async def auto_check_in_participants(self, ctx, member):
        new_ctx = await self.bot.get_context(ctx.message)
        new_ctx.message.author = member
        new_ctx.study_times_collection = self.study_times_collection
        await self.bot.get_command("check_in").callback(self, new_ctx)

    async def update_challenge_in_db(self, channel, ctx, duration, members, message):
        # Save the challenge details to MongoDB
        end_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=duration)
        challenge = {
            "channel_id": channel.id,
            "message_id": message.id,
            "original_channel_id": ctx.channel.id,
            "end_time": end_time,
            "participants": [member.id for member in members],  # Save the user IDs of the participants
        }
        self.challenge_collection.insert_one(challenge)

    @tasks.loop(minutes=1)
    async def check_challenges(self, ):
        # Check MongoDB for any channels that should be deleted
        now = datetime.datetime.utcnow()
        expired_challenges = self.challenge_collection.find({"end_time": {"$lt": now}})
        for challenge in expired_challenges:
            channel = self.bot.get_channel(challenge["channel_id"])
            if "original_channel_id" not in challenge:
                await channel.delete(reason="Study challenge has ended.")
                self.challenge_collection.delete_one({"_id": challenge["_id"]})
                continue
            original_channel = self.bot.get_channel(challenge["original_channel_id"])
            if channel and original_channel:
                try:
                    # Fetch the original message from the original channel
                    message = await original_channel.fetch_message(challenge["message_id"])
                except discord.errors.NotFound:
                    # Message doesn't exist, continue with the next challenge
                    continue

                await update_challenge_complete(challenge, message)

                # Delete the study challenge channel
                await channel.delete(reason="Study challenge has ended.")
                self.challenge_collection.delete_one({"_id": challenge["_id"]})

                await self.auto_check_out_participants(challenge, channel, message, original_channel)

    async def auto_check_out_participants(self, challenge, channel, message, original_channel):
        if channel and original_channel:
            # Automatically check out the participants
            for user_id in challenge["participants"]:
                member = self.bot.get_guild(channel.guild.id).get_member(user_id)
                if member and not member.bot:
                    new_ctx = await self.bot.get_context(message)
                    new_ctx.message.author = member
                    new_ctx.study_times_collection = self.study_times_collection
                    await self.bot.get_command("check_out").callback(self, new_ctx)
