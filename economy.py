import discord
import sqlite3
import random
import datetime
from discord.ext import commands
import asyncio

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect("game.db")
        self.c = self.conn.cursor()
        self.setup_economy()  # Ensure tables exist

    def setup_economy(self):
        """Create the economy-related database tables if they don’t exist."""
        self.c.execute("""
        CREATE TABLE IF NOT EXISTS tax_rate (
            trade_rate REAL DEFAULT 0.05,
            corporate_rate REAL DEFAULT 0.1,
            capital_gains_rate REAL DEFAULT 0.15,
            government_balance REAL DEFAULT 0
    )
    """)
        self.c.execute("""
        CREATE TABLE IF NOT EXISTS loans (
            issuer INTEGER,
            recipient INTEGER,
            amount REAL,
            interest REAL,
            date_issued TEXT,
            PRIMARY KEY (issuer, recipient)        
    )
            
    """)
        
        self.conn.commit()
        self.c.execute("SELECT COUNT(*) FROM tax_rate")
        row_count = self.c.fetchone()[0]

        if row_count == 0:
            print("🔹 No tax rate found, inserting default values.")
            self.c.execute("INSERT INTO tax_rate (trade_rate, corporate_rate,government_balance) VALUES (0.05, 0.1, 0)")
            self.conn.commit()
            
    @commands.command()
    @commands.has_role("RP Admin")
    async def reload_tax_table(self,ctx):
        """Reloads the tax table."""
        self.c.execute("DROP TABLE tax_rate")
        self.conn.commit()
        self.setup_economy()
        await ctx.send("Tax table reloaded.")        
            
    @commands.command(aliases=['balance', 'bal'])
    async def b(self, ctx, member: discord.Member = None):
        """Check your balance or another user's balance."""
        
        user = member if member else ctx.author  # Default to the command sender if no user is mentioned
        user_id = user.id
        # Fetch user balance
        self.c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = self.c.fetchone()
        if row:
            embed = discord.Embed(title="Balance Check", color=discord.Color.green())
            embed.add_field(name="User", value=f"{user}", inline=True)
            embed.add_field(name="Balance", value=f"**${row[0]:.2f}** 💰", inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"{user}! You need to join a district before checking your balance.")

    @commands.command(aliases=['board'])
    async def leader_board(self, ctx):
        """displays a leader board based on total value of an individual's assets"""
        self.c.execute("SELECT user_id, balance FROM users")
        rows = self.c.fetchall()
        if not rows:
            await ctx.send("⚠️ No users found.")
            return
        rows.sort(key=lambda x: x[1], reverse=True)
        embed = discord.Embed(title="Balance Leader Board", color=discord.Color.green())
        for i, row in enumerate(rows[:10], start=1):
            user = self.bot.get_user(row[0])
            if user:
                embed.add_field(name=f"{i}. {user}", value=f"${row[1]:.2f}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(aliases=['rou'])
    async def roulette(self, ctx, amount: float, color_number: str):
        """Play a game of roulette with your balance."""
        user_id = ctx.author.id
        # Fetch user balance
        self.c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = self.c.fetchone()
        if not row:
            await ctx.send("You need to join a district before playing roulette.")
            return
        balance = row[0]
        if amount <= 0:
            await ctx.send("⚠️ You must bet a positive amount of money.")
            return
        if amount > balance:
            await ctx.send("⚠️ You don't have enough balance to bet that amount.")
            return

        # Parse the color and number
        color_number = color_number.lower()
        if color_number in ["red", "black", "green"]:
            color = color_number
            number = None
        else:
            try:
                number = int(color_number)
                color = None
            except ValueError:
                await ctx.send("⚠️ You must bet on either a number or a color.")
                return

            
        # Calculate the result
        if number is not None:
            if number < 0 or number > 36:
                await ctx.send("⚠️ The number must be between 0 and 36.")
                return
            # Deduct the bet amount from the user's balance
            self.c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - amount, user_id))
            self.conn.commit()
            self.c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            row = self.c.fetchone()
            balance = row[0]
            winning_number = random.randint(0, 36)
            if winning_number == number and number != 0:
                winnings = amount * 35
                new_balance = balance + winnings
                self.c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
                self.c.execute("UPDATE tax_rate SET government_balance = government_balance - ?", (winnings,))
                self.conn.commit()
                result_message = f"🎰 The ball landed on {winning_number}. You won ${winnings}! Your new balance is ${new_balance:.2f}."
            elif winning_number == number and number == 0:
                winnings = amount * 100
                new_balance = balance + winnings
                self.c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
                self.c.execute("UPDATE tax_rate SET government_balance = government_balance - ?", (winnings,))
                self.conn.commit()
                result_message = f"🎰 The ball landed on {winning_number}. You won ${winnings}! Your new balance is ${new_balance:.2f}."
            else:
                result_message = f"🎰 The ball landed on {winning_number}. You lost ${amount}! Your new balance is ${balance:.2f}."
                self.c.execute("SELECT government_balance FROM tax_rate")
                government_balance = self.c.fetchone()[0]
                new_government_balance = government_balance + amount
                self.c.execute("UPDATE tax_rate SET government_balance = ?", (new_government_balance,))
                self.conn.commit()
        elif color is not None:
            self.c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - amount, user_id))
            self.conn.commit()
            self.c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            row = self.c.fetchone()
            balance = row[0]
            winning_color = random.choices(["red", "black", "green"], weights=[18, 18, 2], k=1)[0]
            if winning_color == color.lower() and winning_color != "green":
                winnings = amount * 2
                new_balance = balance + winnings
                self.c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
                self.c.execute("UPDATE tax_rate SET government_balance = government_balance - ?", (winnings,))
                self.conn.commit()
                result_message = f"🎰 The ball landed on {winning_color}. You won ${winnings}! Your new balance is ${new_balance:.2f}."
            elif winning_color == color.lower() and winning_color == "green":
                winnings = amount * 10
                new_balance = balance + winnings
                self.c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
                self.c.execute("UPDATE tax_rate SET government_balance = government_balance - ?", (winnings,))
                self.conn.commit()
                result_message = f"🎰 The ball landed on {winning_color}. You won ${winnings}! Your new balance is ${new_balance:.2f}."
            else:
                new_balance = balance - amount
                result_message = f"🎰 The ball landed on {winning_color}. You lost ${amount}! Your new balance is ${balance:.2f}."
                # Add the lost amount to the government balance
                self.c.execute("SELECT government_balance FROM tax_rate")
                government_balance = self.c.fetchone()[0]
                new_government_balance = government_balance + amount
                self.c.execute("UPDATE tax_rate SET government_balance = ?", (new_government_balance,))
                self.conn.commit()
        else:
            await ctx.send("⚠️ You must bet on either a number or a color.")
            return

        # Send result in an embed
        embed = discord.Embed(title="Roulette Result", color=discord.Color.green())
        embed.add_field(name="Result", value=result_message, inline=False)
        await ctx.send(embed=embed)
        
    @commands.command()
    async def slots(self, ctx, bet: float):
        """Plays a game of slots."""
        user_id = ctx.author.id
        # Fetch user balance
        self.c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = self.c.fetchone()
        if not row:
            await ctx.send("You need to join a district before playing slots.")
            return
        balance = row[0]
        if bet <= 0:
            await ctx.send("⚠️ You must bet a positive amount of money.")
            return
        if bet > balance:
            await ctx.send("⚠️ You don't have enough balance to bet that amount.")
            return

        # Deduct the bet amount from the user's balance
        self.c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance - bet, user_id))
        self.conn.commit()
        self.c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = self.c.fetchone()
        balance = row[0]

        # Slot machine logic
        emojis = ["🍒", "🍋", "🍉", "🍇", "🍓", "⭐"]
        slots = [random.choice(emojis) for _ in range(3)]
        result_message = f"🎰 {' | '.join(slots)} 🎰\n"

        if slots[0] == slots[1] == slots[2]:
            winnings = bet * 10
            new_balance = balance + winnings
            self.c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
            self.conn.commit()
            result_message += f"🎉 You won ${winnings}! Your new balance is ${new_balance:.2f}."
        elif slots[0] == slots[1] or slots[1] == slots[2] or slots[0] == slots[2]:
            winnings = bet * 2
            new_balance = balance + winnings
            self.c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
            self.conn.commit()
            result_message += f"🎉 You won ${winnings}! Your new balance is ${new_balance:.2f}."
        else:
            result_message += f"😢 You lost ${bet}. Your new balance is ${balance:.2f}."
            self.c.execute("SELECT government_balance FROM tax_rate")
            government_balance = self.c.fetchone()[0]
            new_government_balance = government_balance + bet
            self.c.execute("UPDATE tax_rate SET government_balance = ?", (new_government_balance,))
            self.conn.commit()

        # Send result in an embed
        embed = discord.Embed(title="Slots Result", color=discord.Color.green())
        embed.add_field(name="Result", value=result_message, inline=False)
        await ctx.send(embed=embed)

    @commands.command(aliases=['balgov','bg'])
    async def government_balance(self, ctx):
        """Check the government's balance."""
        self.c.execute("SELECT government_balance FROM tax_rate")
        row = self.c.fetchone()
        if row:
            embed = discord.Embed(title="Government Balance and Tax Rates", color=discord.Color.green())
            embed.add_field(name="Balance", value=f"**${row[0]:.2f}** 💰", inline=True)
            self.c.execute("SELECT trade_rate, corporate_rate, capital_gains_rate FROM tax_rate")
            rates = self.c.fetchone()
            embed.add_field(name="Trade Rate", value=f"{rates[0] * 100:.2f}%", inline=True)
            embed.add_field(name="Corporate Rate", value=f"{rates[1] * 100:.2f}%", inline=True)
            embed.add_field(name="Capital Gains Rate", value=f"{rates[2] * 100:.2f}%", inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send("No government balance found.")

    @commands.command()
    async def send(self, ctx, recipient: discord.Member, amount: float):
        """Send money between users, companies, or both, while applying tax to government balance."""
        sender_id = ctx.author.id
        recipient_id = recipient.id

        if sender_id == recipient_id:
            await ctx.send("⚠️ You can't send money to yourself.")
            return
        
        if amount <= 0:
            await ctx.send("⚠️ You must send a positive amount of money.")
            return

        # Check if sender has enough balance
        self.c.execute("SELECT balance FROM users WHERE user_id = ?", (sender_id,))
        sender_balance = self.c.fetchone()
        if not sender_balance or sender_balance[0] < amount:
            await ctx.send("⚠️ You don't have enough balance to send that amount.")
            return

        # Calculate tax
        self.c.execute("SELECT trade_rate FROM tax_rate")
        trade_rate = self.c.fetchone()[0]
        tax_amount = amount * trade_rate
        net_amount = amount - tax_amount

        # Update sender's balance
        new_sender_balance = sender_balance[0] - amount
        self.c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_sender_balance, sender_id))

        # Update recipient's balance
        self.c.execute("SELECT balance FROM users WHERE user_id = ?", (recipient_id,))
        recipient_balance = self.c.fetchone()
        if recipient_balance:
            new_recipient_balance = recipient_balance[0] + net_amount
            self.c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_recipient_balance, recipient_id))
        else:
            self.c.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (recipient_id, net_amount))

        # Update government balance
        self.c.execute("SELECT government_balance FROM tax_rate")
        government_balance = self.c.fetchone()[0]
        new_government_balance = government_balance + tax_amount
        self.c.execute("UPDATE tax_rate SET government_balance = ?", (new_government_balance,))

        self.conn.commit()

        embed = discord.Embed(title="Transaction Complete", color=discord.Color.green())
        embed.add_field(name="Sender", value=f"{ctx.author}", inline=True)
        embed.add_field(name="Recipient", value=f"{recipient}", inline=True)
        embed.add_field(name="Amount Sent", value=f"${amount}", inline=True)
        embed.add_field(name="Net Amount Received", value=f"${net_amount}", inline=True)
        embed.add_field(name="Tax Amount", value=f"${tax_amount}", inline=True)
        embed.add_field(name="Government Balance Added", value=f"${tax_amount}", inline=True)
        await ctx.send(embed=embed)

    @commands.command()
    async def loan(self, ctx, sender: discord.Member | str, receiver: discord.Member | str, amount: float, interest: float):
        scomp = False
        rcomp = False
        suser = False
        ruser = False
        today = datetime.date.today()
        
        if isinstance(sender, discord.Member):
            suser = True
            print("here user")
            sender_id = sender.id
            sender = sender_id
        if isinstance(receiver, discord.Member):
            ruser = True
            print("here user2")
            receiver_id = receiver.id
            receiver = receiver_id
        
        self.c.execute("SELECT company_id FROM companies WHERE ticker = ?", (sender,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            sender_id = ticker_result[0]
            scomp = True
        
        self.c.execute("SELECT company_id FROM companies WHERE ticker = ?", (receiver,))
        ticker_result = self.c.fetchone()
        
        if ticker_result:
            receiver_id = ticker_result[0]
            rcomp = True
        
        print(sender, receiver)
        
        if not sender_id or not receiver_id:
            await ctx.send("⚠️ Invalid sender or receiver.")
            return
        
        if amount <= 0 or interest <= 0:
            await ctx.send("⚠️ The amount and interest must be positive.")
            return
        
        channel_id = self.bot.get_channel(1343374601631043727)  # Replace with your channel ID
    
        if scomp and rcomp:
            print(1)
            # Check if the sender company has enough balance
            self.c.execute("SELECT balance FROM companies WHERE company_id = ?", (sender,))
            sender_balance = self.c.fetchone()[0]
            if sender_balance < amount:
                await ctx.send("⚠️ The sender company doesn't have enough balance to issue the loan.")
                return
            # Ask the receiver company if they want to proceed with the loan
            self.c.execute("SELECT owner_id FROM companies WHERE company_id = ?", (receiver,))
            owner_id = self.c.fetchone()[0]
            user = self.bot.get_user(owner_id)
            
            await ctx.send(f"{user.mention}, do you want to proceed with the loan? (yes/no)")

            def check(m):
                return m.author == user and m.channel == channel_id.channel and m.content.lower() in ["yes", "no"]
            
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=60.0)
            except asyncio.TimeoutError:
                embed = discord.Embed(title="⏰ Time's Up", color=discord.Color.red())
                embed.add_field(name="Loan Status", value="The loan process has been cancelled.", inline=False)
                await channel_id.send(embed=embed)
                return
            
            if msg.content.lower() == "no":
                embed = discord.Embed(title="❌ Loan Declined", color=discord.Color.red())
                embed.add_field(name="Loan Status", value="The loan has been declined.", inline=False)
                await channel_id.send(embed=embed)
                return
            # Insert the loan into the loans table
            self.c.execute("INSERT INTO loans (issuer, recipient, amount, interest, date_issued) VALUES (?, ?, ?, ?)", (sender, receiver, amount, interest, today))
            # Update the sender company's balance
            self.c.execute("UPDATE companies SET balance = balance - ? WHERE company_id = ?", (amount, sender))
            # Update the receiver company's balance
            self.c.execute("UPDATE companies SET balance = balance + ? WHERE company_id = ?", (amount, receiver))
            self.conn.commit()
            embed = discord.Embed(title="Loan Recorded", color=discord.Color.green())
            embed.add_field(name="Amount", value=f"${amount}", inline=True)
            embed.add_field(name="Interest", value=f"{interest}%", inline=True)
            embed.add_field(name="Sender", value=f"{sender}", inline=True)
            embed.add_field(name="Receiver", value=f"{receiver}", inline=True)
            await channel_id.send(embed=embed)
            
        if scomp and ruser:
            print(2)
            # Check if the sender company has enough balance
            self.c.execute("SELECT balance FROM companies WHERE company_id = ?", (sender,))
            sender_balance = self.c.fetchone()[0]
            if sender_balance < amount:
                await ctx.send("⚠️ The sender company doesn't have enough balance to issue the loan.")
                return
            # Ask the receiver user if they want to proceed with the loan
            user = self.bot.get_user(receiver)
            def check(m):
                return m.author == user and m.channel == ctx.channel and m.content.lower() in ["yes", "no"]
        
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=60.0)
            except asyncio.TimeoutError:
                embed = discord.Embed(title="⏰ Time's Up", color=discord.Color.red())
                embed.add_field(name="Loan Status", value="The loan process has been cancelled.", inline=False)
                await channel_id.send(embed=embed)
                return
        
            if msg.content.lower() == "no":
                embed = discord.Embed(title="❌ Loan Declined", color=discord.Color.red())
                embed.add_field(name="Loan Status", value="The loan has been declined.", inline=False)
                await channel_id.send(embed=embed)
                return
            
            # Insert the loan into the loans table
            self.c.execute("INSERT INTO loans (issuer, recipient, amount, interest, date_issued) VALUES (?, ?, ?, ?)", (sender, receiver, amount, interest, today))
            # Update the sender company's balance
            self.c.execute("UPDATE companies SET balance = balance - ? WHERE company_id = ?", (amount, sender))
            # Update the receiver user's balance
            self.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, receiver))
            self.conn.commit()
            embed = discord.Embed(title="Loan Recorded", color=discord.Color.green())
            embed.add_field(name="Amount", value=f"${amount}", inline=True)
            embed.add_field(name="Interest", value=f"{interest}%", inline=True)
            embed.add_field(name="Sender", value=f"{sender}", inline=True)
            embed.add_field(name="Receiver", value=f"{receiver}", inline=True)
            await channel_id.send(embed=embed)
            
        if suser and rcomp:
            print(3)
            # Check if the sender user has enough balance
            self.c.execute("SELECT balance FROM users WHERE user_id = ?", (sender,))
            sender_balance = self.c.fetchone()[0]
            if sender_balance < amount:
                await ctx.send("⚠️ The sender user doesn't have enough balance to issue the loan.")
                return
            # Ask the receiver company if they want to proceed with the loan
            self.c.execute("SELECT owner_id FROM companies WHERE company_id = ?", (receiver,))
            owner_id = self.c.fetchone()[0]
            user = self.bot.get_user(owner_id)
            await channel_id.send(f"{user.mention}, do you want to proceed with the loan? (yes/no)")

            def check(m):
                return m.author == user and m.channel == ctx.channel and m.content.lower() in ["yes", "no"]
            
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=60.0)
            except asyncio.TimeoutError:
                embed = discord.Embed(title="⏰ Time's Up", color=discord.Color.red())
                embed.add_field(name="Loan Status", value="The loan process has been cancelled.", inline=False)
                await channel_id.send(embed=embed)
                return
            
            if msg.content.lower() == "no":
                embed = discord.Embed(title="❌ Loan Declined", color=discord.Color.red())
                embed.add_field(name="Loan Status", value="The loan has been declined.", inline=False)
                await channel_id.send(embed=embed)
                return
            # Insert the loan into the loans table
            self.c.execute("INSERT INTO loans (issuer, recipient, amount, interest, date_issued) VALUES (?, ?, ?, ?)", (sender, receiver, amount, interest, today))
            # Update the sender user's balance
            self.c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, sender))
            # Update the receiver company's balance
            self.c.execute("UPDATE companies SET balance = balance + ? WHERE company_id = ?", (amount, receiver))
            self.conn.commit()
            embed = discord.Embed(title="Loan Recorded", color=discord.Color.green())
            embed.add_field(name="Amount", value=f"${amount}", inline=True)
            embed.add_field(name="Interest", value=f"{interest}%", inline=True)
            embed.add_field(name="Sender", value=f"{sender}", inline=True)
            embed.add_field(name="Receiver", value=f"{receiver}", inline=True)
            await channel_id.send(embed=embed)
            
        if suser and ruser:
            print(4)
            # Check if the sender user has enough balance
            self.c.execute("SELECT balance FROM users WHERE user_id = ?", (sender,))
            sender_balance = self.c.fetchone()[0]
            if sender_balance < amount:
                await ctx.send("⚠️ The sender user doesn't have enough balance to issue the loan.")
                return
            # Ask the receiver user if they want to proceed with the loan
            print("here")
            await channel_id.send(f"{user.mention}, do you want to proceed with the loan? (yes/no)")
            def check(m):
                return m.author == receiver and m.channel == channel_id.channel and m.content.lower() in ["yes", "no"]
        
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=60.0)
            except asyncio.TimeoutError:
                embed = discord.Embed(title="⏰ Time's Up", color=discord.Color.red())
                embed.add_field(name="Message", value="The loan process has been cancelled.", inline=False)
                await channel_id.send(embed=embed)
                return
            
            if msg.content.lower() == "no":
                embed = discord.Embed(title="❌ Private Sale Declined", color=discord.Color.red())
                embed.add_field(name="Message", value="The loan has been declined.", inline=False)
                await channel_id.send(embed=embed)
                return
            # Insert the loan into the loans table
            self.c.execute("INSERT INTO loans (issuer, recipient, amount, interest, date_issued) VALUES (?, ?, ?, ?)", (sender, receiver, amount, interest, today))
            # Update the sender user's balance
            self.c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, sender))
            # Update the receiver user's balance
            self.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, receiver))
            self.conn.commit()
            embed = discord.Embed(title="Loan Recorded", color=discord.Color.green())
            embed.add_field(name="Amount", value=f"${amount}", inline=True)
            embed.add_field(name="Interest", value=f"{interest}%", inline=True)
            embed.add_field(name="Sender", value=f"{sender}", inline=True)
            embed.add_field(name="Receiver", value=f"{receiver}", inline=True)
            await channel_id.send(embed=embed)
          
    @commands.command()
    async def pay_loan(self, ctx, issuer: str, amount: float):
        receiver = ctx.author.id
        today = datetime.date.today()
        self.c.execute("SELECT company_id FROM companies WHERE ticker = ?", (issuer,))
        ticker_result = self.c.fetchone()
        if ticker_result:
            issuer = ticker_result[0]
        
                

async def setup(bot):
    await bot.add_cog(Economy(bot))
