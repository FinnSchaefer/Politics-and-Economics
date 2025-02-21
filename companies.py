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
            balance REAL DEFAULT 0.0,
            shares_available INTEGER DEFAULT 100,
            total_shares INTEGER DEFAULT 100,
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
        self.conn.commit()
        
        await ctx.send(f"🏢 **{company_name}** has been created successfully with an initial balance of $1000!")

    @commands.command()
    async def companies(self, ctx):
        """Lists all registered companies and the total outstanding shares."""
        self.c.execute("SELECT name, balance, shares_available, is_public, total_shares FROM companies")
        companies = self.c.fetchall()

        if not companies:
            await ctx.send("📜 There are currently no registered companies.")
            return

        embed = discord.Embed(title="📢 Registered Companies", color=discord.Color.blue())
        
        for comp in companies:
            if comp[3]:  # If the company is public
                price_per_share = comp[1] / comp[2] if comp[2] > 0 else 0
                embed.add_field(
                    name=f"🏢 {comp[0]}",
                    value=(
                    f"💰 Balance: ${comp[1]:,.2f}\n"
                    f"📈 Price per Share: ${price_per_share:.2f}\n"
                    f"📊 Total Shares: {comp[4]}\n"
                    f"📊 Outstanding Shares: {comp[2]}\n"
                    f"📈 Publicly Traded"
                    ),
                    inline=False
                )
            else:  # If the company is private
                embed.add_field(
                    name=f"🏢 {comp[0]}",
                    value=(
                    f"💰 Balance: ${comp[1]:,.2f}\n"
                    f"📊 Total Shares: {comp[4]}\n"
                    f"🔒 Privately Owned"
                    ),
                    inline=False
                )
                
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
    async def make_public(self, ctx, company_name: str):
        """Allows a company to go public on the stock exchange and assigns all available shares to the owner."""
        sender_id = ctx.author.id
        
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
        self.conn.commit()
        
        embed = discord.Embed(title="📊 Company Publicly Listed", color=discord.Color.green())
        embed.add_field(name="Company", value=company_name, inline=False)
        embed.add_field(name="Message", value=f"{company_name} is now publicly traded on the stock exchange! All available shares have been assigned to {ctx.author.name}.", inline=False)
        await ctx.send(embed=embed)


    @commands.command(aliases=["send2c","s2c"])
    async def send_to_company(self, ctx, company: str, amount: float):
        """Send money from a user to a company."""
        sender_id = ctx.author.id

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
        price_per_share = balance / new_total_shares if new_total_shares > 0 else 0

        self.c.execute("UPDATE companies SET total_shares = ?, shares_available = shares_available + ? WHERE name = ?", (new_total_shares, new_shares, company_name))
        self.conn.commit()
        
        embed = discord.Embed(title="📈 Shares Issued", color=discord.Color.blue())
        embed.add_field(name="Company", value=company_name, inline=False)
        embed.add_field(name="New Total Shares", value=new_total_shares, inline=False)
        embed.add_field(name="New Stock Price", value=f"${price_per_share:.2f} per share", inline=False)
        await ctx.send(embed=embed)
    
    @commands.command()
    async def appoint_board_member(self, ctx, company_name: str, member: discord.Member):
        """Appoints a board member to a company."""
        sender_id = ctx.author.id
        
        self.c.execute("SELECT owner_id, board_members FROM companies WHERE name = ? AND owner_id = ?", (company_name, sender_id))
        company = self.c.fetchone()
        
        if not company:
            await ctx.send("⚠️ You do not own this company or it does not exist.")
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
                balance, total_shares = company
                price_per_share = balance / total_shares if total_shares > 0 else 0
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
        
        # Fetch company information
        self.c.execute("SELECT owner_id, balance, shares_available, total_shares, is_public, board_members FROM companies WHERE name = ?", (company_name,))
        company = self.c.fetchone()
        
        if not company:
            await ctx.send("⚠️ Company not found.")
            return
        
        owner_id, balance, shares_available, total_shares, is_public, board_members = company
        
        if not is_public:
            await ctx.send("⚠️ This company is private and does not have a public stock value.")
            return
        
        # Calculate stock price per share
        price_per_share = float(balance) / float(total_shares) if total_shares > 0 else 0.0
        
        # Fetch ownership data
        self.c.execute("SELECT owner_id, shares FROM ownership WHERE company_name = ?", (company_name,))
        ownership_data = self.c.fetchall()
        
        # Prepare data for pie chart
        labels = []
        sizes = []
        for owner_id, shares in ownership_data:
            user = self.bot.get_user(owner_id)
            labels.append(user.name if user else f"User {owner_id}")
            sizes.append(shares)
        
        # Add outstanding shares to the pie chart
        labels.append("Floating Shares")
        sizes.append(shares_available)
        
        # Create pie chart
        fig, ax = plt.subplots()
        ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
        ax.axis('equal')  # Equal aspect ratio ensures the pie chart is circular.
        
        # Save pie chart to image
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png')
        buffer.seek(0)
        
        # Fetch owner and board members
        owner = self.bot.get_user(owner_id)
        board_members = json.loads(board_members)
        board_member_names = [self.bot.get_user(member_id).name for member_id in board_members if self.bot.get_user(member_id)]
        
        # Send stock price and ownership chart
        file = discord.File(buffer, filename="stock_price.png")
        embed = discord.Embed(title=f"📈 {company_name} Stock Information", color=discord.Color.blue())
        embed.add_field(name="🏢 Owner", value=owner.name if owner else f"User {owner_id}", inline=False)
        embed.add_field(name="🏛️ Board Members", value=", ".join(board_member_names) if board_member_names else "None", inline=False)
        embed.add_field(name="💰 Stock Price", value=f"**${price_per_share:.2f}** per share", inline=False)
        embed.add_field(name="📈 Total Floating Shares", value=f"**{shares_available}**", inline=False)
        embed.set_image(url="attachment://stock_price.png")
        
        await ctx.send(embed=embed, file=file)

    @commands.command(aliases=["buyshares","bs"])
    async def buy_shares(self, ctx, company_name: str, amount: int):
        """Allows users to buy shares in a public company, with corporate tax applied."""
        user_id = ctx.author.id
        
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
            price_per_share = balance / shares_available if shares_available > 0 else 0
            total_cost += price_per_share
            balance += price_per_share
            shares_available -= 1
        
        self.c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        user_balance = self.c.fetchone()
        
        if not user_balance or user_balance[0] < total_cost:
            await ctx.send("⚠️ You do not have enough funds to buy these shares.")
            return
        
        self.c.execute("SELECT corporate_rate, government_balance FROM tax_rate")
        tax_row = self.c.fetchone()
        corporate_rate, government_balance = tax_row
        tax = total_cost * corporate_rate

        if (total_cost + total_cost * tax) > user_balance[0]:
            await ctx.send("⚠️ You do not have enough funds to pay for the shares and corporate tax.")
            return
        
        self.c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_cost + tax, user_id))
        self.c.execute("UPDATE companies SET balance = ?, shares_available = ? WHERE name = ?", (balance, shares_available, company_name))
        self.c.execute("UPDATE tax_rate SET government_balance = government_balance + ?", (tax,))
        self.c.execute("INSERT INTO ownership (owner_id, company_name, shares) VALUES (?, ?, ?) ON CONFLICT(owner_id, company_name) DO UPDATE SET shares = shares + ?", (user_id, company_name, amount, amount))
        self.conn.commit()
        
        # Check if the user now owns a majority of shares
        self.c.execute("SELECT shares FROM ownership WHERE owner_id = ? AND company_name = ?", (user_id, company_name))
        user_shares = self.c.fetchone()[0]
        
        if user_shares > total_shares / 2:
            self.c.execute("UPDATE companies SET owner_id = ? WHERE name = ?", (user_id, company_name))
            embed.add_field(name="New Owner", value=ctx.author.mention, inline=False)
        
        embed = discord.Embed(title="📈 Shares Purchased", color=discord.Color.green())
        embed.add_field(name="Company", value=company_name, inline=False)
        embed.add_field(name="Shares Purchased", value=amount, inline=False)
        embed.add_field(name="Total Cost", value=f"${total_cost:.2f}", inline=False)
        embed.add_field(name="Corporate Tax", value=f"${tax:.2f}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(aliases=["sellshares","ss"])
    async def sell_shares(self, ctx, company_name: str, amount: int):
        """Allows users to sell shares of a public company, with corporate tax applied."""
        user_id = ctx.author.id
        
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
        
        self.c.execute("SELECT corporate_rate, government_balance FROM tax_rate")
        tax_row = self.c.fetchone()
        corporate_rate, government_balance = tax_row
        
        total_earnings = 0
        for _ in range(amount):
            price_per_share = balance / total_shares if total_shares > 0 else 0
            total_earnings += price_per_share
            balance -= price_per_share
            shares_available += 1
        
        tax = total_earnings * corporate_rate
        
        self.c.execute("UPDATE ownership SET shares = shares - ? WHERE owner_id = ? AND company_name = ?", (amount, user_id, company_name))
        self.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (total_earnings - tax, user_id))
        self.c.execute("UPDATE companies SET balance = ?, shares_available = ? WHERE name = ?", (balance, shares_available, company_name))
        self.c.execute("UPDATE tax_rate SET government_balance = government_balance + ?", (tax,))
        self.conn.commit()
        
        embed = discord.Embed(title="📉 Shares Sold", color=discord.Color.red())
        embed.add_field(name="Company", value=company_name, inline=False)
        embed.add_field(name="Shares Sold", value=amount, inline=False)
        embed.add_field(name="Total Earnings", value=f"${total_earnings:.2f}", inline=False)
        embed.add_field(name="Corporate Tax", value=f"${tax:.2f}", inline=False)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Companies(bot))
