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
    async def balance(self, ctx, member: discord.Member = None):
        """Check your balance or another user's balance."""
        user = member if member else ctx.author  # Default to the command sender if no user is mentioned
        user_id = user.id

        # Fetch balance
        self.c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = self.c.fetchone()

        if row:
            await ctx.send(f"{user}'s balance is **${row[0]}**.")
        else:
            # Auto-register user if they don't exist
            await ctx.send(f"{user}! You need to join a district before checking your balance.")

    @commands.command()
    async def send_money(self, ctx, recipient: discord.Member, amount: int):
        """Send money between users, companies, or both, while applying tax to government balance."""
        sender_id = ctx.author.id
        recipient_id = recipient.id  # Extract recipient ID for SQL compatibility

        print(f"🔍 Transaction started by {sender_id} - Sending ${amount} to {recipient.mention}")

        # Ensure amount is positive
        if amount <= 0:
            print("❌ Error: Transaction amount must be greater than zero.")
            await ctx.send("⚠️ Transaction amount must be greater than zero.")
            return

        # Fetch tax rate and government balance
        try:
            print("📊 Fetching tax rate...")
            self.c.execute("SELECT trade_rate, corporate_rate, government_balance FROM tax_rate")
            tax_row = self.c.fetchone()
            if not tax_row:
                await ctx.send("⚠️ Tax rate information is missing. Please set a tax rate first.")
                return
            trade_rate, corporate_rate, government_balance = tax_row
            print(f"📊 Trade Rate: {trade_rate}, Corporate Rate: {corporate_rate}, Gov Balance: {government_balance}")
        except sqlite3.Error as e:
            print(f"❌ Database error while fetching tax rate: {e}")
            await ctx.send("⚠️ A database error occurred while processing the transaction.")
            return

        # Determine sender type (Person or Company)
        try:
            print("🔍 Checking if sender is a person...")
            self.c.execute("SELECT balance FROM users WHERE user_id = ?", (sender_id,))
            sender_balance = self.c.fetchone()
            print(f"👤 Sender balance: {sender_balance}")

            print("🏢 Checking if recipient is a company...")
            self.c.execute("SELECT balance FROM companies WHERE name = ?", (recipient.name,))
            company_recipient_balance = self.c.fetchone()
            print(f"🏢 Company recipient balance: {company_recipient_balance}")
        except sqlite3.Error as e:
            print(f"❌ Database error while checking sender/recipient: {e}")
            await ctx.send("⚠️ A database error occurred while identifying sender/recipient.")
            return

        is_sender_company = sender_balance is None  # If no user balance, sender must be a company
        is_recipient_company = company_recipient_balance is not None  # If company exists, recipient is a company

        print(f"🔹 Sender is a {'company' if is_sender_company else 'person'}, Recipient is a {'company' if is_recipient_company else 'person'}")

        try:
            if is_sender_company:
                # Sender is a company
                self.c.execute("SELECT balance FROM companies WHERE owner_id = ?", (sender_id,))
                sender_balance = self.c.fetchone()

                tax = int(amount * corporate_rate)
                total_amount = amount + tax

                if not sender_balance or sender_balance[0] < total_amount:
                    await ctx.send("⚠️ Company has insufficient funds.")
                    return

                self.c.execute("UPDATE companies SET balance = balance - ? WHERE owner_id = ?", (total_amount, sender_id))
            
            else:
                # Sender is a person
                tax = int(amount * trade_rate)
                total_amount = amount + tax  # Tax calculation moved here to prevent undefined variable error

                if not sender_balance or sender_balance[0] < total_amount:
                    await ctx.send("⚠️ You have insufficient funds.")
                    return

                self.c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_amount, sender_id))

            # Process recipient deposit
            if is_recipient_company:
                # Recipient is a company
                self.c.execute("UPDATE companies SET balance = balance + ? WHERE name = ?", (amount, recipient.name))
                recipient_name = recipient.name  # Keep company name for messages
            else:
                # Recipient is a person
                self.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, recipient_id))

                recipient_name = recipient.mention

            # Add tax to government balance
            new_government_balance = government_balance + tax
            self.c.execute("UPDATE tax_rate SET government_balance = ?", (new_government_balance,))

            # Commit the transaction
            self.conn.commit()
            print(f"✅ Transaction Success: ${amount} transferred to {recipient_name}, Tax ${tax} collected.")

            await ctx.send(f"💸 Transaction complete! Transferred **${amount}** (+ **${tax} tax**) to **{recipient_name}**.\n"
                        f"🏛 **Government Balance Updated:** +${tax}. New total: **${new_government_balance}**")

        except sqlite3.Error as e:
            print(f"❌ Database transaction error: {e}")
            await ctx.send("⚠️ A database error occurred while processing the transaction.")

async def setup(bot):
    await bot.add_cog(Economy(bot))
