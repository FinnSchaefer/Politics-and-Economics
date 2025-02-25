import discord
import sqlite3
import random
from discord.ext import commands

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
            winning_number = random.randint(0, 36)
            if winning_number == number and number != 0:
                winnings = amount * 35
                new_balance = balance + winnings
                result_message = f"🎰 The ball landed on {winning_number}. You won ${winnings}! Your new balance is ${new_balance:.2f}."
            elif winning_number == number and number == 0:
                winnings = amount * 100
                new_balance = balance + winnings
                result_message = f"🎰 The ball landed on {winning_number}. You won ${winnings}! Your new balance is ${new_balance:.2f}."
            else:
                new_balance = balance - amount
                result_message = f"🎰 The ball landed on {winning_number}. You lost ${amount}! Your new balance is ${new_balance:.2f}."
                self.c.execute("SELECT government_balance FROM tax_rate")
                government_balance = self.c.fetchone()[0]
                new_government_balance = government_balance + amount
                self.c.execute("UPDATE tax_rate SET government_balance = ?", (new_government_balance,))
                self.conn.commit()
        elif color is not None:
            winning_color = random.choices(["red", "black", "green"], weights=[18, 18, 2], k=1)[0]
            if winning_color == color.lower() and winning_color != "green":
                winnings = amount * 2
                new_balance = balance + winnings
                result_message = f"🎰 The ball landed on {winning_color}. You won ${winnings}! Your new balance is ${new_balance:.2f}."
            elif winning_color == color.lower() and winning_color == "green":
                winnings = amount * 10
                new_balance = balance + winnings
                result_message = f"🎰 The ball landed on {winning_color}. You won ${winnings}! Your new balance is ${new_balance:.2f}."
            else:
                new_balance = balance - amount
                result_message = f"🎰 The ball landed on {winning_color}. You lost ${amount}! Your new balance is ${new_balance:.2f}."
                # Add the lost amount to the government balance
                self.c.execute("SELECT government_balance FROM tax_rate")
                government_balance = self.c.fetchone()[0]
                new_government_balance = government_balance + amount
                self.c.execute("UPDATE tax_rate SET government_balance = ?", (new_government_balance,))
                self.conn.commit()
        else:
            await ctx.send("⚠️ You must bet on either a number or a color.")
            return

        # Update user balance
        self.c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        self.conn.commit()

        # Send result in an embed
        embed = discord.Embed(title="Roulette Result", color=discord.Color.green())
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

async def setup(bot):
    await bot.add_cog(Economy(bot))
