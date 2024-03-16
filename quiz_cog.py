import discord
import pytz
from discord.ext import commands, tasks
import datetime

from discord.ext.commands import hybrid_command

from logger_config import setup_logger

TIMEZONE = pytz.timezone('America/New_York')


class QuizCog(commands.Cog, name="Quiz Commands"):
    LOG = setup_logger("QuizCog")

    def __init__(self, bot, quiz_collection, active_quizzes_collection, user_answers_collection):
        self.bot = bot
        self.quiz_collection = quiz_collection
        self.active_quizzes_collection = active_quizzes_collection
        self.user_answers_collection = user_answers_collection
        self.check_quizzes.start()

    def cog_unload(self):
        self.check_quizzes.cancel()

    @hybrid_command(aliases=['q'])
    async def quiz(self, ctx):
        """Start a quiz."""
        quiz = self.quiz_collection.aggregate([{'$sample': {'size': 1}}])
        quiz = list(quiz)
        if not quiz:
            await ctx.send("No quiz questions found!")
            return
        quiz = quiz[0]
        embed = discord.Embed(title="📚 Quiz Time!", description=quiz['question'], color=0x3498db)
        for i, option in enumerate(quiz['options']):
            embed.add_field(name=f"Option {i + 1}", value=option, inline=False)
        embed.set_footer(text="React with the number corresponding to your answer. I'll DM you the answer. Quiz is "
                              "only valid for 12 hours. You can use !quiz to generate a new one.")
        message = await ctx.send(embed=embed)
        emojis = ['\u0031\uFE0F\u20E3', '\u0032\uFE0F\u20E3', '\u0033\uFE0F\u20E3', '\u0034\uFE0F\u20E3']
        for emoji in emojis:
            await message.add_reaction(emoji)

        # Store the active quiz in the database
        self.active_quizzes_collection.insert_one({
            'message_id': message.id,
            'quiz': quiz,
            'start_time': datetime.datetime.now(),
            'answered_by': []
        })

    @tasks.loop(minutes=1)  # check every minute
    async def check_quizzes(self):
        """Delete quizzes that have expired."""
        now = datetime.datetime.now()
        self.active_quizzes_collection.delete_many({
            'start_time': {
                '$lt': now - datetime.timedelta(hours=12)
            }
        })

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Check if a reaction is the answer to a quiz."""
        # Ignore reactions from the bot
        if user == self.bot.user:
            return

        # Check if the reaction is for an active quiz
        active_quiz = self.active_quizzes_collection.find_one({'message_id': reaction.message.id})
        if active_quiz and user.id not in active_quiz['answered_by']:
            emojis = ['\u0031\uFE0F\u20E3', '\u0032\uFE0F\u20E3', '\u0033\uFE0F\u20E3', '\u0034\uFE0F\u20E3']
            answer = emojis.index(reaction.emoji)
            quiz = active_quiz['quiz']
            correct = answer == quiz['answer']
            if correct:
                embed = discord.Embed(title="✅ Correct!",
                                      description=f"The question was: {quiz['question']}.\nThe correct answer "
                                                  f"is:\n**{quiz['options'][quiz['answer']]}**.",
                                      color=0x00ff00)
                await user.send(embed=embed)
            else:
                embed = discord.Embed(title="❌ Incorrect.",
                                      description=f"Sorry, the correct answer was\n**{quiz['options'][quiz['answer']]}**.\nThe question was:\n{quiz['question']}.",
                                      color=0xff0000)
                await user.send(embed=embed)

            # Update the active quiz in the database
            self.active_quizzes_collection.update_one(
                {'message_id': reaction.message.id},
                {
                    '$push': {'answered_by': user.id},
                    '$currentDate': {'last_interaction': True}
                }
            )

            # Store the user's answer in the database
            self.user_answers_collection.insert_one({
                'user_id': user.id,
                'quiz_id': quiz['_id'],
                'correct': correct
            })

    @hybrid_command(aliases=['qr'])
    async def quiz_report(self, ctx):
        """Report the correct rate of the user."""
        answers = list(self.user_answers_collection.find({'user_id': ctx.author.id}))
        if not answers:
            await ctx.send("You haven't answered any quizzes yet.")
            return
        correct_answers = sum(1 for answer in answers if answer['correct'])
        correct_rate = correct_answers / len(answers)
        await ctx.send(f"{ctx.message.author.mention} Your correct rate is {correct_rate:.2%}.")

    @tasks.loop(hours=12)
    async def daily_quiz(self, ):
        self.LOG.info("run daily quiz")
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                async for message in channel.history(limit=1):
                    ctx = await self.bot.get_context(message)
                    await self.quiz(ctx)
                    self.LOG.info(f"quiz channel {channel}")
                    break
                else:
                    await channel.send("Remember to study and check in today!")

    @daily_quiz.before_loop
    async def before_daily_reminder(self, ):
        now = datetime.datetime.now(TIMEZONE)
        if now.hour < 8:
            next_reminder = now.replace(hour=8, minute=0, second=0)
        elif now.hour < 20:
            next_reminder = now.replace(hour=20, minute=0, second=0)
        else:
            next_reminder = (now + datetime.timedelta(days=1)).replace(hour=8, minute=0, second=0)
        await discord.utils.sleep_until(next_reminder)