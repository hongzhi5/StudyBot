import datetime
import pytz
import discord
from discord.app_commands import describe
from discord.ext import commands, tasks
from discord.ext.commands import hybrid_command, is_owner
TIMEZONE = pytz.timezone('America/New_York')


class StudyCog(commands.Cog, name="Study Commands"):
    def __init__(self, bot, study_times_collection, timers_collection, user_daily_study_time_collection, guild_id):
        self.bot = bot
        self.study_times_collection = study_times_collection
        self.timers_collection = timers_collection
        self.check_timers.start()
        self.guild_id = guild_id
        self.reset_daily_study_time.start()
        self.user_daily_study_time_collection = user_daily_study_time_collection
        self.update_daily_study_time.start()

    @hybrid_command()
    @is_owner()
    async def sync(self, ctx):
        synced = await self.bot.tree.sync(guild=self.guild_id)
        await ctx.send(f"synced {synced}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = member.guild.system_channel
        if channel is not None:
            await channel.send(f'Welcome {member.mention}.')

    @hybrid_command(aliases=['ci'])
    async def check_in(self, ctx):
        """Indicate that you're starting your study session."""
        user_id = str(ctx.message.author.id)
        channel_id = str(ctx.channel.id)
        user_data = self.study_times_collection.find_one({'user_id': user_id, 'channel_id': channel_id})

        # Check if the user has already checked in
        if user_data and 'check_in_time' in user_data:
            await ctx.send(f'{ctx.message.author.mention} already checked in!')
            return

        check_in_time = datetime.datetime.now()
        self.study_times_collection.update_one(
            {'user_id': user_id, 'channel_id': channel_id},
            {'$set': {'check_in_time': check_in_time}},
            upsert=True
        )
        await ctx.send(f'{ctx.message.author.mention} checked in!')

    @hybrid_command(aliases=['co'])
    async def check_out(self, ctx):
        """Indicate that you're done studying."""
        user_id = str(ctx.message.author.id)
        channel_id = str(ctx.channel.id)
        user_data = self.study_times_collection.find_one({'user_id': user_id, 'channel_id': channel_id})
        
        if user_data and 'check_in_time' in user_data:
            check_out_time = datetime.datetime.now()
            study_time = (check_out_time - user_data['check_in_time']).total_seconds()
            
            self.study_times_collection.update_one(
                {'user_id': user_id, 'channel_id': channel_id},
                {'$inc': {'total_study_time': study_time, 'daily_study_time': study_time}, '$unset': {'check_in_time': ""}},
                upsert=True
            )

            current_date = datetime.datetime.now().strftime('%Y-%m-%d')
            self.user_daily_study_time_collection.update_one(
                {'user_id': user_id, 'channel_id': channel_id, 'date': current_date},
                {'$inc': {'study_time_this_day': study_time}},
                upsert=True
            )

            if 'goal' in user_data:
                goal_progress = user_data.get('daily_study_time', 0) + study_time
                if goal_progress >= user_data['goal']:
                    await ctx.send(
                        f'{ctx.message.author.mention} checked out and reached their study goal for today! Congratulations!'
                        f'{ctx.message.author.mention} has focused ' f'**{round(goal_progress / 60, 2)}** minutes today!'
                        )
                else:
                    await ctx.send(
                        f'{ctx.message.author.mention} checked out and is '
                        f'**{round((user_data["goal"] - goal_progress) / 60, 2)}** minutes away from their study goal.'
                        f'{ctx.message.author.mention} has focused ' f'**{round(goal_progress / 60, 2)}** minutes today!'
                    )
            else:
                await ctx.send(f'{ctx.message.author.mention} checked out!')
        else:
            await ctx.send(f'{ctx.message.author.mention} please check in before checking out!')
            return
        
    @tasks.loop(hours=24)
    async def reset_daily_study_time(self):
        self.study_times_collection.update_many({}, {'$set': {'daily_study_time': 0}})
    @reset_daily_study_time.before_loop
    async def before_reset_daily_study_time(self):
        now = datetime.datetime.now(TIMEZONE)
        next_reset_time = now.replace(hour=0, minute=0, second=0)
        if now != next_reset_time:
            next_reset_time += datetime.timedelta(days=1)
        await discord.utils.sleep_until(next_reset_time)

    @tasks.loop(hours=24)
    async def update_daily_study_time(self):
        current_date = datetime.datetime.now(TIMEZONE).strftime('%Y-%m-%d')
        for guild in self.bot.guilds:
            for member in guild.members:
                user_id = str(member.id)
                self.user_daily_study_time_collection.update_one(
                    {'user_id': user_id, 'date': current_date},
                    {'$set': {'study_time_this_day': 0}},
                    upsert=True
                )
    @update_daily_study_time.before_loop
    async def before_update_daily_study_time(self):
        now = datetime.datetime.now(TIMEZONE)
        next_update_time = now.replace(hour=0, minute=0, second=0) + datetime.timedelta(days=1)
        await discord.utils.sleep_until(next_update_time)
    
    @hybrid_command(aliases=["sg"])
    async def set_goal(self, ctx, goal: int):
        """Set your daily study goal (in minutes). For example set a 30 minutes goal: !set_gal 30 """
        if goal < 10:
            await ctx.send(f"{ctx.message.author.mention}, the study goal must be at least 10 minutes!")
            return
        
        user_id = str(ctx.message.author.id)
        channel_id = str(ctx.channel.id)
        self.study_times_collection.update_one(
            {'user_id': user_id, 'channel_id': channel_id},
            {'$set': {'goal': goal * 60}},
            upsert=True
        )
        await ctx.send(f'{ctx.message.author.mention} set a study goal of {goal} minutes!')

    def cog_unload(self):
        self.check_timers.cancel()

    @hybrid_command(aliases=['po'])
    @describe(study_time="study time", break_time="break time", cycles="how many cycles")
    async def start_pomodoro(self, ctx, study_time: int, break_time: int = 5, cycles: int = 1):
        """Start a Pomodoro timer.!start_pomodoro 25 5 4 """
        timer = {
            'user_id': ctx.author.id,
            'start_time': datetime.datetime.now(),
            'study_time': study_time,
            'break_time': break_time,
            'cycles': cycles,
            'current_cycle': 0,
            'on_break': False
        }
        self.timers_collection.insert_one(timer)
        await ctx.send(f"{ctx.message.author.mention} Pomodoro timer started!")

    @hybrid_command(aliases=['spo'])
    async def stop_pomodoro(self, ctx):
        """Stop a Pomodoro timer."""
        self.timers_collection.delete_one({'user_id': ctx.author.id})
        await ctx.send(f"{ctx.message.author.mention} Pomodoro timer stopped!")

    @tasks.loop(seconds=60)
    async def check_timers(self):
        """Check timers and send notifications."""
        for timer in self.timers_collection.find():
            elapsed_time = datetime.datetime.now() - timer['start_time']
            total_time = (timer['study_time'] + timer['break_time']) * timer['cycles']
            if elapsed_time.total_seconds() >= total_time:
                self.timers_collection.delete_one({'user_id': timer['user_id']})
                await self.bot.get_user(timer['user_id']).send("Your Pomodoro timer has ended!")
            elif not timer['on_break'] and elapsed_time.total_seconds() >= timer['study_time'] * (
                    timer['current_cycle'] + 1):
                self.timers_collection.update_one({'user_id': timer['user_id']}, {'$set': {'on_break': True}})
                await self.bot.get_user(timer['user_id']).send("Time for a break!")
            elif timer['on_break'] and elapsed_time.total_seconds() >= (timer['study_time'] + timer['break_time']) * (
                    timer['current_cycle'] + 1):
                self.timers_collection.update_one({'user_id': timer['user_id']},
                                                  {'$inc': {'current_cycle': 1}, '$set': {'on_break': False}})
                await self.bot.get_user(timer['user_id']).send("Break's over, back to work!")
