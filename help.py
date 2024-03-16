import discord
from discord.ext import commands as discord_commands


class CustomHelpCommand(discord_commands.HelpCommand):
    def get_command_signature(self, command):
        aliases = f'{command.name} ({self.context.prefix}{" ".join(command.aliases)})'
        return f'🔹 {self.context.prefix}{aliases} {command.signature}'

    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="🤖 Bot Commands", color=0x3498db)
        embed.set_footer(text="📝 Use the prefix followed by the command name (or its alias) to use a command.")
        for cog, commands in mapping.items():
            if cog:
                cog_name = getattr(cog, "qualified_name", "No Category")
                commands_desc = ''
                for command in commands:
                    if not command.hidden:
                        commands_desc += f'**{self.get_command_signature(command)}**\n- {command.short_doc}\n\n'
                if commands_desc:
                    embed.add_field(name=f'📚 {cog_name}', value=commands_desc, inline=False)
        channel = self.get_destination()
        await channel.send(embed=embed)









