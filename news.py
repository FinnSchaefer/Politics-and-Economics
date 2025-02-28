import discord
import random
from discord.ext import commands

class News(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_role("News")
    async def story(self, ctx, title: str, story: str):
        if ctx.channel.id != 1344822725532975185:
            await ctx.send("You can only use this command in #post-news-here.")
            return
        channel = self.bot.get_channel(1344821784733552691)
        embed = discord.Embed(title=title, description=story, color=discord.Color.green())
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)
        embed.set_footer(text="Posted on " + ctx.message.created_at.strftime("%m/%d/%Y, %H:%M:%S"))
        await channel.send(embed=embed)