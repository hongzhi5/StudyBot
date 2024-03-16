import json
import os
from difflib import get_close_matches

import discord
import pytz
from discord.ext import commands
from dotenv import load_dotenv
from pymongo import MongoClient

from challenge_cog import ChallengeCog
from help import CustomHelpCommand
from logger_config import setup_logger
from quiz_cog import QuizCog
from stats_cog import StatsCog
from study_cog import StudyCog

timezone = pytz.timezone('America/New_York')
load_dotenv()  # take environment variables from .env.
GUILDS_ID = discord.Object(id=os.getenv('GUILD_ID'))


class StudyBot(commands.Bot):
    LOG = setup_logger("StudyBot")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cogs_added = False
        self.mongo_client = MongoClient(os.getenv('MONGODB_CONNECTION_STRING'))
        self.LOG.info(f"initialized MONGO CLIENT:{self.mongo_client}")
        self.db = self.mongo_client['study_bot_db']
        self.quiz_collection = self.db['quiz_collection']
        self.study_times_collection = self.db['study_times']
        self.timers_collection = self.db['timers']
        self.active_quizzes_collection = self.db['active_quizzes']
        self.user_answers_collection = self.db['user_answers']
        self.challenge_collection = self.db['challenge']
        self.user_daily_study_time_collection = self.db['user_daily_study_time']
        self.user_levels_collection = self.db['user_levels']

    async def on_ready(self):
        if not self.cogs_added:
            self.LOG.info(f'We have logged in as {self.user}')

            await self.add_cog(StudyCog(bot, self.study_times_collection, self.timers_collection, self.user_daily_study_time_collection, GUILDS_ID))
            await self.add_cog(QuizCog(bot,
                                    self.quiz_collection, self.active_quizzes_collection, self.user_answers_collection))
            await self.add_cog(ChallengeCog(bot, self.challenge_collection, self.study_times_collection))
            await self.add_cog(StatsCog(bot, self.study_times_collection, self.user_daily_study_time_collection, self.user_levels_collection, self.user_answers_collection))
            self.load_quiz()
            self.tree.copy_global_to(guild=GUILDS_ID)
            await self.tree.sync(guild=GUILDS_ID)
            self.cogs_added = True

    def load_quiz(self):
        if self.quiz_collection.count_documents({}) == 0:  # Check if the collection is empty
            with open('quizzes.json', 'r') as f:
                quizzes = json.load(f)
                self.quiz_collection.insert_many(quizzes)

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"{ctx.message.author.mention} {error.param.name} is a required argument that is missing.")
        elif isinstance(error, commands.CommandNotFound):
            # Get the attempted command
            attempted_command = ctx.message.content.split(" ")[0][len(self.command_prefix):]

            # Get a list of actual command names
            command_names = [command.name for command in self.commands]
            for command in self.commands:
                command_names.extend(command.aliases)

            # Find the closest match to the attempted command
            matches = get_close_matches(attempted_command, command_names, n=1, cutoff=0.5)
            if matches:
                await ctx.send(f"{ctx.message.author.mention} Command not found. Did you mean `{self.command_prefix}{matches[0]}`?")
            else:
                await ctx.send(f"{ctx.message.author.mention} Command not found.")
        else:
            # If the error is not a CommandNotFound error, call the default error handler
            await super().on_command_error(ctx, error)


if __name__ == "__main__":
    bot = StudyBot(command_prefix='!', intents=discord.Intents.all())
    bot.help_command = CustomHelpCommand()
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))
