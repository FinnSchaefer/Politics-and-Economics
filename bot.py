import asyncio
import discord
import sqlite3
import os
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
        senator INTEGER DEFAULT 0,
        chancellor INTEGER DEFAULT 0
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

@bot.command(name="help")
async def help(ctx):
    """Displays a help message with all available commands."""

    embed = discord.Embed(
        title="📜 **Server Commands Guide**",
        description="Welcome to The Republic of Severum: Political & Economic Simulation! Below is a list of commands to help you get started.",
        color=discord.Color.gold()
    )

    # 🏛️ Politics Commands
    embed.add_field(
        name="🏛️ **Politics Commands**",
        value=(
            "`join_district [District]` → Join a district.\n"
            "`propose_bill [Name] [Desc] [Link]` → Senator-only: Propose a law.\n"
            "`list_bills` → View all proposed bills.\n"
            "`list_laws` → See all passed laws.\n"
            "`start_election` → Admin-only: Start elections.\n"
            "`set_tax [Corporate Rate] [Trade Rate]` → Chancellor-only: Set tax rates.\n"
        ),
        inline=False
    )

    # 💰 Economy Commands
    embed.add_field(
        name="💰 **Economy Commands**",
        value=(
            "`balance` → Check your balance.\n"
            "`send [User] [Amount]` → Transfer money.\n"
            "`stock_price [Company]` → Check a stock’s value.\n"
            "`make_public [Company]` → List a company on the stock exchange.\n"
        ),
        inline=False
    )

    # 🏢 Company Commands
    embed.add_field(
        name="🏢 **Company Commands**",
        value=(
            "`list_companies` → View all registered companies.\n"
            "`create_company [Name]` → Start a company.\n"
            "`sendc [Company] [Recipient] [Amount]` → Transfer money from a company.\n"
            "`buy_shares [Company] [Amount]` → Buy shares in a company (corporate tax applies).\n"
            "`sell_shares [Company] [Amount]` → Sell shares of a company (corporate tax applies).\n"
            "`appoint_board_member [Company] @User` → Assign a board member.\n"
        ),
        inline=False
    )

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

    # 🔧 Other Commands
    embed.add_field(
        name="🔧 **Other Commands**",
        value=(
            "`help` → Display this message.\n"
            "`ping` → Pong!\n"
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
