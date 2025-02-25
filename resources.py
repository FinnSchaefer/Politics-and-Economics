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
    async def company_owned_resources(self, ctx, company: str):
        """Shows all reosources by the company"""
        self.c.execute("SELECT district, resource, stockpile, price_per_unit FROM resources WHERE district IN (SELECT district FROM companies WHERE name = ?)", (company,))
        rows = self.c.fetchall()

        if not rows:
            await ctx.send(f"⚠️ No resources found for company '{company}'.")
            return

        embed = discord.Embed(title=f"🏢 **{company}'s Owned Resources**", color=discord.Color.blue())
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
        """Allows a company to harvest resources from its assigned district at a cost that starts at 1/3rd the price of the material but becomes exponentially more expensive per resource harvested."""
        # Check if the company exists in the database
        self.c.execute("SELECT owner_id FROM companies WHERE name = ?", (company_name,))
        result = self.c.fetchone()
        if not result:
            await ctx.send(f"⚠️ Company '{company_name}' does not exist.")
            return

        owner_id = result[0]
        district = self.c.execute("SELECT district FROM users WHERE id = ?", (owner_id,))

        # Get the current stockpile and price of the resource
        self.c.execute("SELECT stockpile, price_per_unit FROM resources WHERE district = ?", (district,))
        resource_data = self.c.fetchone()
        if not resource_data:
            await ctx.send(f"⚠️ No resources found for district '{district}'.")
            return

        stockpile, price_per_unit = resource_data

        if amount > stockpile:
            await ctx.send(f"⚠️ Not enough resources in stockpile. Available: {stockpile}")
            return

        # Calculate the cost using an exponential formula
        cost = sum(price_per_unit * (1/3) * (1.1 ** i) for i in range(amount))

        # Deduct the resources from the stockpile
        new_stockpile = stockpile - amount
        self.c.execute("UPDATE resources SET stockpile = ? WHERE district = ?", (new_stockpile, district))
        self.conn.commit()

        embed = discord.Embed(title="✅ Harvest Successful", color=discord.Color.blue())
        embed.add_field(name="Company", value=company_name, inline=True)
        embed.add_field(name="District", value=district, inline=True)
        embed.add_field(name="Amount Harvested", value=f"{amount} units", inline=True)
        embed.add_field(name="Total Cost", value=f"${cost:.2f}", inline=True)
        embed.add_field(name="New Stockpile", value=f"{new_stockpile} units", inline=True)
        await ctx.send(embed=embed)
    
    @commands.command()
    async def sell_resources(self, ctx, company: str, resource: str, amount: int):
        """Sells an amount of a given resource that the company owns"""
        # Check if the company exists in the database
        self.c.execute("SELECT district FROM companies WHERE name = ?", (company,))
        result = self.c.fetchone()
        if not result:
            await ctx.send(f"⚠️ Company '{company}' does not exist.")
            return

        district = result[0]

        # Get the current stockpile and price of the resource
        self.c.execute("SELECT stockpile, price_per_unit FROM resources WHERE district = ? AND resource = ?", (district, resource))
        resource_data = self.c.fetchone()
        if not resource_data:
            await ctx.send(f"⚠️ No resources found for district '{district}' with resource '{resource}'.")
            return

        stockpile, price_per_unit = resource_data

        if amount > stockpile:
            await ctx.send(f"⚠️ Not enough resources in stockpile. Available: {stockpile}")
            return

        # Calculate the total sale value
        total_value = amount * price_per_unit

        # Deduct the resources from the stockpile
        new_stockpile = stockpile - amount
        self.c.execute("UPDATE resources SET stockpile = ? WHERE district = ?", (new_stockpile, district))
        self.conn.commit()

        embed = discord.Embed(title="✅ Sale Successful", color=discord.Color.green())
        embed.add_field(name="Company", value=company, inline=True)
        embed.add_field(name="District", value=district, inline=True)
        embed.add_field(name="Resource", value=resource, inline=True)
        embed.add_field(name="Amount Sold", value=f"{amount} units", inline=True)
        embed.add_field(name="Total Value", value=f"${total_value:.2f}", inline=True)
        embed.add_field(name="New Stockpile", value=f"{new_stockpile} units", inline=True)
        await ctx.send(embed=embed)
        
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
