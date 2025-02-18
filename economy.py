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
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 500,
            district TEXT
        )
        """)
        self.c.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            company_id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER,
            name TEXT,
            equity INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 100,
            FOREIGN KEY (owner_id) REFERENCES users(user_id)
        )
        """)
        self.conn.commit()

    @commands.command()
    async def balance(self, ctx):
        """Check user balance."""
        user_id = ctx.author.id
        self.c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = self.c.fetchone()

        if row:
            await ctx.send(f"{ctx.author.mention}, your balance is ${row[0]}")
        else:
            self.c.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            self.conn.commit()
            await ctx.send(f"{ctx.author.mention}, your balance is $500")

    @commands.command()
    async def create_company(self, ctx, name: str):
        """Create a company with initial capital."""
        user_id = ctx.author.id
        self.c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = self.c.fetchone()

        if not balance or balance[0] < 2000:
            await ctx.send("You need at least $2000 to start a company.")
            return

        self.c.execute("INSERT INTO companies (owner_id, name, equity) VALUES (?, ?, ?)", (user_id, name, 2000))
        self.c.execute("UPDATE users SET balance = balance - 2000 WHERE user_id = ?", (user_id,))
        self.conn.commit()

        await ctx.send(f"Company `{name}` created with $2000 in equity!")

    @commands.command()
    async def send_money(self, ctx, recipient: discord.Member, amount: int):
        """Send money to another user."""
        sender_id = ctx.author.id
        recipient_id = recipient.id

        self.c.execute("SELECT balance FROM users WHERE user_id = ?", (sender_id,))
        sender_balance = self.c.fetchone()

        if not sender_balance or sender_balance[0] < amount:
            await ctx.send("Insufficient funds.")
            return

        self.c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, sender_id))
        self.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, recipient_id))
        self.conn.commit()

        await ctx.send(f"Transferred ${amount} to {recipient.mention}.")

async def setup(bot):
    await bot.add_cog(Economy(bot))
