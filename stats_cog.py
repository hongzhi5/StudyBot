import datetime
import discord
import math
import pytz
from discord.ext import commands, tasks
from discord.ext.commands import hybrid_command

from Util import Utils
from logger_config import setup_logger

TIMEZONE = pytz.timezone('America/New_York')
COLUMN_WIDTH = 15
LEADERBOARD_COLUMN_NAME = "```\nUser           | Study Time\n"
LEADERBOARD_COLUMN_SPLITTER = f"{'-' * COLUMN_WIDTH}|-----------\n"
EMBED_COLOR = 0X78C2C4


class StatsCog(commands.Cog, name="Stats Commands"):
    LOG = setup_logger("StatsCog")

    def __init__(self, bot, study_times_collection, user_daily_study_time_collection, user_levels_collection, user_answers_collection):
        self.bot = bot
        self.study_times_collection = study_times_collection
        self.user_daily_study_time_collection = user_daily_study_time_collection
        self.user_levels_collection = user_levels_collection
        self.user_answers_collection = user_answers_collection
        self.progress_reports.start()
    
    def calculate_weekly_study_time(self, user_id, start_of_week, end_of_week):
        weekly_data = self.user_daily_study_time_collection.find({
            'user_id': user_id,
            'date': {'$gte': start_of_week, '$lte': end_of_week}
        })

        weekly_study_time = sum(day.get('study_time_this_day', 0) for day in weekly_data)

        return weekly_study_time
    

    @hybrid_command()
    async def report(self, ctx):
        user_id = str(ctx.message.author.id)
        user_data = self.study_times_collection.find_one({'user_id': user_id})

        if not user_data:
            await ctx.send(f"{ctx.message.author.mention}, you don't have any recorded study data yet.")
            return
        total_study_time = user_data.get("total_study_time", 0)
        daily_study_time = user_data.get("daily_study_time", 0)
        answers = list(self.user_answers_collection.find({'user_id': ctx.author.id}))
        if not answers:
            correct_answers = 0
        else:
            correct_answers = sum(1 for answer in answers if answer['correct'])
        
        xp = (total_study_time / 60) * 0.5 + correct_answers * 50
        def calculate_level(xp):
            level = (xp / 50) ** 0.5
            return math.floor(level)
        level = calculate_level(xp)
        self.user_levels_collection.update_one(
                {'user_id': user_id},
                {'$set': {'xp': xp, 'level': level}},
                upsert=True
            )

        today = datetime.datetime.now()
        start_of_week = (today - datetime.timedelta(days=today.weekday())).strftime('%Y-%m-%d')
        end_of_week = (today - datetime.timedelta(days=today.weekday()) + datetime.timedelta(days=6)).strftime('%Y-%m-%d')

        weekly_study_time = self.calculate_weekly_study_time(user_id, start_of_week, end_of_week)

        human_readable_time_total = Utils.convert_seconds_to_time(total_study_time)
        human_readable_time_daily = Utils.convert_seconds_to_time(daily_study_time)
        human_readable_time_weekly = Utils.convert_seconds_to_time(weekly_study_time)

        message = f'LEVEL: **{level}**  |  XP: **{int(xp)}**\n' \
                  f'DAILY: {human_readable_time_daily}\n' \
                  f'WEEKLY: {human_readable_time_weekly}\n' \
                  f'ALL TIME: {human_readable_time_total}\n'
            

        await ctx.send(message)
    @hybrid_command(aliases=['lb'])
    async def leaderboard(self, ctx):
        """Display a leaderboard showing the total study times within the channel."""
        channel_id = str(ctx.channel.id)
        leaderboard_text = LEADERBOARD_COLUMN_NAME
        leaderboard_text += LEADERBOARD_COLUMN_SPLITTER
        sorted_users = self.study_times_collection.find({'channel_id': channel_id}).sort('total_study_time', -1).limit(
            100)
        for user_data in sorted_users:
            user = await self.bot.fetch_user(int(user_data['user_id']))
            total_study_time = Utils.convert_seconds_to_time(user_data["total_study_time"])
            leaderboard_text += f"{user.name[:COLUMN_WIDTH]:<{COLUMN_WIDTH}}| {total_study_time}\n"
        leaderboard_text += "```"
        embed = discord.Embed(title="Leaderboard for this channel", description=leaderboard_text, color=EMBED_COLOR)
        await ctx.send(embed=embed)

    @hybrid_command(aliases=['olb'])
    async def overall_leaderboard(self, ctx):
        """Display a leaderboard showing the total study times within the server."""
        leaderboard_text = LEADERBOARD_COLUMN_NAME
        leaderboard_text += LEADERBOARD_COLUMN_SPLITTER

        sorted_users = self.study_times_collection.find().sort('total_study_time', -1).limit(100)
        for user_data in sorted_users:
            user = await self.bot.fetch_user(int(user_data['user_id']))
            total_study_time = Utils.convert_seconds_to_time(user_data["total_study_time"])
            leaderboard_text += f"{user.name[:COLUMN_WIDTH]:<{COLUMN_WIDTH}}| {total_study_time}\n"
        leaderboard_text += "```"
        embed = discord.Embed(title="Server Leaderboard", description=leaderboard_text, color=EMBED_COLOR)
        await ctx.send(embed=embed)

    @tasks.loop(hours=24)
    async def progress_reports(self, ):
        for guild in self.bot.guilds:
            for member in guild.members:

                user_id = str(member.id)
                user_data = self.study_times_collection.find_one({'user_id': user_id})
                if user_data and 'total_study_time' in user_data:
                    total_study_time = Utils.convert_seconds_to_time(user_data["total_study_time"])
                    await member.send(f'Your total study time is: {total_study_time}')
                    self.LOG.info(f"Generated report for {member}")

    @progress_reports.before_loop
    async def before_progress_reports(self, ):
        now = datetime.datetime.now(TIMEZONE)
        next_report = now.replace(hour=12, minute=0, second=0)
        if now.hour >= 12:
            next_report += datetime.timedelta(days=1)
        await discord.utils.sleep_until(next_report)
