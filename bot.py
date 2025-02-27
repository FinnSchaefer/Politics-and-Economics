import asyncio
import discord
import sqlite3
import os
import random
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise ValueError("Bot token is missing. Make sure DISCORD_BOT_TOKEN is set in the .env file.")

# Set up bot with required intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True  # Required for member tracking
intents.message_content = True  # Ensures bot can read messages
# Ensure database setup for users

class MyBot(commands.Bot):
    async def setup_hook(self):
        """Ensure cogs load correctly."""
        try:
            await self.load_extension("economy")
            await self.load_extension("politics")
            await self.load_extension("companies")
            await self.load_extension("resources")
            print("Cogs loaded successfully.")
        except Exception as e:
            print(f"Error loading cogs: {e}")

bot = MyBot(command_prefix=".", intents=intents)
bot.remove_command("help")  # Remove default help command
# Database setup
conn = sqlite3.connect("game.db")
c = conn.cursor()

def setup_database():
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0.0,
        district TEXT,
        party TEXT,
        senator INTEGER DEFAULT 0,
        chancellor INTEGER DEFAULT 0,
        vote_senate INTEGER DEFAULT 0,
        vote_chancellor INTEGER DEFAULT 0,
        last_move TEXT
    )
    """)
    conn.commit()

setup_database()
# Initialize APScheduler
scheduler = AsyncIOScheduler()

async def distribute_ubi():
    """Function to distribute Universal Basic Income (UBI) daily."""
    c.execute("UPDATE users SET balance = balance + 500")
    conn.commit()
    
async def update_prices(self):
        """Randomly adjusts resource prices every 24 hours to simulate market fluctuation."""
        self.c.execute("SELECT district, price_per_unit FROM resources")
        rows = self.c.fetchall()

        for district, price in rows:
            fluctuation = random.uniform(-0.1, 0.1)  # Prices change by -40% to +20%
            new_price = max(5, price * (1 + fluctuation))  # Ensure price never drops below $5
            self.c.execute("UPDATE resources SET price_per_unit = ? WHERE district = ?", (new_price, district))

        self.conn.commit()
        print("🔄 Resource prices updated!")

@bot.command()
@commands.has_permissions(administrator=True)
async def clear(ctx):
    """Clears all messages in the current channel."""
    await ctx.channel.purge()

@bot.command()
@commands.has_permissions(administrator=True)
async def rolestrip(ctx):
    """Removes all roles from all users in the server."""
    for member in ctx.guild.members:
        try:
            await member.edit(roles=[])
            await asyncio.sleep(1)  # Add delay to avoid rate limits
        except discord.Forbidden:
            await ctx.send(f"Failed to remove roles from {member.name} due to insufficient permissions.")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to remove roles from {member.name} due to an HTTP error: {e}")
    await ctx.send("Roles have been stripped from all users.")

@bot.command()
async def rp(ctx):
    """Assings the RP Ping role to the user."""
    role = discord.utils.get(ctx.guild.roles, name="RP Ping")
    await ctx.author.add_roles(role)
    embed = discord.Embed(
        title="Role Assigned",
        description="You have been assigned the RP Ping role.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="help")
async def help(ctx, menu: str = None):
    """Displays a help message with all available commands."""

    embed = discord.Embed(
        title="📜 **Server Commands Guide**",
        description="Welcome to The Republic of Severum: Political & Economic Simulation! Below is a list of commands to help you get started.",
        color=discord.Color.gold()
    )
    if (menu=="p"):
        # 🏛️ Politics Commands
        embed.add_field(
            name="🏛️ **Politics Commands**",
            value=(
                "`join [District]` → Join a district.\n"
                "`propose_bill [Name] [Desc] [Link]` → Senator-only: Propose a law.\n"
                "`bills` → View all proposed bills.\n"
                "`laws` → See all passed laws.\n"
                "`start_election` → Admin-only: Start elections.\n"
                "`set_tax [Corporate Rate] [Trade Rate]` → Chancellor-only: Set tax rates.\n"
                "`mp [Party Name]` → Create a new political party.\n"
                "`jp [Party Name]` → Join an existing political party.\n"
                "`dp [Party Name]` → Delete a political party.\n"
                "`pp` → Show all political parties.\n"
            ),
            inline=False
        )

    if (menu == "e"):
    # 💰 Economy Commands
        embed.add_field(
            name="💰 **Economy Commands**",
            value=(
                "`balance` → Check your balance.\n"
                "`bg` → Check the government's balance.\n"
                "`send [User] [Amount]` → Transfer money.\n"
                "`sendc [Company] [Recipient] [Amount]` → Transfer money from a company to user.\n"
                "`send2c [Company] [Amount]` → Transfer money to a company.\n"
                "`stock_price [Company]` → Check a stock’s value.\n"
                "`make_public [Company]` → List a company on the stock exchange.\n"
                "`stock_ownership` → Check your stock ownership.\n"
            ),
            inline=False
        )

    if (menu == "c"):
        # 🏢 Company Commands
        embed.add_field(
            name="🏢 **Company Commands**",
            value=(
                "`companies [Page number]` → View all registered companies.\n"
                "`create_company [Name]` → Start a company.\n"
                "`delete_company [Name]` → Close a company.\n"
                "`sendc [Company] [Recipient] [Amount]` → Transfer money from a company.\n"
                "`buy_shares [Company] [Amount]` → Buy shares in a company (corporate tax applies).\n"
                "`sell_shares [Company] [Amount]` → Sell shares of a company (corporate tax applies).\n"
                "`is [Company] [Amount]` → Issues an amount of stock.\n"
                "`cbs [Company Buying] [Stock] [Amount]` → Buy a company owned stock.\n"
                "`css [Company Selling] [Stock] [Amount]` → Sell a company owned stock..\n"
                "`appoint_board_member [Company] @User` → Assign a board member.\n"
            ),
            inline=False
        )

    if (menu == "v"):
        # 🗳️ Voting Commands
        embed.add_field(
            name="🗳️ **Voting Commands**",
            value=(
                "`vote_bill [Bill number] aye/nay` → Senator-only: Vote on legislation. Must be typed in #senate-voting.\n"
                "`vote_senator [District] @user` → Elect your senator.\n"
                "`vote_chancellor @user` → Senator-only: Elect the Chancellor. Must be typed in #senate-voting.\n"
            ),
            inline=False
        )

    if (menu == "g"):
        # 🎰 Gambling Commands
        embed.add_field(
            name="🎰 **Gambling Commands**",
            value=(
                "`rou [Amount] [Color or Number]` → Play roulette.\n"
                "`slots [Amount]` → Play the slot machine.\n"
            ),
            inline=False
        )
        
    if menu == "r":
        #resource commands
        embed.add_field(
            name="🌿 **Resource Commands**",
            value=(
            "`harvest [Company] [Amount]` → Mine the districts assigned resource.\n"
            "`cr` → Check current resource price and amounts left to harvest.\n"
            "`cor [Company]` → Trade resources with another user.\n"
            ),
            inline=False
        )

    # 🔧 Other Commands
    embed.add_field(
        name="🔧 **Other Commands**",
        value=(
            "`help [c, e, g, p, r, v]` → Company, Economy, Gambling, Political, Resource, and Voting help menus.\n"
            "`ping` → Pong!\n"
            "`about @user` → Displays info on yourself or others.\n"
            "`rp` → Assign the RP Ping role.\n"
        ),
        inline=False
    )

    embed.set_footer(text="Use the commands wisely to shape your world!")
    
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    """Event triggered when the bot is ready."""
    print(f"Logged in as {bot.user}")
    print(f"Command prefix: {bot.command_prefix}")

    # Start the scheduler once the bot is ready
    if not scheduler.running:
        scheduler.add_job(distribute_ubi, "cron", hour=5, minute=0)  # 12am EST (5am UTC)
        scheduler.add_job(distribute_ubi, "cron", hour=17, minute=0)  # 12pm EST (5pm UTC)
        scheduler.add_job(update_prices, "cron", hour=5, minute=0)
        scheduler.add_job(update_prices, "cron", hour=17, minute=0)
        scheduler.start()

# Test Ping Command
@bot.command()
async def ping(ctx):
    """Basic ping command to check if the bot is working."""
    await ctx.send("Pong!")


# Start the bot
def main():
    asyncio.run(bot.start(TOKEN))

if __name__ == "__main__":
    main()
