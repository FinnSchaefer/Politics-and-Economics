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
            comp_id INTEGER DEFAULT 0,
            district TEXT,
            resource TEXT,
            stockpile INTEGER DEFAULT 0,
            FOREIGN KEY (comp_id) REFERENCES companies (company_id)
        )
        """)
        self.c.execute("""
        CREATE TABLE IF NOT EXISTS natinal_market(
            FOREIGN KEY (comp_id) REFERENCES companies (company_id)
            resource TEXT,
            amount INTEGER DEFAULT 0,
            price_per_unit REAL DEFAULT 0.0
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

    @commands.command(aliases=["cr"])
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

    @commands.command(aliases=["cor"])
    async def company_owned_resources(self, ctx, company: str):
        """Shows all reosources by a company"""
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (company,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            company = ticker_result[0]
        self.c.execute("SELECT company_id FROM companies WHERE name = ?", (company,))
        company_row = self.c.fetchone()
        if not company_row:
            await ctx.send("⚠️ Company not found.")
            return
        company_id = company_row[0]
        
        self.c.execute("SELECT * FROM company_resources WHERE comp_id = ?", (company_id,))
        rows = self.c.fetchall()
        
        if not rows:
            await ctx.send("⚠️ No resource data available for this company.")
            return

        embed = discord.Embed(title=f"🏢 {company}", color=discord.Color.green())
        for row in rows:
            _, district, resource, stockpile = row
            self.c.execute("SELECT price_per_unit FROM resources WHERE district = ?", (district,))
            price_row = self.c.fetchone()
            if not price_row:
                await ctx.send(f"⚠️ Price not found for district {district}.")
                return
            price = price_row[0]
            embed.add_field(
            name=f"🏙️ {district}",
            value=f"🔹 **Resource:** {resource}\n📦 **Stockpile:** {stockpile}\n💰 **Price per Unit:** ${price:.2f}",
            inline=False
            )
        await ctx.send(embed=embed)
        
    @commands.command(aliases=["harvest"])
    @commands.cooldown(1,43200,commands.BucketType.user)
    async def harvest_resource(self, ctx, company_name: str, amount: int):
        """Allows a company to harvest resources from its assigned district at a cost that starts at 1/3rd the price of the material but becomes exponentially more expensive per resource harvested."""
        # Get the company ID from the company name
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (company_name,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            company_name = ticker_result[0]
            
        self.c.execute("SELECT company_id FROM companies WHERE name = ?", (company_name,))
        company_row = self.c.fetchone()
        if not company_row:
            await ctx.send("⚠️ Company not found.")
            return
        company_id = company_row[0]
        
        # Get the district assigned to the company
        self.c.execute("SELECT owner_id FROM companies WHERE company_id = ?", (company_id,))
        owner_row = self.c.fetchone()
        if not owner_row:
            await ctx.send("⚠️ Owner not found for the company.")
            return
        owner_id = owner_row[0]

        self.c.execute("SELECT district FROM users WHERE user_id = ?", (owner_id,))
        district_row = self.c.fetchone()
        if not district_row:
            await ctx.send("⚠️ District not found for the company.")
            return
        district = district_row[0]

        # Get the resource assigned to the district
        self.c.execute("SELECT resource FROM resources WHERE district = ?", (district,))
        resource_row = self.c.fetchone()
        if not resource_row:
            await ctx.send("⚠️ Resource not found in the district.")
            return
        resource = resource_row[0]

        # Get the current stockpile and price of the resource in the district
        self.c.execute("SELECT stockpile, price_per_unit FROM resources WHERE district = ?", (district,))
        resource_row = self.c.fetchone()
        if not resource_row:
            await ctx.send("⚠️ Resource not found in the district.")
            return
        stockpile, price_per_unit = resource_row

        if stockpile < amount:
            embed = discord.Embed(title="⚠️ Not enough resources", color=discord.Color.red())
            embed.add_field(name="Available Stockpile", value=f"{stockpile} units", inline=True)
            embed.add_field(name="Requested Amount", value=f"{amount} units", inline=True)
            await ctx.send(embed=embed)
            return

        cost = price_per_unit * amount * (1 + 0.1 * (amount - 1) / 2)
        # Deduct the cost from the company's balance
        if cost > (self.c.execute("SELECT balance FROM companies WHERE company_id = ?", (company_id,)).fetchone()[0]):
            embed = discord.Embed(title="⚠️ Not enough balance", color=discord.Color.red())
            embed.add_field(name="Available Balance", value=f"${self.c.execute('SELECT balance FROM companies WHERE id = ?', (company_id,)).fetchone()[0]:.2f}", inline=True)
            embed.add_field(name="Required Amount", value=f"${cost:.2f}", inline=True)
            await ctx.send(embed=embed)
            return
        
        self.c.execute("UPDATE companies SET balance = balance - ? WHERE company_id = ?", (cost, company_id))
        self.c.execute("UPDATE tax_rate SET government_balance = government_balance + ?", (cost,))
  
        # Deduct the resources from the district stockpile and add to the company's stockpile
        self.c.execute("UPDATE resources SET stockpile = stockpile - ? WHERE district = ?", (amount, district))
        self.c.execute("SELECT stockpile FROM company_resources WHERE comp_id = ? AND resource = ?", (company_id, resource))
        company_stockpile = self.c.fetchone()
        if company_stockpile:
            self.c.execute("UPDATE company_resources SET stockpile = stockpile + ? WHERE comp_id = ? AND resource = ?", (amount, company_id, resource))
        else:
            self.c.execute("INSERT INTO company_resources (comp_id, resource, stockpile, district) VALUES (?, ?, ?, ?)", (company_id, resource, amount, district))
        self.conn.commit()
        embed = discord.Embed(title="✅ Resource Harvested", color=discord.Color.green())
        embed.add_field(name="Company", value=company_name, inline=True)
        embed.add_field(name="Amount", value=f"{amount} units", inline=True)
        embed.add_field(name="Cost", value=f"${cost:.2f}", inline=True)
        await ctx.send(embed=embed)
        
    @commands.command(aliases=["srg"])
    async def sell_resources_government(self, ctx, company: str, resource: str, amount: int):
        """Allows a company to sell resources to the government at the current market price."""
        # Get the company ID from the company name
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (company,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            company = ticker_result[0]
            
        self.c.execute("SELECT owner_id FROM companies WHERE name = ?", (company,))
        owner_row = self.c.fetchone()
        if not owner_row or owner_row[0] != ctx.author.id:
            await ctx.send("⚠️ You are not the owner of this company.")
            return
            
        self.c.execute("SELECT company_id FROM companies WHERE name = ?", (company,))
        company_row = self.c.fetchone()
        if not company_row:
            await ctx.send("⚠️ Company not found.")
            return
        company_id = company_row[0]
        
        # Check if the company has enough of the resource to sell
        self.c.execute("SELECT stockpile FROM company_resources WHERE comp_id = ? AND resource = ?", (company_id, resource))
        company_stockpile = self.c.fetchone()
        if not company_stockpile or company_stockpile[0] < amount:
            await ctx.send("⚠️ Not enough resources to sell.")
            return

        # Get the current market price of the resource
        self.c.execute("SELECT price_per_unit FROM resources WHERE resource = ?", (resource,))
        price_row = self.c.fetchone()
        if not price_row:
            await ctx.send("⚠️ Resource not found in the market.")
            return
        price_per_unit = price_row[0]
        tax_rate = self.c.execute("SELECT corporate_tax FROM tax_rate").fetchone()[0]
        # Calculate the total sale amount
        total_sale_amount = price_per_unit * amount
        taxed_amount = total_sale_amount * tax_rate
        total_sale_amount = total_sale_amount - taxed_amount

        # Update the company's resource stockpile and balance
        self.c.execute("UPDATE company_resources SET stockpile = stockpile - ? WHERE comp_id = ? AND resource = ?", (amount, company_id, resource))
        self.c.execute("UPDATE companies SET balance = balance + ? WHERE company_id = ?", (total_sale_amount, company_id))
        
        # Update the government balance
        self.c.execute("UPDATE tax_rate SET government_balance = government_balance - ?", (total_sale_amount,))
        self.conn.commit()

        embed = discord.Embed(title="✅ Resources Sold to Government", color=discord.Color.green())
        embed.add_field(name="Company", value=company, inline=True)
        embed.add_field(name="Resource", value=resource, inline=True)
        embed.add_field(name="Amount", value=f"{amount} units", inline=True)
        embed.add_field(name="Tax", value=f"${taxed_amount:.2f}", inline=True)
        embed.add_field(name="Total Sale Amount", value=f"${total_sale_amount:.2f}", inline=True)
        await ctx.send(embed=embed)      
        
    @commands.command(aliases=["lm"])
    async def list_on_market(self, ctx, company: str, resource: str, amount: int):
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (company,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            company = ticker_result[0]
        
        self.c.execute("SELECT owner_id FROM companies WHERE name = ?", (company,))
        owner_row = self.c.fetchone()
        if not owner_row or owner_row[0] != ctx.author.id:
            await ctx.send("⚠️ You are not the owner of this company.")
            return
        
        self.c.execute("SELECT company_id FROM companies WHERE name = ?", (company,))
        company_row = self.c.fetchone()
        if not company_row:
            await ctx.send("⚠️ Company not found.")
            return
        
        company_id = company_row[0]
        
        # Check if the company has enough of the resource to list
        self.c.execute("SELECT stockpile FROM company_resources WHERE comp_id = ? AND resource = ?", (company_id, resource))
        company_stockpile = self.c.fetchone()
        if not company_stockpile or company_stockpile[0] < amount:
            await ctx.send("⚠️ Not enough resources to list.")
            return

        # Get the current market price of the resource
        self.c.execute("SELECT price_per_unit FROM resources WHERE resource = ?", (resource,))
        price_row = self.c.fetchone()
        if not price_row:
            await ctx.send("⚠️ Resource not found in the market.")
            return
        price_per_unit = price_row[0]

        # Update the company's resource stockpile
        self.c.execute("UPDATE company_resources SET stockpile = stockpile - ? WHERE comp_id = ? AND resource = ?", (amount, company_id, resource))
        
        # Insert or update the national market with the listed resource
        self.c.execute("""
        INSERT INTO national_market (comp_id, resource, amount, price_per_unit)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(comp_id, resource) DO UPDATE SET
        amount = amount + excluded.amount,
        price_per_unit = excluded.price_per_unit
        """, (company_id, resource, amount, price_per_unit))
        
        self.conn.commit()

        embed = discord.Embed(title="✅ Resource Listed on Market", color=discord.Color.green())
        embed.add_field(name="Company", value=company, inline=True)
        embed.add_field(name="Resource", value=resource, inline=True)
        embed.add_field(name="Amount", value=f"{amount} units", inline=True)
        embed.add_field(name="Price per Unit", value=f"${price_per_unit:.2f}", inline=True)
        await ctx.send(embed=embed)
        
    @commands.command(aliases=["bm"])
    async def buy_from_market(self, ctx, company: str, company_selling: str, resource: str, amount: int):
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (company,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            company = ticker_result[0]
            
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (company_selling,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            company_selling = ticker_result[0]
        
        self.c.execute("SELECT company_id FROM companies WHERE name = ?", (company,))
        company_row = self.c.fetchone()
        if not company_row:
            await ctx.send("⚠️ Company not found.")
            return
        company_id = company_row[0]
        
        self.c.execute("SELECT company_id FROM companies WHERE name = ?", (company_selling,))
        selling_company_row = self.c.fetchone()
        if not selling_company_row:
            await ctx.send("⚠️ Selling company not found.")
            return
        selling_company_id = selling_company_row[0]
        
        # Check if the selling company has enough of the resource to sell
        self.c.execute("SELECT amount, price_per_unit FROM national_market WHERE comp_id = ? AND resource = ?", (selling_company_id, resource))
        market_row = self.c.fetchone()
        if not market_row or market_row[0] < amount:
            await ctx.send("⚠️ Not enough resources available on the market.")
            return
        available_amount, price_per_unit = market_row
        
        # Check if the buying company has enough balance to buy
        self.c.execute("SELECT balance FROM companies WHERE company_id = ?", (company_id,))
        balance_row = self.c.fetchone()
        if not balance_row or balance_row[0] < amount * price_per_unit:
            await ctx.send("⚠️ Not enough balance to buy the resources.")
            return
        balance = balance_row[0]
        
        total_cost = amount * price_per_unit
        tax_rate = self.c.execute("SELECT corporate_tax FROM tax_rate").fetchone()[0]
        taxed_amount = total_cost * tax_rate
        total_cost_2 = total_cost + taxed_amount
        
        # Update the balances and stockpiles
        self.c.execute("UPDATE companies SET balance = balance - ? WHERE company_id = ?", (total_cost_2, company_id))
        self.c.execute("UPDATE companies SET balance = balance + ? WHERE company_id = ?", (total_cost, selling_company_id))
        self.c.execute("UPDATE national_market SET amount = amount - ? WHERE comp_id = ? AND resource = ?", (amount, selling_company_id, resource))
        self.c.execute("DELETE FROM national_market WHERE amount = 0")
        self.c.exexcue("UPDATE tax_rate SET government_balance = government_balance + ?", (taxed_amount,))
        self.c.execute("SELECT stockpile FROM company_resources WHERE comp_id = ? AND resource = ?", (company_id, resource))
        company_stockpile = self.c.fetchone()
        if company_stockpile:
            self.c.execute("UPDATE company_resources SET stockpile = stockpile + ? WHERE comp_id = ? AND resource = ?", (amount, company_id, resource))
        else:
            self.c.execute("INSERT INTO company_resources (comp_id, resource, stockpile, district) VALUES (?, ?, ?, ?)", (company_id, resource, amount, None))
        self.conn.commit()
        
        embed = discord.Embed(title="✅ Resource Purchased", color=discord.Color.green())
        embed.add_field(name="Buying Company", value=company, inline=True)
        embed.add_field(name="Selling Company", value=company_selling, inline=True)
        embed.add_field(name="Resource", value=resource, inline=True)
        embed.add_field(name="Units", value=f"{amount}", inline=True)
        embed.add_field(name="Tax", value=f"${taxed_amount:.2f}", inline=True)
        embed.add_field(name="Total Cost", value=f"${total_cost:.2f}", inline=True)
        await ctx.send(embed=embed)
        
    @commands.command(aliases=["sm"])
    async def show_market(self,ctx, page: int=1):
        self.c.execute("SELECT * FROM national_market")
        rows = self.c.fetchall()
        if not rows:
            await ctx.send("⚠️ No resources listed on the market.")
            return

        items_per_page = 5
        offset = (page - 1) * items_per_page

        self.c.execute("SELECT * FROM national_market LIMIT ? OFFSET ?", (items_per_page, offset))
        rows = self.c.fetchall()

        embed = discord.Embed(title="🌍 **National Market**", color=discord.Color.green())
        for i, row in enumerate(rows, start=offset + 1):
            comp_id, resource, amount, price_per_unit = row
            self.c.execute("SELECT name FROM companies WHERE company_id = ?", (comp_id,))
            company_name = self.c.fetchone()[0]
            embed.add_field(
            name=f"{i}. 🏢 {company_name}",
            value=f"🔹 **Resource:** {resource}\n📦 **Amount:** {amount} units\n💰 **Price per Unit:** ${price_per_unit:.2f}",
            inline=False
            )
        await ctx.send(embed=embed)
        
    @harvest_resource.error
    async def harvest_resource_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            minutes, seconds = divmod(error.retry_after, 60)
            await ctx.send(f"⏰ You are on cooldown. Try again in {minutes:.0f} minutes and {seconds:.0f} seconds.")
        else:
            await ctx.send(f"⚠️ An error occurred: {error}")

async def setup(bot):
    await bot.add_cog(Resources(bot))
