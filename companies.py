import discord
import sqlite3
import json
import asyncio
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
            balance REAL DEFAULT 0.0,
            shares_available INTEGER DEFAULT 100,
            total_shares INTEGER DEFAULT 100,
            board_members TEXT DEFAULT '[]',
            is_public INTEGER DEFAULT 0,
            ticker TEXT UNIQUE
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


    @commands.command(aliases=["cc"])
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
        self.c.execute("INSERT INTO ownership (owner_id, company_name, shares) VALUES (?, ?, ?)", (owner_id, company_name, 100))
        self.c.execute("UPDATE shares_available = shares_available - 100 WHERE name = ?", (company_name,))
        self.conn.commit()
        
        await ctx.send(f"🏢 **{company_name}** has been created successfully with an initial balance of $1000!")

    @commands.command()
    async def companies(self, ctx, page: int=1):
        """Lists all registered companies and the total outstanding shares."""
        self.c.execute("SELECT name, balance, shares_available, is_public, total_shares FROM companies")
        companies = self.c.fetchall()

        if not companies:
            await ctx.send("📜 There are currently no registered companies.")
            return

        items_per_page = 5
        offset = (page - 1) * items_per_page
        emb = discord.Embed(title="📢 Registered Companies", color=discord.Color.blue())
        
        for i, comp in enumerate(companies[offset:offset + items_per_page], start=offset + 1):
            self.c.execute("SELECT owner_id, ticker FROM companies WHERE name = ?", (comp[0],))
            owner_id, ticker = self.c.fetchone()
            owner = self.bot.get_user(owner_id)
            owner_name = owner.name if owner else f"User {owner_id}"
            comp_val = await self.calc_stock_value(comp[0])
            name = comp[0]
            if ticker == None:
                ticker = ""
            else: 
                ticker = f": {ticker}"
            if comp[3]:
                # If the company is public
                if comp_val > 0:
                    price_per_share = comp_val / comp[4]
                else:
                    price_per_share = 0
                emb.add_field(
                    name=f"🏢 {comp[0]}{ticker}",
                    value=(
                    f"👤 Owner: {owner_name}\n"
                    f"💰 Value: ${comp_val:,.2f}\n"
                    f"📈 Price per Share: ${price_per_share:.2f}\n"
                    f"📊 Total Shares: {comp[4]}\n"
                    f"📊 Floating Shares: {comp[2]}\n"
                    f"📈 Publicly Traded\n"
                    ),
                    inline=False
                )
            else:  
                # If the company is private
                emb.add_field(
                    name=f"🏢 {comp[0]}{ticker}",
                    value=(
                    f"👤 Owner: {owner_name}\n"
                    f"💰 Value: ${comp_val:,.2f}\n"
                    f"📊 Privately Held Shares: {comp[4]}\n"
                    f"🔒 Privately Owned\n"
                    ),
                    inline=False
                )
        await ctx.send(embed=emb)
    
    @commands.command(aliases=["isp"])
    async def issue_private_shares(self, ctx, company_name: str, new_shares: int):
        """Issues new shares to a private company."""
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (company_name,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            company_name = ticker_result[0]
        sender_id = ctx.author.id      
        
        self.c.execute("SELECT balance, total_shares, is_public FROM companies WHERE name = ? AND owner_id = ?", (company_name, sender_id))
        company = self.c.fetchone()
        
        if not company:
            await ctx.send("⚠️ You do not own this company or it does not exist.")
            return
        
        balance, total_shares, is_public = company
        
        if is_public:
            await ctx.send("⚠️ This company must be privately held before issuing new shares.")
            return
        
        if new_shares <= 0:
            await ctx.send("⚠️ You must issue a positive amount of shares.")
            return
        
        self.c.execute("UPDATE companies SET total_shares = total_shares + ? WHERE name = ?", (new_shares, company_name))
        self.c.execute("UPDATE ownership SET shares = shares + ? WHERE owner_id = ? AND company_name = ?", (new_shares, sender_id, company_name))
        self.conn.commit()
        
        embed = discord.Embed(title="📈 Shares Issued", color=discord.Color.blue())
        embed.add_field(name="Company", value=company_name, inline=False)
        embed.add_field(name="New Shares Issued", value=new_shares, inline=False)
        await ctx.send(embed=embed)
    
    @commands.command(aliases=["ps"])
    async def private_sale(self, ctx, company: str, shares: int, price: float, user: discord.Member):
        """Proposes a private sale of shares of a company to another user."""
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (company,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            company = ticker_result[0]
        
        owner_id = ctx.author.id
        if shares <= 0:
            await ctx.send("⚠️ You must sell a positive amount of shares.")
            return

        if price <= 0:
            await ctx.send("⚠️ You must sell shares for a positive price.")
            return

        self.c.execute("SELECT name FROM companies WHERE owner_id = ? AND name = ?", (owner_id, company))
        company_data = self.c.fetchone()
        
        if not company_data:
            await ctx.send("⚠️ You do not own this company or it does not exist.")
            return
        
        self.c.execute("SELECT shares FROM ownership WHERE owner_id = ? AND company_name = ?", (owner_id, company))
        owner_shares = self.c.fetchone()
        
        if not owner_shares or owner_shares[0] < shares:
            await ctx.send(f"⚠️ You do not own enough shares to sell {shares} shares.")
            return
        self.c.execute("SELECT balance FROM users WHERE user_id = ?", (user.id,))
        user_balance = self.c.fetchone()
        
        total_price = shares * price
        if not user_balance or user_balance[0] < total_price:
            await ctx.send(f"⚠️ {user.mention} does not have enough funds to purchase these shares.")
            return
        
        await ctx.send(f"{user.mention}, {ctx.author.mention} is proposing to sell {shares} shares of **{company}** to you for ${total_price:.2f}. Type 'yes' to accept or 'no' to decline.")
        
        def check(m):
            return m.author == user and m.channel == ctx.channel and m.content.lower() in ["yes", "no"]
        
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60.0)
        except asyncio.TimeoutError:
            embed = discord.Embed(title="⏰ Time's Up", color=discord.Color.red())
            embed.add_field(name="Message", value="The private sale has been cancelled.", inline=False)
            await ctx.send(embed=embed)
            return
        
        if msg.content.lower() == "no":
            embed = discord.Embed(title="❌ Private Sale Declined", color=discord.Color.red())
            embed.add_field(name="Message", value="The private sale has been declined.", inline=False)
            await ctx.send(embed=embed)
            return
        
        self.c.execute("SELECT capital_gains_rate FROM tax_rate")
        capital_gains_rate = self.c.fetchone()[0]
        tax = (total_price * capital_gains_rate)
        user_gain = total_price - tax
        
        # Transfer shares and update balances
        self.c.execute("UPDATE ownership SET shares = shares - ? WHERE owner_id = ? AND company_name = ?", (shares, owner_id, company))
        self.c.execute("INSERT INTO ownership (owner_id, company_name, shares) VALUES (?, ?, ?) ON CONFLICT(owner_id, company_name) DO UPDATE SET shares = shares + ?", (user.id, company, shares, shares))
        self.c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_price, user.id))
        self.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (user_gain, owner_id))
        self.c.execute("UPDATE tax_rate SET government_balance = government_balance + ?", (tax,))
        self.conn.commit()
        
        embed = discord.Embed(title="✅ Private Sale Accepted", color=discord.Color.green())
        embed.add_field(name="Buyer", value=user.mention, inline=True)
        embed.add_field(name="Seller", value=ctx.author.mention, inline=True)
        embed.add_field(name="Company", value=company, inline=True)
        embed.add_field(name="Shares", value=shares, inline=True)
        embed.add_field(name="Total Price", value=f"${total_price:.2f}", inline=True)
        await ctx.send(embed=embed)
    
    @commands.command()
    @commands.has_role("RP Admin")
    async def spawn_money(self, ctx, member: discord.Member, amount: int):
        """Spawns money to a user's balance."""
        user = member.id
        self.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user))
        self.conn.commit()
        
        await ctx.send(f"✅ {amount} has been spawned to user ID {user}.")
    
    
    @commands.command()
    async def make_public(self, ctx, company_name: str, ticker: str):
        """Allows a company to go public on the stock exchange and assigns all available shares to the owner."""
        sender_id = ctx.author.id
        
        if len(ticker) > 4:
            await ctx.send("⚠️ The ticker symbol must be a maximum of 4 letters.")
            return
        
        self.c.execute("SELECT ticker FROM companies WHERE ticker = ?", (ticker,))
        existing_ticker = self.c.fetchone()
        
        if existing_ticker:
            await ctx.send("⚠️ This ticker symbol is already in use.")
            return
        
        self.c.execute("SELECT is_public, shares_available, total_shares FROM companies WHERE name = ? AND owner_id = ?", (company_name, sender_id))
        company = self.c.fetchone()
        
        if not company:
            await ctx.send("⚠️ You do not own this company or it does not exist.")
            return
        
        if company[0]:
            await ctx.send("⚠️ This company is already publicly listed.")
            return

        shares_available = company[1]
        total_shares = company[2]
        
        self.c.execute("UPDATE companies SET is_public = 1, shares_available = 0 WHERE name = ?", (company_name,))
        self.c.execute("INSERT INTO ownership (owner_id, company_name, shares) VALUES (?, ?, ?) ON CONFLICT(owner_id, company_name) DO UPDATE SET shares = shares + ?", (sender_id, company_name, shares_available, shares_available))
        self.c.execute("UPDATE companies SET ticker = ? WHERE name = ?", (ticker, company_name))
        self.conn.commit()
        
        embed = discord.Embed(title="📊 Company Publicly Listed", color=discord.Color.green())
        embed.add_field(name="Company", value=company_name, inline=False)
        embed.add_field(name="Ticker", value=ticker, inline=False)
        embed.add_field(name="Message", value=f"{company_name} is now publicly traded on the stock exchange! All available shares have been assigned to {ctx.author.name}.", inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    async def add_ticker(self, ctx, company: str, ticker: str):
        
        owner_id = ctx.author.id
        
        self.c.execute("SELECT owner_id FROM companies WHERE name = ?", (company,))
        company_owner = self.c.fetchone()
        
        if not company_owner or company_owner[0] != owner_id:
            await ctx.send("⚠️ You do not own this company.")
            return
        
        if len(ticker) > 4:
            await ctx.send("⚠️ The ticker symbol must be a maximum of 4 letters.")
            return
        
        self.c.execute("SELECT ticker FROM companies WHERE ticker = ?", (ticker,))
        existing_ticker = self.c.fetchone()
        
        if existing_ticker:
            await ctx.send("⚠️ This ticker symbol is already in use.")
            return
        
        self.c.execute("UPDATE companies SET ticker = ? WHERE name = ?", (ticker, company))
        self.conn.commit()
        
        await ctx.send(f"✅ Ticker symbol for **{company}** has been set to **{ticker}**.")
        

    @commands.command(aliases=["send2c","s2c"])
    async def send_to_company(self, ctx, company: str, amount: float):
        """Send money from a user to a company."""
        sender_id = ctx.author.id
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (company,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            company = ticker_result[0]
        # Check if the sender has enough balance
        self.c.execute("SELECT balance FROM users WHERE user_id = ?", (sender_id,))
        sender_balance = self.c.fetchone()

        if not sender_balance or sender_balance[0] < amount:
            await ctx.send("⚠️ You do not have enough funds to send this amount.")
            return

        # Update user balance
        self.c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, sender_id))
        
        # Update company balance
        self.c.execute("UPDATE companies SET balance = balance + ? WHERE name = ?", (amount, company))
        
        self.conn.commit()
        
        embed = discord.Embed(title="💸 Transfer Successful", color=discord.Color.green())
        embed.add_field(name="Sender", value=ctx.author.mention, inline=True)
        embed.add_field(name="Company", value=f"**{company}**", inline=True)
        embed.add_field(name="Amount", value=f"${amount:,.2f}", inline=True)
        await ctx.send(embed=embed)
        
    @commands.command()
    async def sendc(self, ctx, company: str, recipient: discord.Member, amount: float):
        """Send money from a company to a user while applying tax to government balance."""
        sender_id = ctx.author.id
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (company,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            company = ticker_result[0]
        # Check if the sender owns the company
        self.c.execute("SELECT balance FROM companies WHERE name = ? AND owner_id = ?", (company, sender_id))
        company_data = self.c.fetchone()

        if not company_data:
            await ctx.send("⚠️ You do not own this company or it does not exist.")
            return

        company_balance = company_data[0]

        if company_balance < amount:
            await ctx.send("⚠️ The company does not have enough funds to send this amount.")
            return

        # Update company balance
        self.c.execute("UPDATE companies SET balance = balance - ? WHERE name = ?", (amount, company))
        
        # Update recipient balance
        self.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, recipient.id))
        
        self.conn.commit()
        
        embed = discord.Embed(title="💸 Transfer Successful", color=discord.Color.green())
        embed.add_field(name="Company", value=f"**{company}**", inline=True)
        embed.add_field(name="Recipient", value=recipient.mention, inline=True)
        embed.add_field(name="Amount", value=f"${amount:,.2f}", inline=True)
        await ctx.send(embed=embed)

    @commands.command()
    async def delete_company(self, ctx, company_name: str):
        """Deletes a company and liquidates its assets."""
        sender_id = ctx.author.id
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (company_name,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            company_name = ticker_result[0]
        # Check if the sender owns the company
        self.c.execute("SELECT balance, is_public, shares_available, total_shares FROM companies WHERE name = ? AND owner_id = ?", (company_name, sender_id))
        company = self.c.fetchone()

        if not company:
            await ctx.send("⚠️ You do not own this company or it does not exist.")
            return

        balance, is_public, shares_available, total_shares = company

        if is_public:
            # Cash out all shareholders
            self.c.execute("SELECT owner_id, shares FROM ownership WHERE company_name = ?", (company_name,))
            ownerships = self.c.fetchall()

            for owner_id, shares in ownerships:
                share_value = (balance / total_shares) * shares
                self.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (share_value, owner_id))
                self.c.execute("DELETE FROM ownership WHERE owner_id = ? AND company_name = ?", (owner_id, company_name))

        else:
            # Liquidate all funds to the owner
            self.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (balance, sender_id))

        # Delete the company
        self.c.execute("DELETE FROM companies WHERE name = ?", (company_name,))
        self.conn.commit()

        embed = discord.Embed(title="🏢 Company Deleted", color=discord.Color.red())
        embed.add_field(name="Company", value=company_name, inline=False)
        embed.add_field(name="Message", value="The company has been successfully deleted and all assets have been liquidated.", inline=False)
        await ctx.send(embed=embed)

    @commands.command(aliases=["issue","is"])
    async def issue_shares(self, ctx, company_name: str, new_shares: int):
        """Dilutes a company's shares by increasing the total amount, only if public."""
        sender_id = ctx.author.id
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (company_name,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            company_name = ticker_result[0]
        
        if new_shares <= 0:
            await ctx.send("⚠️ You must issue a positive amount of shares.")
            return
        
        self.c.execute("SELECT balance, total_shares, is_public FROM companies WHERE name = ? AND owner_id = ?", (company_name, sender_id))
        company = self.c.fetchone()
        
        if not company:
            await ctx.send("⚠️ You do not own this company or it does not exist.")
            return

        balance, total_shares, is_public = company
        
        if not is_public:
            await ctx.send("⚠️ This company must be publicly listed before diluting shares.")
            return

        # Calculate the new stock value after issuing new shares
        new_total_shares = total_shares + new_shares

        self.c.execute("UPDATE companies SET total_shares = ?, shares_available = shares_available + ? WHERE name = ?", (new_total_shares, new_shares, company_name))
        self.conn.commit()
        
        value = await self.calc_stock_value(company_name)
        price_per_share = value / new_total_shares if new_total_shares > 0 else 0
        
        embed = discord.Embed(title="📈 Shares Issued", color=discord.Color.blue())
        embed.add_field(name="Company", value=company_name, inline=False)
        embed.add_field(name="New Total Shares", value=new_total_shares, inline=False)
        embed.add_field(name="New Stock Price", value=f"${price_per_share:.2f} per share", inline=False)
        await ctx.send(embed=embed)
    
    @commands.command()
    async def appoint_board_member(self, ctx, company_name: str, member: discord.Member):
        """Appoints a board member to a company."""
        sender_id = ctx.author.id
        
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (company_name,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            company_name = ticker_result[0]
        
        self.c.execute("SELECT owner_id, board_members FROM companies WHERE name = ? AND owner_id = ?", (company_name, sender_id))
        company = self.c.fetchone()
        
        if not company:
            await ctx.send("⚠️ You do not own this company or it does not exist.")
            return
        
        if member.id == sender_id:
            await ctx.send("⚠️ The owner cannot be appointed as a board member.")
            return

        owner_id, board_members = company
        board_members = json.loads(board_members)
        
        if member.id == owner_id:
            await ctx.send("⚠️ The owner cannot be appointed as a board member.")
            return
        
        if member.id in board_members:
            await ctx.send("⚠️ This user is already a board member.")
            return

        board_members.append(member.id)
        self.c.execute("UPDATE companies SET board_members = ? WHERE name = ?", (json.dumps(board_members), company_name))
        self.conn.commit()
        
        embed = discord.Embed(title="🏛️ Board Member Appointed", color=discord.Color.blue())
        embed.add_field(name="Company", value=company_name, inline=False)
        embed.add_field(name="New Board Member", value=member.mention, inline=False)
        await ctx.send(embed=embed)
        

    @commands.command(aliases=["so"])
    async def stock_ownership(self, ctx, member: discord.Member=None):
        """Shows all stocks an individual owns."""
        user = member if member else ctx.author  # Default to the command sender if no user is mentioned
        user_id = user.id
        
        self.c.execute("SELECT company_name, shares FROM ownership WHERE owner_id = ?", (user_id,))
        ownerships = self.c.fetchall()
        
        if not ownerships:
            await ctx.send("📜 You do not own any stocks.")
            return
        
        embed = discord.Embed(title="📈 Your Stock Ownership", color=discord.Color.blue())
        
        for company_name, shares in ownerships:
            self.c.execute("SELECT balance, total_shares FROM companies WHERE name = ?", (company_name,))
            company = self.c.fetchone()
            if company:
                value = await self.calc_stock_value(company_name)
                balance, total_shares = company
                price_per_share = value / total_shares if total_shares > 0 else 0
                embed.add_field(
                    name=f"🏢 {company_name}",
                    value=(
                    f"📊 Shares Owned: {shares}\n"
                    f"💰 Value per Share: ${price_per_share:.2f}\n"
                    f"💸 Total Value: ${shares * price_per_share:.2f}"
                    ),
                    inline=False
                )
        
        await ctx.send(embed=embed)

    @commands.command(aliases=["stock","sp"])
    async def stock_price(self, ctx, company_name: str):
        """Checks a company's stock value if they are public and displays an ownership pie chart."""
        # Check if the input is a ticker symbol
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (company_name,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            company_name = ticker_result[0]
            
        orig_company_name = company_name
        # Fetch company information
        self.c.execute("SELECT owner_id, balance, shares_available, total_shares, is_public, board_members, ticker FROM companies WHERE name = ?", (company_name,))
        company = self.c.fetchone()
        
        if not company:
            await ctx.send("⚠️ Company not found.")
            return
        
        owner_id, balance, shares_available, total_shares, is_public, board_members, ticker = company
        if ticker == None:
            ticker = ""
        else: 
            ticker = f": {ticker}"
        
        if not is_public:
            owner = self.bot.get_user(owner_id)
            owner_name = owner.name if owner else f"User {owner_id}"
            total_value = await self.calc_stock_value(company_name)
            embed = discord.Embed(title=f"🏢 {orig_company_name}{ticker}", color=discord.Color.blue())
            embed.add_field(name="Owner", value=owner_name, inline=False)
            embed.add_field(name="Balance", value=f"${balance:.2f}", inline=False)
            embed.add_field(name="Total Value", value=f"${total_value:.2f}", inline=False)
            embed.add_field(name="Status", value="Privately Owned", inline=False)
            await ctx.send(embed=embed)
            return
        
        value = await self.calc_stock_value(company_name)
        
        # Calculate stock price per share
        price_per_share = float(value) / float(total_shares) if total_shares > 0 else 0.0
        
        # Fetch ownership data
        self.c.execute("SELECT owner_id, shares FROM ownership WHERE company_name = ?", (company_name,))
        ownership_data = self.c.fetchall()
        
        # Prepare data for pie chart
        labels = []
        sizes = []
        for shareholder_id, shares in ownership_data:
            if shares > 0:
                user = self.bot.get_user(shareholder_id)
                self.c.execute("SELECT name FROM companies WHERE company_id = ?", (shareholder_id,))
                shareholder_company_name = self.c.fetchone()
            if shareholder_company_name:
                labels.append(shareholder_company_name[0])
            else:
                labels.append(user.name if user else f"User {shareholder_id}")
            sizes.append(shares)
        
        # Add outstanding shares to the pie chart
        if shares_available > 0:
            labels.append("Floating Shares")
            sizes.append(shares_available)
        
        # Create pie chart
        fig, ax = plt.subplots()
        wedges, texts, autotexts = ax.pie(sizes, labels=None, autopct=lambda p: f'{p:.1f}%' if p > 5 else '', startangle=90)
        ax.axis('equal')  # Equal aspect ratio ensures the pie chart is circular.

        # Improve label visibility
        for autotext in autotexts:
            autotext.set_fontsize(10)
            autotext.set_color('white')
            autotext.set_weight('bold')
        
        # Add a legend
        # Filter out shareholders with less than 5% shares for the legend
        legend_labels = [label for label, size in zip(labels, sizes) if size / sum(sizes) >= 0.05]
        legend_wedges = [wedge for wedge, size in zip(wedges, sizes) if size / sum(sizes) >= 0.05]
        
        ax.legend(legend_wedges, legend_labels, title="Top Shareholders", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))

        # Save pie chart to image
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', bbox_inches='tight')
        buffer.seek(0)
        
        # Fetch owner and board members
        owner = self.bot.get_user(owner_id)
        board_members = json.loads(board_members)
        board_member_names = [self.bot.get_user(member_id).name for member_id in board_members if self.bot.get_user(member_id)]
        
        # Send stock price and ownership chart
        file = discord.File(buffer, filename="stock_price.png")
        embed = discord.Embed(title=f"📈 {orig_company_name}{ticker}", color=discord.Color.blue())
        embed.add_field(name="🏢 Owner", value=owner.name if owner else f"User {owner_id}", inline=False)
        embed.add_field(name="🏛️ Board Members", value=", ".join(board_member_names) if board_member_names else "None", inline=False)
        embed.add_field(name="💰 Stock Price", value=f"**${price_per_share:.2f}** per share", inline=False)
        embed.add_field(name="📈 Total Floating Shares", value=f"**{shares_available}**", inline=False)
        embed.add_field(name="💵 Total Value", value=f"**${balance:.2f}**", inline=False)
        embed.set_image(url="attachment://stock_price.png")
        
        await ctx.send(embed=embed, file=file)

    async def calc_stock_value(self, company_name: str):
        """Calculates the value of a stock based on its holdings of other companies and balance and returns a float."""
        self.c.execute("SELECT balance, total_shares FROM companies WHERE name = ?", (company_name,))
        company = self.c.fetchone()
        if company:
            balance, total_shares = company
            total_stock_value = 0
            
            # Check if the company owns shares in other companies
            self.c.execute("SELECT company_name, shares FROM ownership WHERE owner_id = (SELECT company_id FROM companies WHERE name = ?)", (company_name,))
            owned_stocks = self.c.fetchall()
            
            # Add the value of resources owned by the company to the total stock value
            try:
                self.c.execute("SELECT resource, stockpile FROM company_resources WHERE comp_id = (SELECT company_id FROM companies WHERE name = ?)", (company_name,))
                resources = self.c.fetchall()
                
                for resource, stockpile in resources:
                    self.c.execute("SELECT price_per_unit FROM resources WHERE resource = ?", (resource,))
                    resource_value = self.c.fetchone()
                    if resource_value:
                        total_stock_value += stockpile * resource_value[0]
            except sqlite3.OperationalError:
                pass  # Table does not exist, skip this part
            
            for owned_company_name, shares in owned_stocks:
                self.c.execute("SELECT balance, total_shares FROM companies WHERE name = ?", (owned_company_name,))
                owned_company = self.c.fetchone()
                if owned_company:
                    owned_balance, owned_total_shares = owned_company
                    owned_price_per_share = owned_balance / owned_total_shares if owned_total_shares > 0 else 0
                    total_stock_value += shares * owned_price_per_share
            
            return balance + total_stock_value
        return 0
        
    @commands.command(aliases=["cbs"])
    async def company_buy_shares(self, ctx, purchaser_company: str, stock: str, amount: int):
        """Allows companies to buy shares in another company."""
        new_owner = False
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (purchaser_company,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            purchaser_company = ticker_result[0]
            
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (stock,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            stock = ticker_result[0]
    
        if(amount <= 0):
            await ctx.send("⚠️ You must buy a positive amount of shares.")
            return
        
        self.c.execute("SELECT company_id FROM companies WHERE name = ?", (purchaser_company,))
        purchaser_id = self.c.fetchone()[0]
        if not purchaser_id:
            await ctx.send("⚠️ Purchaser company not found.")
            return
        
        self.c.execute("SELECT owner_id FROM companies WHERE name = ?", (purchaser_company,))
        owner_id = self.c.fetchone()
        
        if not owner_id or owner_id[0] != ctx.author.id:
            await ctx.send("⚠️ You do not own this company.")
            return
        
        
        self.c.execute("SELECT balance, total_shares, is_public FROM companies WHERE name = ?", (stock,))
        company = self.c.fetchone()
        
        
        if not company:
            await ctx.send("⚠️ Company not found.")
            return
        
        balance, total_shares, is_public = company
        
        if not is_public:
            await ctx.send("⚠️ This company is private and does not sell shares.")
            return
        
        self.c.execute("SELECT balance FROM companies WHERE name = ?", (purchaser_company,))
        purchaser_balance = self.c.fetchone()
        
        value = await self.calc_stock_value(stock)
        
        price_per_share = value / total_shares if total_shares > 0 else 0
        total_cost = price_per_share * amount
        
        if purchaser_balance[0] < total_cost:
            await ctx.send("⚠️ The purchaser company does not have enough funds to buy this amount of shares.")
            return
        
        value = await self.calc_stock_value(stock)
        
        price_per_share = value / total_shares if total_shares > 0 else 0
        
        self.c.execute("UPDATE companies SET balance = balance - ? WHERE name = ?", (price_per_share, purchaser_company))
        self.c.execute("UPDATE companies SET balance = balance + ? WHERE name = ?", (price_per_share, stock))
        self.c.execute("UPDATE companies SET shares_available = shares_available - ? WHERE name = ?", (amount, stock))
        self.c.execute("INSERT INTO ownership (owner_id, company_name, shares) VALUES (?, ?, ?) ON CONFLICT(owner_id, company_name) DO UPDATE SET shares = shares + ?", (purchaser_id, stock, amount, amount))
        self.conn.commit()
        self.c.execute("SELECT owner_id, shares FROM ownership WHERE company_name = ? ORDER BY shares DESC LIMIT 1", (stock,))
        largest_shareholder = self.c.fetchone()
        if largest_shareholder and largest_shareholder[0] == purchaser_id:
            self.c.execute("UPDATE companies SET owner_id = ? WHERE name = ?", (purchaser_id, stock))
            self.conn.commit()
            new_owner = True
        
        price_per_share = value / total_shares if total_shares > 0 else 0
        
        embed = discord.Embed(title="📈 Shares Purchased", color=discord.Color.green())
        embed.add_field(name="Company", value=stock, inline=False)
        embed.add_field(name="Purchaser", value=purchaser_company, inline=False)
        embed.add_field(name="Price per Share", value=f"${price_per_share:.2f}", inline=False)
        if new_owner:
            embed.add_field(name="New Owner", value=purchaser_company, inline=False)
        await ctx.send(embed=embed)

    @commands.command(aliases=["css"])
    async def company_sell_shares(self, ctx, seller_company: str, stock: str, amount: int):
        """Allows companies to sell shares in another company."""
        new_owner = False
        
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (seller_company,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            seller_company = ticker_result[0]
            
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (stock,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            stock = ticker_result[0]
        
        if(amount <= 0):
            await ctx.send("⚠️ You must sell a positive amount of shares.")
            return
        
        self.c.execute("SELECT balance, shares_available, total_shares, is_public FROM companies WHERE name = ?", (stock,))
        company = self.c.fetchone()
        
        if not company:
            await ctx.send("⚠️ Company not found.")
            return
        
        balance, shares_available, total_shares, is_public = company
        
        if not is_public:
            await ctx.send("⚠️ This company is private and does not allow share selling.")
            return
        
        self.c.execute("SELECT balance FROM companies WHERE name = ?", (seller_company,))
        seller_balance = self.c.fetchone()
        
        if not seller_balance:
            await ctx.send("⚠️ Seller company not found.")
            return
        
        self.c.execute("SELECT shares FROM ownership WHERE owner_id = (SELECT company_id FROM companies WHERE name = ?) AND company_name = ?", (seller_company, stock))
        seller_shares = self.c.fetchone()
        
        if not seller_shares or seller_shares[0] < amount:
            await ctx.send("⚠️ The seller company does not own enough shares to sell this amount.")
            return
        
        self.c.execute("SELECT capital_gains_rate FROM tax_rate")
        capital_gains_rate = self.c.fetchone()[0]
        
        value = await self.calc_stock_value(stock)
        
        price_per_share = value / total_shares if total_shares > 0 else 0
        tax = (price_per_share * amount) * capital_gains_rate
        total_earnings = (price_per_share * amount) - tax
        
        if seller_balance[0] < total_earnings:
            await ctx.send("⚠️ The seller company does not have enough funds to sell shares.")
            return
        
        self.c.execute("UPDATE companies SET balance = balance - ? WHERE name = ?", (total_earnings, stock))
        self.c.execute("UPDATE companies SET balance = balance + ? WHERE name = ?", (total_earnings, seller_company))
        self.c.execute("UPDATE tax_rate SET government_balance = government_balance + ?", (tax,))
        self.c.execute("UPDATE companies SET shares_available = shares_available + ? WHERE name = ?", (amount, stock))
        self.c.execute("UPDATE ownership SET shares = shares - ? WHERE owner_id = (SELECT company_id FROM companies WHERE name = ?) AND company_name = ?", (amount, seller_company, stock))
        self.c.execute("DELETE FROM ownership WHERE owner_id = (SELECT company_id FROM companies WHERE name = ?) AND company_name = ? AND shares = 0", (seller_company, stock))
        self.conn.commit()
        
        self.c.execute("SELECT owner_id, shares FROM ownership WHERE company_name = ? ORDER BY shares DESC LIMIT 1", (stock,))
        largest_shareholder = self.c.fetchone()
        if largest_shareholder and largest_shareholder[0] != ctx.author.id:
            self.c.execute("UPDATE companies SET owner_id = ? WHERE name = ?", (largest_shareholder[0], stock))
            self.conn.commit()
            new_owner = self.bot.get_user(largest_shareholder[0])
        
        embed = discord.Embed(title="📉 Shares Sold", color=discord.Color.red())
        embed.add_field(name="Company", value=stock, inline=False)
        embed.add_field(name="Seller", value=seller_company, inline=False)
        embed.add_field(name="Shares Sold", value=amount, inline=False)
        embed.add_field(name="Total Earnings", value=f"${total_earnings:.2f}", inline=False)
        embed.add_field(name="Capital Gains Tax", value=f"${tax:.2f}", inline=False)
        if new_owner:
            embed.add_field(name="New Owner", value=new_owner.mention, inline=False)
        await ctx.send(embed=embed)
        
    @commands.command(aliases=["co"])
    async def company_ownership(self, ctx, company_name: str):
        """Shows all shares that a company owns"""
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (company_name,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            company_name = ticker_result[0]
        
        self.c.execute("SELECT company_id FROM companies WHERE name = ?", (company_name,))
        company_id = self.c.fetchone()
        
        if not company_id:
            await ctx.send("⚠️ Company not found.")
            return
        
        self.c.execute("SELECT company_name, shares FROM ownership WHERE owner_id = ?", (company_id[0],))
        ownerships = self.c.fetchall()
        
        if not ownerships:
            await ctx.send("📜 No ownership data found for this company.")
            return
        
        embed = discord.Embed(title=f"📈 {company_name} Stock Ownership", color=discord.Color.blue())
        
        for owned_company_name, shares in ownerships:
            self.c.execute("SELECT balance, total_shares FROM companies WHERE name = ?", (owned_company_name,))
            company = self.c.fetchone()
            if company:
                value = await self.calc_stock_value(owned_company_name)
                balance, total_shares = company
                price_per_share = value / total_shares if total_shares > 0 else 0
                embed.add_field(
                    name=f"🏢 {owned_company_name}",
                    value=(
                    f"📊 Shares Owned: {shares}\n"
                    f"💰 Value per Share: ${price_per_share:.2f}\n"
                    f"💸 Total Value: ${shares * price_per_share:.2f}"
                    ),
                    inline=False
                )
        await ctx.send(embed=embed)

    @commands.command(aliases=["buyshares","bs"])
    async def buy_shares(self, ctx, company_name: str, amount: int):
        """Allows users to buy shares in a public company, with corporate tax applied."""
        user_id = ctx.author.id
        new_owner = False

        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (company_name,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            company_name = ticker_result[0]
            
        self.c.execute("SELECT balance, shares_available, total_shares, is_public FROM companies WHERE name = ?", (company_name,))
        company = self.c.fetchone()
        
        if not company:
            await ctx.send("⚠️ Company not found.")
            return
        
        balance, shares_available, total_shares, is_public = company
        
        if not is_public:
            await ctx.send("⚠️ This company is private and does not sell shares.")
            return
        
        if(amount <= 0):
            await ctx.send("⚠️ You must buy a positive amount of shares.")
            return
        
        if(amount > shares_available):
            await ctx.send("⚠️ There are not enough shares available to buy this amount.")
            return
        
        total_cost = 0
        for _ in range(amount):
            value = await self.calc_stock_value(company_name)
            price_per_share = value / total_shares if total_shares > 0 else 0
            total_cost += price_per_share
            balance += price_per_share
            shares_available -= 1
        
        self.c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        user_balance = self.c.fetchone()

        if (total_cost) > user_balance[0]:
            await ctx.send("⚠️ You do not have enough funds to pay for the shares")
            return
        
        
        self.c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_cost, user_id))
        self.c.execute("UPDATE companies SET balance = ?, shares_available = ? WHERE name = ?", (balance, shares_available, company_name))
        self.c.execute("INSERT INTO ownership (owner_id, company_name, shares) VALUES (?, ?, ?) ON CONFLICT(owner_id, company_name) DO UPDATE SET shares = shares + ?", (user_id, company_name, amount, amount))
        self.conn.commit()
        
        self.c.execute("SELECT owner_id, shares FROM ownership WHERE company_name = ? ORDER BY shares DESC LIMIT 1", (company_name,))
        largest_shareholder = self.c.fetchone()
        if largest_shareholder and largest_shareholder[0] == user_id:
            self.c.execute("UPDATE companies SET owner_id = ? WHERE name = ?", (user_id, company_name))
            new_owner = True
            self.conn.commit()
        
        
        embed = discord.Embed(title="📈 Shares Purchased", color=discord.Color.green())
        embed.add_field(name="Company", value=company_name, inline=False)
        embed.add_field(name="Shares Purchased", value=amount, inline=False)
        embed.add_field(name="Total Cost", value=f"${total_cost:.2f}", inline=False)
        if new_owner:
            embed.add_field(name="New Owner", value=ctx.author.mention, inline=False)
            
        await ctx.send(embed=embed)



    @commands.command(aliases=["sellshares","ss"])
    async def sell_shares(self, ctx, company_name: str, amount: int):
        """Allows users to sell shares of a public company, with corporate tax applied."""
        user_id = ctx.author.id
        new_owner = False
        
        self.c.execute("SELECT name FROM companies WHERE ticker = ?", (company_name,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            company_name = ticker_result[0]
        
        self.c.execute("SELECT balance, shares_available, total_shares, is_public FROM companies WHERE name = ?", (company_name,))
        company = self.c.fetchone()
        
        if not company:
            await ctx.send("⚠️ Company not found.")
            return
        
        balance, shares_available, total_shares, is_public = company
        
        if not is_public:
            await ctx.send("⚠️ This company is private and does not allow share selling.")
            return
        
        if(amount <= 0):
            await ctx.send("⚠️ You must sell a positive amount of shares.")
            return
        
        if(amount > total_shares):
            await ctx.send("⚠️ You cannot sell more shares than the total floating shares.")
            return
        
        self.c.execute("SELECT shares FROM ownership WHERE owner_id = ? AND company_name = ?", (user_id, company_name))
        user_shares = self.c.fetchone()
        
        if not user_shares or user_shares[0] < amount:
            await ctx.send("⚠️ You do not own enough shares to sell this amount.")
            return
        
        self.c.execute("SELECT capital_gains_rate FROM tax_rate")
        capital_gains_rate = self.c.fetchone()[0]
        
        total_earnings = 0
        for _ in range(amount):
            value = await self.calc_stock_value(company_name)
            price_per_share = value / total_shares if total_shares > 0 else 0
            total_earnings += price_per_share
            balance -= price_per_share
            shares_available += 1
        
        tax = total_earnings * capital_gains_rate
        
        self.c.execute("UPDATE ownership SET shares = shares - ? WHERE owner_id = ? AND company_name = ?", (amount, user_id, company_name))
        self.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (total_earnings - tax, user_id))
        self.c.execute("UPDATE companies SET balance = ?, shares_available = ? WHERE name = ?", (balance, shares_available, company_name))
        self.c.execute("UPDATE tax_rate SET government_balance = government_balance + ?", (tax,))
        self.c.execute("DELETE FROM ownership WHERE (owner_id = ? AND company_name = ?) AND shares = 0", (user_id, company_name))
        self.conn.commit()
        
        self.c.execute("SELECT owner_id, shares FROM ownership WHERE company_name = ? ORDER BY shares DESC LIMIT 1", (company_name,))
        largest_shareholder = self.c.fetchone()
        if largest_shareholder and largest_shareholder[0] != user_id:
            self.c.execute("UPDATE companies SET owner_id = ? WHERE name = ?", (largest_shareholder[0], company_name))
            self.conn.commit()
            new_owner = self.bot.get_user(largest_shareholder[0])
            
        
        embed = discord.Embed(title="📉 Shares Sold", color=discord.Color.red())
        embed.add_field(name="Company", value=company_name, inline=False)
        embed.add_field(name="Shares Sold", value=amount, inline=False)
        embed.add_field(name="Total Earnings", value=f"${total_earnings:.2f}", inline=False)
        embed.add_field(name="Capital Gains Tax", value=f"${tax:.2f}", inline=False)
        if new_owner:
            embed.add_field(name="New Owner", value=new_owner.mention, inline=False)
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Companies(bot))
