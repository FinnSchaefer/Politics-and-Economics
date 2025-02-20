import discord
import sqlite3
import json
from discord.ext import commands
import matplotlib.pyplot as plt
import io

class Companies(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect("game.db", check_same_thread=False)
        self.c = self.conn.cursor()
        self.setup_companies()

    def setup_companies(self):
        """Create required database tables if they don't exist."""
        self.c.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            company_id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER,
            name TEXT UNIQUE,
            balance INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 100,
            board_members TEXT DEFAULT '[]',
            is_public INTEGER DEFAULT 0
        )
        """)
        self.c.execute("""
        CREATE TABLE IF NOT EXISTS ownership (
            owner_id INTEGER,
            company_name TEXT,
            shares INTEGER DEFAULT 0,
            PRIMARY KEY (owner_id, company_name),
            FOREIGN KEY (owner_id) REFERENCES users(user_id),
            FOREIGN KEY (company_name) REFERENCES companies(name)
        )
        """)
        self.conn.commit()


    @commands.command()
    async def create_company(self, ctx, company_name: str):
        """Creates a new company for the user."""
        owner_id = ctx.author.id
        
        self.c.execute("SELECT balance FROM users WHERE user_id = ?", (owner_id,))
        user_balance = self.c.fetchone()
        
        if not user_balance or user_balance[0] < 1000:
            await ctx.send("⚠️ You need at least $1000 to create a company.")
            return
        
        self.c.execute("SELECT name FROM companies WHERE owner_id = ?", (owner_id,))
        existing_company = self.c.fetchone()
        
        if existing_company:
            await ctx.send("⚠️ You already own a company.")
            return
        
        self.c.execute("INSERT INTO companies (owner_id, name, balance) VALUES (?, ?, ?)", (owner_id, company_name, 1000))
        self.c.execute("UPDATE users SET balance = balance - 1000 WHERE user_id = ?", (owner_id,))
        self.conn.commit()
        
        await ctx.send(f"🏢 **{company_name}** has been created successfully with an initial balance of $1000!")

    @commands.command()
    async def listed_companies(self, ctx):
        """Lists all registered companies."""
        self.c.execute("SELECT name, balance, shares, is_public FROM companies")
        companies = self.c.fetchall()

        if not companies:
            await ctx.send("📜 There are currently no registered companies.")
            return

        company_list = "\n".join([
            f"🏢 **{comp[0]}** - 💰 Balance: ${comp[1]} - 📈 Shares: {comp[2]} - {'📊 Publicly Traded' if comp[3] else '🔒 Private'}"
            for comp in companies
        ])
        
        await ctx.send(f"📢 **Registered Companies:**\n{company_list}")
    
    @commands.command()
    async def make_public(self, ctx, company_name: str):
        """Allows a company to go public on the stock exchange."""
        sender_id = ctx.author.id
        
        self.c.execute("SELECT is_public FROM companies WHERE name = ? AND owner_id = ?", (company_name, sender_id))
        company = self.c.fetchone()
        
        if not company:
            await ctx.send("⚠️ You do not own this company or it does not exist.")
            return
        
        if company[0]:
            await ctx.send("⚠️ This company is already publicly listed.")
            return

        self.c.execute("UPDATE companies SET is_public = 1 WHERE name = ?", (company_name,))
        self.conn.commit()
        
        await ctx.send(f"📊 {company_name} is now publicly traded on the stock exchange!")

    @commands.command()
    async def send_company_money(self, ctx, company_name: str, recipient: str, amount: int):
        """Send money from a company to another company or user while applying tax to government balance."""
        sender_id = ctx.author.id
        
        self.c.execute("SELECT balance FROM companies WHERE name = ? AND owner_id = ?", (company_name, sender_id))
        sender_company = self.c.fetchone()
        
        if not sender_company:
            await ctx.send("⚠️ You do not own this company or it does not exist.")
            return

        if sender_company[0] < amount:
            await ctx.send("⚠️ Company has insufficient funds.")
            return

        # Fetch corporate tax rate and government balance
        self.c.execute("SELECT corporate_rate, government_balance FROM tax_rate")
        tax_row = self.c.fetchone()
        if not tax_row:
            await ctx.send("⚠️ Tax rate information is missing. Please set a tax rate first.")
            return
        corporate_tax_rate, government_balance = tax_row
        
        # Calculate tax and final amount after tax
        tax = int(amount * corporate_tax_rate)
        net_amount = amount - tax

        self.c.execute("SELECT balance FROM companies WHERE name = ?", (recipient,))
        recipient_company = self.c.fetchone()
        
        if recipient_company:
            self.c.execute("UPDATE companies SET balance = balance + ? WHERE name = ?", (net_amount, recipient))
            recipient_name = recipient
        else:
            recipient_id = int(recipient.strip("<@!>"))
            self.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (net_amount, recipient_id))
            recipient_user = self.bot.get_user(recipient_id)
            recipient_name = recipient_user.mention if recipient_user else "Unknown User"

        # Deduct funds from the sending company
        self.c.execute("UPDATE companies SET balance = balance - ? WHERE name = ?", (amount, company_name))
        
        # Add tax to government balance
        new_government_balance = government_balance + tax
        self.c.execute("UPDATE tax_rate SET government_balance = ?", (new_government_balance,))
        self.conn.commit()
        
        await ctx.send(f"💸 {company_name} sent **${net_amount}** to **{recipient_name}** after a tax of **${tax}**.\n🏛 **Government Balance Updated:** +${tax}. New total: **${new_government_balance}**")


    @commands.command()
    async def issue_shares(self, ctx, company_name: str, new_shares: int):
        """Dilutes a company's shares by increasing the total amount, only if public."""
        sender_id = ctx.author.id
        
        self.c.execute("SELECT shares, is_public FROM companies WHERE name = ? AND owner_id = ?", (company_name, sender_id))
        company = self.c.fetchone()
        
        if not company:
            await ctx.send("⚠️ You do not own this company or it does not exist.")
            return

        if not company[1]:
            await ctx.send("⚠️ This company must be publicly listed before diluting shares.")
            return

        if new_shares <= company[0]:
            await ctx.send("⚠️ New share amount must be greater than current shares.")
            return

        self.c.execute("UPDATE companies SET shares = ? WHERE name = ?", (new_shares, company_name))
        self.conn.commit()
        
        await ctx.send(f"📈 {company_name} has diluted shares to **{new_shares}** total shares!")
    
    @commands.command()
    async def appoint_board_member(self, ctx, company_name: str, member: discord.Member):
        """Appoints a board member to a company."""
        sender_id = ctx.author.id
        
        self.c.execute("SELECT board_members FROM companies WHERE name = ? AND owner_id = ?", (company_name, sender_id))
        company = self.c.fetchone()
        
        if not company:
            await ctx.send("⚠️ You do not own this company or it does not exist.")
            return

        board_members = json.loads(company[0])
        
        if member.id in board_members:
            await ctx.send("⚠️ This user is already a board member.")
            return

        board_members.append(member.id)
        self.c.execute("UPDATE companies SET board_members = ? WHERE name = ?", (json.dumps(board_members), company_name))
        self.conn.commit()
        
        await ctx.send(f"🏛️ {member.mention} has been appointed as a board member of **{company_name}**!")
        

    @commands.command()
    async def stock_price(self, ctx, company_name: str):
        """Checks a company's stock value if they are public and displays an ownership pie chart."""
        
        # Fetch company information
        self.c.execute("SELECT balance, shares, is_public FROM companies WHERE name = ?", (company_name,))
        company = self.c.fetchone()
        
        if not company:
            await ctx.send("⚠️ Company not found.")
            return
        
        balance, total_shares, is_public = company
        
        if not is_public:
            await ctx.send("⚠️ This company is private and does not have a public stock value.")
            return
        
        # Calculate stock price per share
        price_per_share = balance / total_shares if total_shares > 0 else 0
        
        # Fetch ownership data
        self.c.execute("SELECT owner_id, shares FROM ownership WHERE company_name = ?", (company_name,))
        ownership_data = self.c.fetchall()
        
        if not ownership_data:
            await ctx.send(f"🏢 **{company_name}** Stock Price: **${price_per_share:.2f}** per share.")
            return
        
        # Prepare data for pie chart
        labels = []
        sizes = []
        for owner_id, shares in ownership_data:
            user = self.bot.get_user(owner_id)
            labels.append(user.name if user else f"User {owner_id}")
            sizes.append(shares)
        
        # Create pie chart
        fig, ax = plt.subplots()
        ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
        ax.axis('equal')  # Equal aspect ratio ensures the pie chart is circular.
        
        # Save pie chart to image
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        
        # Send stock price and ownership chart
        file = discord.File(buffer, filename="stock_price.png")
        embed = discord.Embed(title=f"📈 {company_name} Stock Information", color=discord.Color.blue())
        embed.add_field(name="🏢 Stock Price", value=f"**${price_per_share:.2f}** per share", inline=False)
        embed.set_image(url="attachment://stock_price.png")
        
        await ctx.send(embed=embed, file=file)

    @commands.command()
    async def buy_shares(self, ctx, company_name: str, amount: int):
        """Allows users to buy shares in a public company, with corporate tax applied."""
        user_id = ctx.author.id
        
        self.c.execute("SELECT balance, shares, is_public FROM companies WHERE name = ?", (company_name,))
        company = self.c.fetchone()
        
        if not company:
            await ctx.send("⚠️ Company not found.")
            return
        
        balance, total_shares, is_public = company
        
        if not is_public:
            await ctx.send("⚠️ This company is private and does not sell shares.")
            return
        
        price_per_share = balance / total_shares if total_shares > 0 else 0
        total_cost = price_per_share * amount
        
        self.c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        user_balance = self.c.fetchone()
        
        if not user_balance or user_balance[0] < total_cost:
            await ctx.send("⚠️ You do not have enough funds to buy these shares.")
            return
        
        self.c.execute("SELECT corporate_rate, government_balance FROM tax_rate")
        tax_row = self.c.fetchone()
        corporate_rate, government_balance = tax_row
        tax = total_cost * corporate_rate
        
        self.c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_cost + tax, user_id))
        self.c.execute("UPDATE companies SET balance = balance + ? WHERE name = ?", (total_cost, company_name))
        self.c.execute("UPDATE tax_rate SET government_balance = government_balance + ?", (tax,))
        self.c.execute("INSERT INTO ownership (owner_id, company_name, shares) VALUES (?, ?, ?) ON CONFLICT(owner_id, company_name) DO UPDATE SET shares = shares + ?", (user_id, company_name, amount, amount))
        self.conn.commit()
        
        await ctx.send(f"✅ You have purchased {amount} shares of **{company_name}** for **${total_cost:.2f}**, paying **${tax:.2f}** in corporate tax.")

    @commands.command()
    async def sell_shares(self, ctx, company_name: str, amount: int):
        """Allows users to sell shares of a public company, with corporate tax applied."""
        user_id = ctx.author.id
        
        self.c.execute("SELECT balance, shares, is_public FROM companies WHERE name = ?", (company_name,))
        company = self.c.fetchone()
        
        if not company:
            await ctx.send("⚠️ Company not found.")
            return
        
        balance, total_shares, is_public = company
        
        if not is_public:
            await ctx.send("⚠️ This company is private and does not allow share selling.")
            return
        
        price_per_share = balance / total_shares if total_shares > 0 else 0
        total_earnings = price_per_share * amount
        
        self.c.execute("SELECT shares FROM ownership WHERE owner_id = ? AND company_name = ?", (user_id, company_name))
        user_shares = self.c.fetchone()
        
        if not user_shares or user_shares[0] < amount:
            await ctx.send("⚠️ You do not own enough shares to sell this amount.")
            return
        
        self.c.execute("SELECT corporate_rate, government_balance FROM tax_rate")
        tax_row = self.c.fetchone()
        corporate_rate, government_balance = tax_row
        tax = total_earnings * corporate_rate
        
        self.c.execute("UPDATE ownership SET shares = shares - ? WHERE owner_id = ? AND company_name = ?", (amount, user_id, company_name))
        self.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (total_earnings - tax, user_id))
        self.c.execute("UPDATE companies SET balance = balance - ? WHERE name = ?", (total_earnings, company_name))
        self.c.execute("UPDATE tax_rate SET government_balance = government_balance + ?", (tax,))
        self.conn.commit()
        
        await ctx.send(f"✅ You have sold {amount} shares of **{company_name}** for **${total_earnings:.2f}**, paying **${tax:.2f}** in corporate tax.")


async def setup(bot):
    await bot.add_cog(Companies(bot))
