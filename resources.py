import sqlite3
import random
import discord
from discord.ext import commands, tasks

class Resources(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect("game.db", check_same_thread=False)
        self.c = self.conn.cursor()
        self.setup_resources()
        self.update_prices.start()  # Start the daily price fluctuation task

    def setup_resources(self):
        """Create resources table and initialize district resource production."""
        self.c.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            district TEXT PRIMARY KEY,
            resource TEXT,
            stockpile INTEGER DEFAULT 100000,
            price_per_unit REAL DEFAULT 100.0
        )
        """)
        self.conn.commit()

        # Initial resource assignments
        initial_resources = {
            "Corinthia": "Factories",
            "Vordane": "Metal",
            "Drakenshire": "Military Strength",
            "Eldoria": "Silicon",
            "Caelmont": "Luxury Goods"
        }

        for district, resource in initial_resources.items():
            self.c.execute("INSERT OR IGNORE INTO resources (district, resource) VALUES (?, ?)", (district, resource))
        self.conn.commit()

    @commands.command()
    async def check_resources(self, ctx):
        """Displays current resource stockpiles and prices."""
        self.c.execute("SELECT * FROM resources")
        rows = self.c.fetchall()

        if not rows:
            await ctx.send("⚠️ No resource data available.")
            return

        embed = discord.Embed(title="🌍 **Current Resource Market**", color=discord.Color.green())
        for row in rows:
            district, resource, stockpile, price = row
            embed.add_field(
                name=f"🏙️ {district}",
                value=f"🔹 **Resource:** {resource}\n📦 **Stockpile:** {stockpile}\n💰 **Price per Unit:** ${price:.2f}",
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.command()
    async def harvest_resource(self, ctx, company_name: str, amount: int):
        """Allows a company to harvest resources from its assigned district at a cost."""
        if amount <= 0:
            await ctx.send("⚠️ You must harvest a positive amount of resources.")
            return

        user_id = ctx.author.id
        self.c.execute("SELECT district FROM companies WHERE name = ? AND owner_id = ?", (company_name, user_id))
        company_info = self.c.fetchone()

        if not company_info:
            await ctx.send("⚠️ You do not own this company or it does not exist.")
            return

        district = company_info[0]
        self.c.execute("SELECT resource, stockpile, price_per_unit FROM resources WHERE district = ?", (district,))
        resource_info = self.c.fetchone()

        if not resource_info:
            await ctx.send("⚠️ No resources available in this district.")
            return

        resource, stockpile, price_per_unit = resource_info
        cost = price_per_unit * amount

        # Ensure company has enough funds
        self.c.execute("SELECT balance FROM companies WHERE name = ?", (company_name,))
        company_balance = self.c.fetchone()
        if not company_balance or company_balance[0] < cost:
            await ctx.send("⚠️ Your company does not have enough funds to harvest these resources.")
            return

        # Ensure enough stockpile is available
        if stockpile < amount:
            await ctx.send("⚠️ Not enough resources available for harvesting.")
            return

        # Deduct funds from the company, update stockpile
        self.c.execute("UPDATE companies SET balance = balance - ? WHERE name = ?", (cost, company_name))
        self.c.execute("UPDATE resources SET stockpile = stockpile - ? WHERE district = ?", (amount, district))
        self.conn.commit()

        await ctx.send(f"✅ **{company_name}** has harvested **{amount} {resource}** for **${cost:.2f}**.")

    @tasks.loop(hours=24)
    async def update_prices(self):
        """Randomly adjusts resource prices every 24 hours to simulate market fluctuation."""
        self.c.execute("SELECT district, price_per_unit FROM resources")
        rows = self.c.fetchall()

        for district, price in rows:
            fluctuation = random.uniform(-0.4, 0.2)  # Prices change by -40% to +20%
            new_price = max(10, price * (1 + fluctuation))  # Ensure price never drops below $10
            self.c.execute("UPDATE resources SET price_per_unit = ? WHERE district = ?", (new_price, district))

        self.conn.commit()
        print("🔄 Resource prices updated!")

async def setup(bot):
    await bot.add_cog(Resources(bot))
