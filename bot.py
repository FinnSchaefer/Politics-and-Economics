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

class MyBot(commands.Bot):
    async def setup_hook(self):
        """Ensure cogs load correctly."""
        try:
            await self.load_extension("economy")
            await self.load_extension("politics")
            print("Cogs loaded successfully.")
        except Exception as e:
            print(f"Error loading cogs: {e}")

bot = MyBot(command_prefix=".", intents=intents)
bot.remove_command("help")  # Remove default help command
# Database setup
conn = sqlite3.connect("game.db")
c = conn.cursor()

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
        ),
        inline=False
    )

    # 💰 Economy Commands
    embed.add_field(
        name="💰 **Economy Commands**",
        value=(
            "`balance` → Check your balance.\n"
            "`send_money [Amount] [User]` → Transfer money.\n"
            "`create_company [Name]` → Start a company.\n"
            "`stock_price [Company]` → Check a stocks value.\n"
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
        scheduler.add_job(distribute_ubi, "interval", days=1)
        scheduler.start()

@bot.event
async def on_message(message):
    """Ensure the bot processes commands correctly."""
    print(f"Message received: {message.content} from {message.author}")

    if message.author == bot.user:
        return  # Ignore bot's own messages

    ctx = await bot.get_context(message)
    if ctx.command:
        print(f"Command detected: {ctx.command.name}")

    await bot.process_commands(message)  # Ensure command processing

# Test Ping Command
@bot.command()
async def ping(ctx):
    """Basic ping command to check if the bot is working."""
    await ctx.send("Pong!")

# Ensure database setup for users
def setup_database():
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 500,
        district TEXT,
        senator INTEGER DEFAULT 0,
        chancellor INTEGER DEFAULT 0
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        company_id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER,
        name TEXT,
        equity INTEGER DEFAULT 0,
        shares INTEGER DEFAULT 100,
        FOREIGN KEY (owner_id) REFERENCES users(user_id)
    )
    """)
    conn.commit()

setup_database()

# Start the bot
def main():
    asyncio.run(bot.start(TOKEN))

if __name__ == "__main__":
    main()
