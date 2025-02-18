import discord
import sqlite3
import json
import asyncio
import datetime
from discord.ext import commands, tasks

OFFICIAL_DISTRICTS = [
    "Corinthia", "Vordane", "Drakenshire", "Eldoria", "Nyxhaven", "Tarsis",
    "Veymar", "Ironmere", "Caelmont", "Branholm", "Solmara", "Rexhelm", "Zephyria"
]

class Politics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect("game.db", check_same_thread=False)
        self.c = self.conn.cursor()
        self.setup_politics()
        self.i = 0

        # Start background tasks
        self.vote_bills.start()

    def setup_politics(self):
        """Create required database tables if they don't exist."""
        self.c.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            bill_number INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_name TEXT,
            description TEXT,
            link TEXT,
            proposed_date TEXT,
            votes TEXT,
            passed INTEGER DEFAULT 0
        )
        """)
        self.c.execute("""
        CREATE TABLE IF NOT EXISTS elections (
            district TEXT PRIMARY KEY,
            candidates TEXT,
            votes TEXT
        )
        """)
        self.conn.commit()

    @commands.command()
    async def join_district(self, ctx, district: str):
        """Allows users to join a district."""
        user_id = ctx.author.id

        if district not in OFFICIAL_DISTRICTS:
            await ctx.send(f"{ctx.author.mention}, '{district}' is not a valid district. Please choose from: {', '.join(OFFICIAL_DISTRICTS)}.")
            return

        self.c.execute("SELECT district FROM users WHERE user_id = ?", (user_id,))
        row = self.c.fetchone()
        if row:
            await ctx.send(f"{ctx.author.mention}, you are already in a district ({row[0]}). You cannot switch districts.")
            return

        self.c.execute("INSERT INTO users (user_id, district) VALUES (?, ?)", (user_id, district))
        self.conn.commit()

        role = discord.utils.get(ctx.guild.roles, name=district)
        if role:
            await ctx.author.add_roles(role)
        
        await ctx.send(f"{ctx.author.mention} has joined the district of **{district}**!")

    @commands.command()
    async def propose_bill(self, ctx, bill_name: str, description: str, link: str):
        """Allows senators to propose a bill from Monday to Friday."""
        proposer_id = ctx.author.id
        print(f"Proposer ID: {proposer_id}")

        try:
            self.conn.commit()  # Force save any uncommitted transactions
            self.c.execute("SELECT senator FROM users WHERE user_id = ?", (proposer_id,))
            row = self.c.fetchone()
            print(f"Senator Check Result: {row}")
        except sqlite3.OperationalError as e:
            print(f"Database error: {e}")
            await ctx.send("⚠️ Database is currently locked or unavailable. Try again later.")
            return

        if not row or row[0] == 0:
            await ctx.send(f"{ctx.author.mention}, only Senators can propose bills.")
            return

        today = datetime.datetime.now(datetime.timezone.utc).weekday()
        if today > 4:
            await ctx.send(f"{ctx.author.mention}, bills can only be proposed Monday-Friday.")
            return

        proposed_date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        self.c.execute("INSERT INTO bills (bill_name, description, link, proposed_date, votes) VALUES (?, ?, ?, ?, ?)",
                    (bill_name, description, link, proposed_date, json.dumps({})))
        self.conn.commit()

        bill_number = self.c.lastrowid
        await ctx.send(f"✅ **Bill Proposed!**\n📜 **Bill Name:** {bill_name}\n🔢 **Bill Number:** {bill_number}\n📝 **Description:** {description}\n🔗 [Google Doc]({link})")

    @commands.command()
    async def list_bills(self, ctx):
        """Displays all currently proposed bills."""
        self.c.execute("SELECT bill_number, bill_name, description, link, proposed_date FROM bills")
        bills = self.c.fetchall()

        if not bills:
            await ctx.send("📜 There are currently no proposed bills.")
            return

        bill_list = "\n\n".join([
            f"**#{bill[0]} {bill[1]}**\n📜 {bill[2]}\n🔗 [Bill Document]({bill[3]})\n📅 Proposed: {bill[4]}"
            for bill in bills
        ])

        await ctx.send(f"📢 **Current Proposed Bills:**\n\n{bill_list}")

    @commands.command()
    async def list_laws(self, ctx):
        """Displays all passed laws."""
        self.c.execute("SELECT bill_number, bill_name, description, link, proposed_date FROM bills WHERE passed = 1")
        laws = self.c.fetchall()

        if not laws:
            await ctx.send("📜 There are currently no passed laws.")
            return

        law_list = "\n\n".join([
            f"**#{law[0]} {law[1]}**\n📜 {law[2]}\n🔗 [Bill Document]({law[3]})\n📅 Passed on: {law[4]}"
            for law in laws
        ])

        await ctx.send(f"📢 **Current Laws:**\n\n{law_list}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def start_elections(self, ctx):
        """Starts elections for all districts, removes existing Senators, and schedules Chancellor election."""
        if self.i != 0:
            # Step 1: Remove Senator and Chancellor roles from all members
            senator_role = discord.utils.get(ctx.guild.roles, name="Senator")
            chancellor_role = discord.utils.get(ctx.guild.roles, name="Chancellor")
            if senator_role:
                for member in senator_role.members:
                    await member.remove_roles(senator_role)
            if chancellor_role:
                for member in chancellor_role.members:
                    await member.remove_roles(chancellor_role)
            await ctx.send("All previous Senators and the Chancellor have been removed.")

            # Step 2: Reset senator and chancellor status in the database
            self.c.execute("UPDATE users SET senator = 0, chancellor = 0")
            self.conn.commit()

        # Step 3: Clear election data
        self.c.execute("DELETE FROM elections")
        self.conn.commit()

        await ctx.send("@everyone All previous election data has been cleared. Starting new elections...")

        # Step 4: Start new elections
        for district in OFFICIAL_DISTRICTS:
            self.c.execute("SELECT user_id FROM users WHERE district = ?", (district,))
            voters = [row[0] for row in self.c.fetchall()]

            if not voters:
                await ctx.send(f"No voters found in {district}, skipping election.")
                continue

            self.c.execute("INSERT INTO elections (district, candidates, votes) VALUES (?, ?, ?)",
                        (district, json.dumps([]), json.dumps({})))
            self.conn.commit()

            await ctx.send(f"Election for **{district}** has begun! Use `.vote_senator {district} @user` to vote.")
            self.i += 1

        # Step 5: Schedule Chancellor election after 24 hours
        await ctx.send("<@1341232328684470293> 📢 Chancellor election will start in 24 hours. Please elect your Senators promptly.")
        await asyncio.sleep(86400)
        self.start_chancellor_election(ctx)

    async def start_chancellor_election(self, ctx):
        """Starts the Chancellor election 24 hours after Senate elections end."""
        self.c.execute("SELECT user_id FROM users WHERE senator = 1")
        senators = [row[0] for row in self.c.fetchall()]

        if not senators or len(senators) < 2:
            await ctx.send("⚠️ Not enough senators to hold a Chancellor election.")
            return

        self.c.execute("DELETE FROM elections WHERE district = 'Chancellor'")
        self.c.execute("INSERT INTO elections (district, candidates, votes) VALUES (?, ?, ?)", 
                    ('Chancellor', json.dumps(senators), json.dumps({})))
        self.conn.commit()

        channel = self.bot.get_channel(1341231889557487739)
        if channel:
            await channel.send(f"📢 **Chancellor Election Started!** Only Senators can vote.\n"
                            f"Use `.vote_chancellor @user` to cast your vote.")

    @commands.command()
    async def vote_chancellor(self, ctx, candidate: discord.Member):
        """Allows Senators to vote for the Chancellor."""
        if ctx.channel.id != 1341231889557487739:
            await ctx.send("⚠️ Chancellor voting can only take place in the designated voting channel.")
            return

        voter_id = ctx.author.id
        self.c.execute("SELECT senator FROM users WHERE user_id = ?", (voter_id,))
        row = self.c.fetchone()
        if not row or row[0] == 0:
            await ctx.send(f"{ctx.author.mention}, only Senators can vote in the Chancellor election.")
            return

        self.c.execute("SELECT votes FROM elections WHERE district = 'Chancellor'")
        row = self.c.fetchone()
        if not row:
            await ctx.send("⚠️ No Chancellor election is currently running.")
            return

        votes = json.loads(row[0])
        votes[str(voter_id)] = candidate.id
        self.c.execute("UPDATE elections SET votes = ? WHERE district = 'Chancellor'", (json.dumps(votes),))
        self.conn.commit()

        await ctx.send(f"{ctx.author.mention} has voted for {candidate.mention} as Chancellor!")


    @commands.command()
    async def vote_senator(self, ctx, district: str, candidate: discord.Member):
        """Allows users to vote for a senator in their district."""
        voter_id = ctx.author.id

        self.c.execute("SELECT district FROM users WHERE user_id = ?", (voter_id,))
        row = self.c.fetchone()
        if not row or row[0] != district:
            await ctx.send(f"{ctx.author.mention}, you can only vote in your own district.")
            return

        self.c.execute("SELECT votes FROM elections WHERE district = ?", (district,))
        row = self.c.fetchone()
        if not row:
            await ctx.send(f"No election is currently running in {district}.")
            return
        self.c.execute("SELECT user_id FROM users WHERE district = ?", (district,))
        voters = [row[0] for row in self.c.fetchall()]

        if len(voters) == 1:
            winner = voters[0]
            await self.assign_senator(ctx, winner, district)
            await ctx.send(f"{ctx.author.mention}, {candidate.mention} is the only candidate and has been automatically assigned as the Senator of {district}.")
            return
        votes = json.loads(row[0])
        votes[str(voter_id)] = candidate.id
        self.c.execute("UPDATE elections SET votes = ? WHERE district = ?", (json.dumps(votes), district))
        self.conn.commit()

        await ctx.send(f"{ctx.author.mention} has voted for {candidate.mention} in **{district}**!")

    @tasks.loop(hours=24)
    async def check_elections(self):
        """Checks elections and assigns senators based on votes."""
        self.c.execute("SELECT district, votes FROM elections")
        elections = self.c.fetchall()

        for district, votes in elections:
            votes = json.loads(votes)

            if not votes:
                continue

            vote_counts = {}
            for voter, candidate in votes.items():
                if candidate not in vote_counts:
                    vote_counts[candidate] = 0
                vote_counts[candidate] += 1

            winner = max(vote_counts, key=vote_counts.get)
            guild = self.bot.get_guild(ctx.guild.id)
            ctx = discord.utils.get(self.bot.get_all_channels(), guild__id=guild.id)
            await self.assign_senator(ctx, winner, district)

    async def assign_senator(self, ctx, user_id, district):
        """Assigns the senator role to the election winner and ensures the database schema is correct."""
        
        # Ensure the senator column exists
        try:
            self.c.execute("SELECT senator FROM users LIMIT 1;")  # Try accessing the column
        except sqlite3.OperationalError:
            # If the column doesn't exist, add it
            self.c.execute("ALTER TABLE users ADD COLUMN senator INTEGER DEFAULT 0;")
            self.conn.commit()
            print("✅ Added 'senator' column to 'users' table.")

        # Update the database to set the senator
        self.c.execute("UPDATE users SET senator = 1 WHERE user_id = ?", (user_id,))
        self.conn.commit()

        # Assign the Discord role
        member = ctx.guild.get_member(user_id)
        if member:
            senator_role = discord.utils.get(ctx.guild.roles, name="Senator")
            if senator_role:
                await member.add_roles(senator_role)
                await ctx.send(f"{member.mention} has been assigned as the Senator of {district}.")
            else:
                await ctx.send("Senator role not found in the guild.")
        else:
            await ctx.send("Member not found in the guild.")

            
    @tasks.loop(hours=24)
    async def vote_bills(self):
        """Automatically announces voting every Sunday for all proposed bills of the current week."""
        today = datetime.datetime.now(datetime.timezone.utc).weekday()
        if today.weekday() == 6:  # Sunday
            self.c.execute("SELECT bill_number, bill_name, description, link FROM bills WHERE proposed_date >= ?", 
                           ((today - datetime.timedelta(days=today.weekday())).strftime("%Y-%m-%d"),))
            bills = self.c.fetchall()

            if not bills:
                return  # No bills proposed this week

            bill_list = "\n".join([f"🗳️ **#{bill[0]} {bill[1]}**\n📜 {bill[2]}\n🔗 [Bill Document]({bill[3]})" for bill in bills])

            channel = self.bot.get_channel(1341231889557487739)  # Replace with actual voting channel ID
            if channel:
                await channel.send(f"📢 **Senators, voting is now open for the following bills!**\n\n{bill_list}\n\n"
                                   f"Use `.vote_bill [Bill Number] aye/nay, [Bill Number] aye/nay, ...` to cast your votes.")

    @commands.command()
    @commands.has_role("Senator")
    async def vote_bill(self, ctx, *, votes: str):
        """Allows Senators to vote on multiple bills at once."""
        voter_id = ctx.author.id
        if ctx.channel.id != 1341231889557487739:
            await ctx.send("⚠️ Bill voting can only take place in the designated voting channel.")
            return
        today = datetime.datetime.now(datetime.timezone.utc).weekday()
        if today != 6:
            await ctx.send("⚠️ Bill voting can only take place on Sundays.")
            return
        # Check if the voter is a Senator
        self.c.execute("SELECT senator FROM users WHERE user_id = ?", (voter_id,))
        row = self.c.fetchone()
        if not row or row[0] == 0:
            await ctx.send(f"{ctx.author.mention}, only Senators can vote on bills.")
            return

        vote_entries = votes.split(", ")
        vote_dict = {}

        # Parse vote input
        for entry in vote_entries:
            parts = entry.split(" ")
            if len(parts) != 2:
                await ctx.send(f"⚠️ Invalid format in `{entry}`. Use `.vote_bill [Bill Number] aye/nay` format.")
                return

            bill_number, vote = parts
            if vote.lower() not in ["aye", "nay"]:
                await ctx.send(f"⚠️ Invalid vote `{vote}` in `{entry}`. Use 'aye' or 'nay'.")
                return

            try:
                bill_number = int(bill_number)
            except ValueError:
                await ctx.send(f"⚠️ `{bill_number}` is not a valid bill number.")
                return

            vote_dict[bill_number] = vote.lower()

        # Process each vote
        for bill_number, vote in vote_dict.items():
            self.c.execute("SELECT votes FROM bills WHERE bill_number = ?", (bill_number,))
            row = self.c.fetchone()
            if not row:
                await ctx.send(f"⚠️ Bill #{bill_number} does not exist.")
                continue

            # Record vote
            votes = json.loads(row[0])
            votes[str(voter_id)] = vote
            self.c.execute("UPDATE bills SET votes = ? WHERE bill_number = ?", (json.dumps(votes), bill_number))
            self.conn.commit()

            # Count votes to check if the bill passes
            aye_count = sum(1 for v in votes.values() if v == "aye")
            nay_count = sum(1 for v in votes.values() if v == "nay")
            total_votes = aye_count + nay_count

            self.c.execute("SELECT COUNT(*) FROM users WHERE senator = 1")  # Count total Senators
            total_senators = self.c.fetchone()[0]

            # If more than 50% of Senators voted "aye", pass the bill
            if aye_count > (total_senators / 2):
                self.c.execute("UPDATE bills SET passed = 1 WHERE bill_number = ?", (bill_number,))
                self.conn.commit()
                await ctx.send(f"✅ **Bill #{bill_number} has passed and is now law!**")

        await ctx.send(f"✅ {ctx.author.mention}, your votes have been recorded!")


async def setup(bot):
    await bot.add_cog(Politics(bot))