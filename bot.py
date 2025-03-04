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
            await self.load_extension("news")
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
    c.execute("""
    CREATE TABLE IF NOT EXISTS foreign_nations(
        nation TEXT PRIMARY KEY,
        balance REAL DEFAULT 0.0
    )
    """)
    conn.commit()

    nations = [
        ("Switzerland", 20000.0),
        ("France", 35000.0),
        ("Germany", 30000.0),
        ("Italy", 25000.0),
        ("Spain", 20000.0)
    ]
    c.executemany("INSERT OR IGNORE INTO foreign_nations (nation, balance) VALUES (?, ?)", nations)
    conn.commit()

setup_database()
# Initialize APScheduler
scheduler = AsyncIOScheduler()

async def distribute_ubi():
    """Function to distribute Universal Basic Income (UBI) daily."""
    c.execute("UPDATE users SET balance = balance + 500")
    conn.commit()

async def update_prices():
    """track price changes over a 12 hour period and post news about the 5 biggest movers"""
    c.execute("SELECT district, price_per_unit FROM resources")
    rows = c.fetchall()
    price_change = []
    for district, price in rows:
        fluctuation = random.uniform(-0.10, 0.15)  # Prices change by -10% to +15%
        new_price = max(5, price * (1 + fluctuation))  # Ensure price never drops below $5
        price_change.append((district, new_price - price))
        c.execute("UPDATE resources SET price_per_unit = ? WHERE district = ?", (new_price, district))
    conn.commit()
    price_change.sort(key=lambda x: x[1], reverse=True)
    channel = bot.get_channel(1345074664850067527)
    embed = discord.Embed(
        title="📈 **Market News** 📉",
        description="Here are the top 5 biggest price movers for resources:",
        color=discord.Color.blue()
    )
    for i in range(5):
        district, change = price_change[i]
        if change > 0:
            embed.add_field(name=f"📈 **{district}**", value=f"Increased by ${change:.2f}", inline=False)
        else:
            embed.add_field(name=f"📉 **{district}**", value=f"Decreased by ${-change:.2f}", inline=False)
    await channel.send(embed=embed)
    
    
@bot.command()
async def test():
    await random_international_buyers()   
    
async def random_international_buyers():
    """Randomly selects a foreign nation to buy a resource from the national market."""
    c.execute("SELECT nation FROM foreign_nations")
    nations = c.fetchall()

    for nation in nations:
        if random.random() < 0.125:  # 12.5% chance
            c.execute("SELECT comp_id, resource, amount, price_per_unit FROM national_market")
            market_items = c.fetchall()
            item = random.choice(market_items)
            comp_id, resource, amount, price_per_unit = item
            purchase_amount = random.randint(1, amount)
            total_cost = purchase_amount * price_per_unit

            # Update the market
            c.execute("UPDATE national_market SET amount = amount - ? WHERE comp_id = ? AND resource = ?", (purchase_amount, comp_id, resource))
            c.execute("DELETE FROM national_market WHERE amount <= 0")

            # Update the company's balance
            c.execute("UPDATE companies SET balance = balance + ? WHERE company_id = ?", (total_cost, comp_id))

            # Update the foreign nation's balance
            c.execute("UPDATE foreign_nations SET balance = balance - ? WHERE nation = ?", (total_cost, nation[0]))

            conn.commit()
            c.execute("SELECT name FROM companies WHERE company_id = ?", (comp_id,))
            company = c.fetchone()
            
            channel = bot.get_channel(1345074664850067527)
            embed = discord.Embed(
                title="🌍 **International Trade** 🌍",
                description=f"{nation[0]} has purchased {purchase_amount} units of {resource} from {company[0]} for ${total_cost:.2f}.",
                color=discord.Color.green()
            )
            await channel.send(embed=embed)


