import discord
import sqlite3
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
    async def b(self, ctx, member: discord.Member = None):
        """Check your balance or another user's balance."""

        if member.display_name.lower() == "gov":
            # Fetch government balance
            self.c.execute("SELECT government_balance FROM tax_rate")
            row = self.c.fetchone()
            if row:
                await ctx.send(f"🏛 The government's balance is **${row[0]}**.")
            else:
                await ctx.send("⚠️ Government balance information is missing.")
        else:
            user = member if member else ctx.author  # Default to the command sender if no user is mentioned
            user_id = user.id
            # Fetch user balance
            self.c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            row = self.c.fetchone()
            if row:
                await ctx.send(f"{user}'s balance is **${row[0]}**.")
            else:
                await ctx.send(f"{user}! You need to join a district before checking your balance.")

    @commands.command()
    async def send(self, ctx, recipient: discord.Member, amount: int):
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

        await ctx.send(f"💸 {ctx.author} sent **${amount}** to {recipient}. After tax, {recipient} received **${net_amount}** and **${tax_amount}** was added to the government balance.")

async def setup(bot):
    await bot.add_cog(Economy(bot))
