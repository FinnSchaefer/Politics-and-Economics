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
        self.c.execute("""
        CREATE TABLE IF NOT EXISTS company_resources (
            company_id INTEGER,
            district TEXT,
            resource TEXT,
            stockpile INTEGER DEFAULT 0,
            FOREIGN KEY (company_id) REFERENCES companies (id)
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
        """Shows all reosources by a company"""
        self.c.execute("SELECT * FROM company_resources WHERE company_id = ?", (company,))
        rows = self.c.fetchall()

        if not rows:
            await ctx.send("⚠️ No resource data available.")
            return

        embed = discord.Embed(title=f"🏢 {company}", color=discord.Color.green())
        for row in rows:
            company_id, district, resource, stockpile, price = row
            embed.add_field(
                value=f"🔹 **Resource:** {resource}\n📦 **Stockpile:** {stockpile}\n💰 **Price per Unit:** ${price:.2f}",
                inline=False
            )
        await ctx.send(embed=embed)
        
    @commands.command()
    async def harvest_resource(self, ctx, company_name: str, amount: int):
        """Allows a company to harvest resources from its assigned district at a cost that starts at 1/3rd the price of the material but becomes exponentially more expensive per resource harvested."""
        # Get the company ID from the company name
        self.c.execute("SELECT company_id FROM companies WHERE name = ?", (company_name,))
        company_row = self.c.fetchone()
        if not company_row:
            await ctx.send("⚠️ Company not found.")
            return
        company_id = company_row[0]

        # Get the district assigned to the company
        self.c.execute("SELECT district FROM users WHERE id = (SELECT owner_id FROM companies WHERE company_id = ?)", (company_id,))
        district_row = self.c.fetchone()
        if not district_row:
            await ctx.send("⚠️ District not found for the company.")
            return
        district = district_row[0]

        # Get the current stockpile and price of the resource in the district
        self.c.execute("SELECT stockpile, price_per_unit FROM resources WHERE district = ?", (district,))
        resource_row = self.c.fetchone()
        if not resource_row:
            await ctx.send("⚠️ Resource not found in the district.")
            return
        stockpile, price_per_unit = resource_row

        # Calculate the cost to harvest the resources
        cost = (price_per_unit / 3) * (1.1 ** amount)
        if stockpile < amount:
            embed = discord.Embed(title="⚠️ Not enough resources", color=discord.Color.red())
            embed.add_field(name="Available Stockpile", value=f"{stockpile} units", inline=True)
            embed.add_field(name="Requested Amount", value=f"{amount} units", inline=True)
            await ctx.send(embed=embed)
            return

        # Deduct the resources from the district stockpile and add to the company's stockpile
        self.c.execute("UPDATE resources SET stockpile = stockpile - ? WHERE district = ?", (amount, district))
        self.c.execute("""
        INSERT INTO company_resources (company_id, district, resource, stockpile) VALUES (?, ?, (SELECT resource FROM resources WHERE district = ?), ?) 
        ON CONFLICT(company_id, district, resource) DO UPDATE SET stockpile = stockpile + ?
        """, (company_id, district, district, amount, amount))

        self.conn.commit()
        embed = discord.Embed(title="✅ Resource Harvested", color=discord.Color.green())
        embed.add_field(name="Company", value=company_name, inline=True)
        embed.add_field(name="Amount", value=f"{amount} units", inline=True)
        embed.add_field(name="Cost", value=f"${cost:.2f}", inline=True)
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