async def international_add_resouce():
    """A foregin company can randomly add resources to the national market with a 40% chance to undercut current prices and 60% to post at an average costs."""
    c.execute("SELECT nation FROM foreign_nations")
    nations = c.fetchall()
    c.execute("SELECT comp_id, resource, amount, price_per_unit FROM national_market")
    market_items = c.fetchall()

    if not market_items:
        return  # No items in the market

    for nation in nations:
        if random.random() < 0.40:  # 40% chance
            item = random.choice(market_items)
            comp_id, resource, amount, price_per_unit = item
            list_amount = random.randint(1, 25)
            c.execute("SELECT AVG(price_per_unit) FROM national_market WHERE resource = ?", (resource,))
            average_price = c.fetchone()[0]
            if random.random() < 0.40:  # 40% chance to undercut
                new_price = average_price * (2 / 3)  # Undercut by 1/3rd
            else:
                new_price = average_price  # Post at average cost

            c.execute("INSERT INTO national_market (comp_id, resource, amount, price_per_unit) VALUES (?, ?, ?, ?)",
                      (comp_id, resource, list_amount, new_price))
            conn.commit()

            channel = bot.get_channel(1345074664850067527)
            embed = discord.Embed(
                title="🌍 **International Market** 🌍",
                description=f"{nation[0]} has listed {list_amount} units of {resource} at ${new_price:.2f} per unit.",
                color=discord.Color.blue()
            )
            await channel.send(embed=embed)
            
@bot.command()
@commands.has_permissions(administrator=True)
async def clear(ctx):
    """Clears all messages in the current channel."""
    await ctx.channel.purge()


@bot.command()
@commands.has_permissions(administrator=True)
async def clean_ownership(ctx):
    """Removes any company in the ownership table that no longer exists."""
    c.execute("SELECT name FROM companies")
    companies = c.fetchall()
    c.execute("SELECT company_name FROM ownership")
    ownership = c.fetchall()
    print("here")
    for company in ownership:
        if (company[0],) not in companies:
            c.execute("DELETE FROM ownership WHERE company_name = ?", (company[0],))
            conn.commit()
    await ctx.send("Ownership table cleaned.")
    

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
                "`lp` → Leave your current political party.\n"
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
                "`make_public [Company] [4 char ticker]` → List a company on the stock exchange.\n"
                "`stock_ownership` → Check your stock ownership.\n"
                "`bs [Company] [Amount]` → Buy shares in a company.\n"
                "`ss [Company] [Amount]` → Sell shares of a company (corporate tax applies).\n"
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
                "`is [Company] [Amount]` → Issues an amount of stock for a public company.\n"
                "`isp [Company] [Amount]` → Issues an amount of stock for a private company.\n"
                "`ps [Company] [Amount] [Price] [User]` → Starts a private stock sale for a certain amount of shares at x price.\n"
                "`cbs [Company Buying] [Stock] [Amount]` → Buy a company owned stock.\n"
                "`css [Company Selling] [Stock] [Amount]` → Sell a company owned stock (tax applied).\n"
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
            "`lm [Company] [Resouce] [Amount] [Price]` → List company resources for sale on the national market.\n"
            "`bm [Buying Company] [Selling Company] [Resource] [Amount]` → Buy resources from the market.\n"
            "`sm [Page]` → Show the market type an integer to go to a different page.\n"
            ),
            inline=False
        )
        
    if menu == "n":
    # 📰 News Commands
        embed.add_field(
            name="📰 **News Commands**",
            value=(
                "`story [Title] [Story]` → Post a news story. Requires the News role.\n"
            ),
            inline=False
        )

    # 🔧 Other Commands
    embed.add_field(
        name="🔧 **Other Commands**",
        value=(
            "`help [c, e, g, n, p, r, v]` → Company, Economy, Gambling, News, Political, Resource, and Voting help menus.\n"
            "`ping` → Pong!\n"
            "`about @user` → Displays info on yourself or others.\n"
            "`rp` → Assign the RP Ping role.\n"
        ),
        inline=False
    )

    embed.set_footer(text="Use the commands wisely to shape your world!")
    
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def force_ubi(ctx):
    """Manually triggers the UBI distribution."""
    await distribute_ubi()
    await update_prices()
    await ctx.send("Universal Basic Income distributed.")

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
        scheduler.add_job(random_international_buyers, "cron", hour=5, minute=0)
        scheduler.add_job(random_international_buyers, "cron", hour=11, minute=0)
        scheduler.add_job(random_international_buyers, "cron", hour=17, minute=0)
        scheduler.add_job(random_international_buyers, "cron", hour=23, minute=0)
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
