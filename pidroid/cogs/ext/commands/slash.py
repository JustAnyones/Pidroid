import random

from discord.ext import commands
from discord.ext.commands.errors import BadArgument # type: ignore

class MyCog(commands.Cog):
    
    def __init__(self, client: commands.Bot) -> None:
        self.client: commands.Bot = client
    
    @commands.hybrid_command(name="roll2")
    async def roll_command(self, ctx: commands.Context, limit: int = 6):
        #This command is actually used as an app command AND a message command.
        #This means it is invoked with `?ping` and `/ping` (once synced, of course).
        
        if limit <= 1:
            raise BadArgument("Limit cannot be 1 or less. It'd be stupid")
        message = f"You rolled a {random.randint(1, limit)}!"
        if ctx.interaction:
            return await ctx.send(message)
        await ctx.reply(message)
    
async def setup(bot: commands.Bot) -> None:
  await bot.add_cog(MyCog(bot))
      