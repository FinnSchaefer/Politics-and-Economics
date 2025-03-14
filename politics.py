import discord
import sqlite3
import json
import random
import datetime
from discord.ext import commands, tasks
from apscheduler.schedulers.asyncio import AsyncIOScheduler

OFFICIAL_DISTRICTS = [
    "Corinthia", "Vordane", "Drakenshire", "Eldoria", "Caelmont"
]

#unused districts for later expansion  "Nyxhaven", "Tarsis", "Veymar", "Ironmere", "Branholm", "Solmara", "Rexhelm", "Zephyria"

class Politics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect("game.db", check_same_thread=False)
        self.c = self.conn.cursor()
        self.setup_politics()
        self.running = 0

    def setup_politics(self):
        """Create required database tables if they don't exist."""
        self.c.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            bill_number INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_name TEXT,
            description TEXT,
            link TEXT,
            proposed_date TEXT,
            votes INTEGER DEFAULT 0,
            passed INTEGER DEFAULT 0,
            senate_number INTEGER DEFAULT 0
        )
        """)
        self.c.execute("""
        CREATE TABLE IF NOT EXISTS elections (
            voter INTEGER PRIMARY KEY DEFAULT 0,
            candidate INTEGER DEFAULT 0,
            district TEXT,
            chancellor_vote INTEGER DEFAULT 0
        )
        """)
        self.c.execute("""
        CREATE TABLE IF NOT EXISTS parties(
            party TEXT PRIMARY KEY,
            party_head INTEGER,
            description TEXT
        )
        """)
        self.conn.commit()
    
    @commands.command()
    async def join(self, ctx, district: str):
        """Allows users to join a district and ensures they have a user profile in the database."""
        user_id = ctx.author.id

        if district not in OFFICIAL_DISTRICTS or district == None:
            embed = discord.Embed(
            title="Invalid District",
            description=f"{ctx.author.mention}, '{district}' is not a valid district. Please choose from: {', '.join(OFFICIAL_DISTRICTS)}.",
            color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        self.c.execute("SELECT district FROM users WHERE user_id = ?", (user_id,))
        row = self.c.fetchone()
        
        if row:
            embed = discord.Embed(
            title="District Join",
            description=f"{ctx.author.mention}, you are already in a district ({row[0]}). If you wish to move, use the `.move` command.",
            color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Check if the district already has 7 members
        self.c.execute("SELECT COUNT(*) FROM users WHERE district = ?", (district,))
        count = self.c.fetchone()[0]
        if count >= 7:
            embed = discord.Embed(
            title="District Full",
            description=f"{ctx.author.mention}, the district of **{district}** already has 7 members and cannot accept more.",
            color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Ensure user is added to the database with a default balance
        self.c.execute("INSERT INTO users (user_id, balance, district, last_move) VALUES (?, ?, ?, ?)", (user_id, 1000, district, datetime.datetime.now().strftime("%Y-%m-%d")))
        self.conn.commit()
        print(f"✅ New user {user_id} added to the database with $1000 balance.")

        role = discord.utils.get(ctx.guild.roles, name=district)
        if role:
            await ctx.author.add_roles(role)
        
        embed = discord.Embed(
            title="District Join",
            description=f"{ctx.author.mention} has joined the district of **{district}**!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        
    @commands.command()
    async def move(self,ctx,district:str):
        user_id = ctx.author.id

        if district not in OFFICIAL_DISTRICTS or district == None:
            await ctx.send(f"{ctx.author.mention}, '{district}' is not a valid district. Please choose from: {', '.join(OFFICIAL_DISTRICTS)}.")
            return

        self.c.execute("SELECT district, last_move FROM users WHERE user_id = ?", (user_id,))
        row = self.c.fetchone()

        if not row:
            await ctx.send(f"⚠️ {ctx.author.mention}, you are not registered in any district. Use the join command first.")
            return

        current_district, last_move = row
        if current_district == district:
            embed = discord.Embed(
                title="District Move",
                description=f"{ctx.author.mention}, you are already in the district of **{district}**.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Check if the new district already has 7 members
        self.c.execute("SELECT COUNT(*) FROM users WHERE district = ?", (district,))
        count = self.c.fetchone()[0]
        if count >= 7:
            embed = discord.Embed(
            title="District Full",
            description=f"{ctx.author.mention}, the district of **{district}** already has 7 members and cannot accept more.",
            color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        if last_move:
            last_move_date = datetime.datetime.strptime(last_move, "%Y-%m-%d")
            if (datetime.datetime.now() - last_move_date).days < 14:
                embed = discord.Embed(
                    title="District Move",
                    description=f"{ctx.author.mention}, you can only move districts once every two weeks.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
            return

        self.c.execute("UPDATE users SET district = ?, last_move = ? WHERE user_id = ?", (district, datetime.datetime.now().strftime("%Y-%m-%d"), user_id))
        self.conn.commit()

        old_role = discord.utils.get(ctx.guild.roles, name=current_district)
        new_role = discord.utils.get(ctx.guild.roles, name=district)
        if old_role:
            await ctx.author.remove_roles(old_role)
        if new_role:
            await ctx.author.add_roles(new_role)
 
        embed = discord.Embed(
            title="District Move",
            description=f"{ctx.author.mention} has moved to the district of **{district}**!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        
    @commands.command(aliases=["mp"])
    async def make_party(self,ctx, party:str, description:str):
        user_id = ctx.author.id
        print("here")
        # Check if the user is already in a party
        self.c.execute("SELECT party FROM users WHERE user_id = ?", (user_id,))
        row = self.c.fetchone()

        if row and row[0]:
            embed = discord.Embed(
            title="Party Creation",
            description="You are already in a party.",
            color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Check if the party already exists
        self.c.execute("SELECT party FROM parties WHERE party = ?", (party,))
        row = self.c.fetchone()

        if row:
            embed = discord.Embed(
            title="Party Creation",
            description="A party with this name already exists.",
            color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Add the party to the parties table
        self.c.execute("INSERT INTO parties (party, party_head, description) VALUES (?, ?, ?)", (party, user_id, description))
        
        # Add the user to the users table with the new party
        self.c.execute("UPDATE users SET party = ? WHERE user_id = ?", (party, user_id))
        self.conn.commit()

        embed = discord.Embed(
            title="Party Created",
            description=f"✅ {ctx.author.mention}, the party **{party}** has been created and you have joined it!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        
    @commands.command(aliases=["jp"])
    async def join_party(self,ctx,part: str):
        user_id = ctx.author.id

        # Check if the user is already in a party
        self.c.execute("SELECT party FROM users WHERE user_id = ?", (user_id,))
        row = self.c.fetchone()
        if row and row[0]:
            embed = discord.Embed(
                title="Party Join",
                description="You are already in a party.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Check if the party exists
        self.c.execute("SELECT party FROM parties WHERE party = ?", (part,))
        row = self.c.fetchone()
        if not row:
            embed = discord.Embed(
                title="Party Join",
                description="This party does not exist.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Add the user to the party
        self.c.execute("UPDATE users SET party = ? WHERE user_id = ?", (part, user_id))
        self.conn.commit()

        embed = discord.Embed(
            title="Party Join",
            description=f"✅ {ctx.author.mention}, you have joined the party **{part}**!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)    
        
    @commands.command(aliases=["pp"])
    async def print_parties(self,ctx):
        self.c.execute("SELECT party, party_head, description FROM parties")
        rows = self.c.fetchall()
        if not rows:
            embed = discord.Embed(
            title="Parties",
            description="📜 There are currently no parties.",
            color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return

        party_list = "\n\n".join([f"**{row[0]}**\n👑 Party Head: <@{row[1]}>\n📝 Description: {row[2]}" for row in rows])
        embed = discord.Embed(
            title="📢 **Current Poltical Parties**",
            description=f"\n\n{party_list}",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
        
    @commands.command()
    async def about(self,ctx,member:discord.Member=None):
        """Displays information about the individual or someone else."""
        member = member or ctx.author
        user_id = member.id

        self.c.execute("SELECT balance, district, party, senator, chancellor FROM users WHERE user_id = ?", (user_id,))
        row = self.c.fetchone()

        if not row:
            await ctx.send("⚠️ User not found in the database.")
            return

        balance, district, party, senator_int, chancellor_int = row
        senator = district if senator_int else "No"
        chancellor = "Yes" if chancellor_int else "No"

        party_info = "None"
        if party:
            self.c.execute("SELECT party_head FROM parties WHERE party = ?", (party,))
            party_row = self.c.fetchone()
            if party_row:
                party_head = party_row[0]
            if party_head == user_id:
                party_info = f"{party} (Party Owner)"
            else:
                party_info = party

        embed = discord.Embed(
            title=f"📜 User Information: {member.name}",
            description=f"💰 **Balance:** ${balance:.2f}\n🏙️ **District:** {district}\n🎉 **Party:** {party_info}\n👑 **Senator:** {senator}\n👑 **Chancellor:** {chancellor}",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
        
    @commands.command()
    @commands.has_role("RP Admin")
    async def force_election_end(self, ctx):
        """Forces the end of still running elections. If there is no winner, the bot randomly selects one."""
        self.running = 0
        self.c.execute("SELECT district FROM users WHERE senator = 0 GROUP BY district")
        districts_without_senator = [row[0] for row in self.c.fetchall()]
        
        for district in districts_without_senator:
            self.c.execute("SELECT user_id FROM users WHERE district = ?", (district,))
            voters = [row[0] for row in self.c.fetchall()]
            if voters:
                self.c.execute("SELECT candidate, COUNT(candidate) as vote_count FROM elections WHERE district = ? GROUP BY candidate ORDER BY vote_count DESC", (district,))
                results = self.c.fetchall()
                
                if results and results[0][1] > results[1][1]:
                    winner_id = results[0][0]
                else:
                    winner_id = random.choice(voters)
                
                await self.assign_senator(ctx, winner_id, district)
                embed = discord.Embed(
                    title="Senator Election Result",
                    description=f"📢 The election for Senator of {district} has ended! Congratulations to <@{winner_id}>!",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
                
        await ctx.send("All elections have been forcefully ended.")
        
    @commands.command()
    @commands.has_role("RP Admin")
    async def force_senator(self,ctx, user: discord.Member):   
        """gets a users district and assigns them senator role"""
        user_id = user.id

        self.c.execute("SELECT district FROM users WHERE user_id = ?", (user_id,))
        row = self.c.fetchone()
        if not row:
            await ctx.send("⚠️ User not found in the database.")
            return

        district = row[0]
        await self.assign_senator(ctx, user_id, district)
        embed = discord.Embed(
            title="Senator Assigned",
            description=f"📢 {user.mention} has been assigned as Senator of {district}!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        
    @commands.command()
    @commands.has_role("RP Admin")
    async def force_district(self, ctx, user: discord.Member, district: str):
        """Forces a user to join a district."""
        user_id = user.id

        self.c.execute("SELECT district FROM users WHERE user_id = ?", (user_id,))
        row = self.c.fetchone()

        if row:
            old_district = row[0]
            self.c.execute("UPDATE users SET district = ? WHERE user_id = ?", (district, user_id))
            self.conn.commit()
            await ctx.send(f"{user.mention} has been moved from **{old_district}** to **{district}**.")
        else:
            self.c.execute("INSERT INTO users (user_id, balance, district) VALUES (?, ?, ?)", (user_id, 500, district))
            self.conn.commit()
            await ctx.send(f"{user.mention} has been added to the district of **{district}** with a starting balance of $500.")

        old_role = discord.utils.get(ctx.guild.roles, name=row[0]) if row else None
        new_role = discord.utils.get(ctx.guild.roles, name=district)
        if old_role:
            await user.remove_roles(old_role)
        if new_role:
            await user.add_roles(new_role)


    @commands.command()
    async def propose_bill(self, ctx, bill_name: str, description: str, link: str):
        """Allows senators to propose a bill from Monday to Friday."""
        proposer_id = ctx.author.id
        print(f"Proposer ID: {proposer_id}")

        if ctx.channel.id != 1341231842166050978:
            await ctx.send("⚠️ Bill proposals can only take place in #senate-chambers.")
            return

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
            embed = discord.Embed(
                title="Bill Proposal",
                description=f"{ctx.author.mention}, bills can only be proposed Monday-Friday.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        proposed_date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        self.c.execute("INSERT INTO bills (bill_name, description, link, proposed_date, votes) VALUES (?, ?, ?, ?, ?)",
                    (bill_name, description, link, proposed_date, json.dumps({})))
        self.conn.commit()

        bill_number = self.c.lastrowid
        embed = discord.Embed(
            title="Bill Proposed",
            description=f"📜 **Bill Name:** {bill_name}\n🔢 **Bill Number:** {bill_number}\n📝 **Description:** {description}\n🔗 [Google Doc]({link})",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def bills(self, ctx):
        """Displays all currently proposed bills."""
        self.c.execute("SELECT bill_number, bill_name, description, link, proposed_date FROM bills")
        bills = self.c.fetchall()

        if not bills:
            embed = discord.Embed(
                title="Proposed Bills",
                description="📜 There are currently no proposed bills.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return

        bill_list = "\n\n".join([
            f"**#{bill[0]} {bill[1]}**\n📜 {bill[2]}\n🔗 [Bill Document]({bill[3]})\n📅 Proposed: {bill[4]}"
            for bill in bills
        ])

        embed = discord.Embed(
            title="Current Proposed Bills",
            description=bill_list,
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def laws(self, ctx):
        """Displays all passed laws."""
        self.c.execute("SELECT bill_number, bill_name, description, link, proposed_date FROM bills WHERE passed = 1")
        laws = self.c.fetchall()

        if not laws:
            embed = discord.Embed(
                title="Passed Laws",
                description="📜 There are currently no passed laws.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return

        law_list = "\n\n".join([
            f"**#{law[0]} {law[1]}**\n📜 {law[2]}\n🔗 [Bill Document]({law[3]})\n📅 Passed on: {law[4]}"
            for law in laws
        ])

        embed = discord.Embed(
            title="Current Laws",
            description=f"📢 **Current Laws:**\n\n{law_list}",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_role("RP Admin")
    async def start_elections(self, ctx):
        """Starts elections for all districts, removes existing Senators, and schedules Chancellor election."""
        
        self.running = 1
        # Step 1: Remove Senator and Chancellor roles from all members
        senator_role = discord.utils.get(ctx.guild.roles, name="Senator")
        chancellor_role = discord.utils.get(ctx.guild.roles, name="Chancellor")
        ctx = self.bot.get_channel(1342194754921828465)
        senate_vote_channel = self.bot.get_channel(1343032313763725322)
        if senator_role:
            for member in senator_role.members:
                await member.remove_roles(senator_role)
        if chancellor_role:
            for member in chancellor_role.members:
                await member.remove_roles(chancellor_role)

        # Step 2: Reset senator and chancellor status in the database
        self.c.execute("UPDATE users SET senator = 0, chancellor = 0, vote_senate = 0, vote_chancellor = 0")
        self.c.execute("DELETE FROM elections")
        self.conn.commit()
        await ctx.send("All previous election data has been cleared. Starting new elections...")

        # Step 3: Start new elections
        for district in OFFICIAL_DISTRICTS:
            self.c.execute("SELECT user_id FROM users WHERE district = ?", (district,))
            voters = [row[0] for row in self.c.fetchall()]

            if not voters:
                continue

            embed = discord.Embed(
            title=f"Elections have begun in {district}!",
            description=f"Use `.vote_senator @user` to vote for your district's senator.\nYou can only vote once!",
            color=discord.Color.blue()
            )
            await ctx.send(embed=embed)

        # Step 4: Schedule Chancellor election after 24 hours
        embed = discord.Embed(
            description="📢 Chancellor election will start in 24 hours. Please elect your Senators promptly.\nWhen you are ready to vote for Chancellor please do so with `.vote_chancellor @user`.",
            color=discord.Color.red()
        )
        await senate_vote_channel.send(embed=embed)

    @commands.command()
    async def vote_chancellor(self, ctx, candidate: discord.Member):
        """Allows Senators to vote for the Chancellor."""
        if ctx.channel.id != 1343032313763725322:
            embed = discord.Embed(
                title="Chancellor Election",
                description="⚠️ Chancellor voting can only take place in the designated voting channel.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        voter_id = ctx.author.id
        elections_announcements = self.bot.get_channel(1342194754921828465)
        
        # if self.running == 0:
        #     embed = discord.Embed(
        #         title="Chancellor Election",
        #         description=f"{ctx.author.mention}, there are no elections currently running.",
        #         color=discord.Color.red()
        #     )
        #     await ctx.send(embed=embed)
        #     return

        self.c.execute("SELECT vote_chancellor FROM users WHERE user_id = ?", (voter_id,))
        row = self.c.fetchone()
        if row and row[0] != 0:
            embed = discord.Embed(
            title="Voter Fraud!",
            description=f"{ctx.author.mention}, you have already voted in this Chancellor election.",
            color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return


        self.c.execute("UPDATE users SET vote_chancellor = 1 WHERE user_id = ?", (voter_id,))
        self.conn.commit()
        self.c.execute("UPDATE elections SET chancellor_vote = ? WHERE voter = ?", (candidate.id, voter_id))
        self.conn.commit()

        embed = discord.Embed(
            title="Chancellor Vote Recorded",
            description=f"{ctx.author.mention} has voted for {candidate.mention} as Chancellor!",
            color=discord.Color.green()
        )
        await elections_announcements.send(embed=embed)

        self.c.execute("SELECT COUNT(chancellor_vote) FROM elections WHERE chancellor_vote != 0")
        total_votes = self.c.fetchone()[0]
        self.c.execute("SELECT chancellor_vote, COUNT(chancellor_vote) as vote_count FROM elections WHERE chancellor_vote != 0 GROUP BY chancellor_vote ORDER BY vote_count DESC")
        results = self.c.fetchall()

        if results and (results[0][1] > 5 / 2 or total_votes == 5):
            winner_id = results[0][0]
            chancellor_role = discord.utils.get(ctx.guild.roles, name="Chancellor")
            winner = ctx.guild.get_member(winner_id)
            if winner and chancellor_role:
                await winner.add_roles(chancellor_role)
                self.running = 0
                embed = discord.Embed(
                    title="Chancellor Election Result",
                    description=f"📢 The Chancellor election has ended! Congratulations to {winner.mention}!",
                    color=discord.Color.green()
                )
                await elections_announcements.send(embed=embed)
            else:
                await ctx.send("⚠️ Chancellor role or winner not found.")


    @commands.command()
    async def force_chancellor(self,ctx, user: discord.Member):
        """Forces a user to become the Chancellor."""
        user_id = user.id
        chancellor_role = discord.utils.get(ctx.guild.roles, name="Chancellor")
        self.c.execute("UPDATE users SET chancellor = 1 WHERE user_id = ?", (user_id,))
        self.conn.commit()
        if chancellor_role:
            await user.add_roles(chancellor_role)
            embed = discord.Embed(
                title="Chancellor Assigned",
                description=f"📢 {user.mention} has been assigned as Chancellor!",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("⚠️ Chancellor role not found.")

    @commands.command()
    async def vote_senator(self, ctx, candidate: discord.Member):
        """Allows users to vote for a senator in their district."""
        voter_id = ctx.author.id
        # Get the message author's district from the users table
        channel = self.bot.get_channel(1342194754921828465)
        self.c.execute("SELECT district FROM users WHERE user_id = ?", (voter_id,))
        row = self.c.fetchone()
        if not row:
            embed = discord.Embed(
            title="Voter Fraud!",
            description=f"{ctx.author.mention}, you are not registered in any district.",
            color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        self.c.execute("SELECT user_id FROM users WHERE district = ?", (row[0],))
        users_in_district = self.c.fetchall()
        for user in users_in_district:
            self.c.execute("SELECT senator FROM users WHERE user_id = ?", (user[0],))
            senator_row = self.c.fetchone()
            if senator_row and senator_row[0] == 1:
                embed = discord.Embed(
                title="Election Over",
                description=f"{ctx.author.mention}, the election is over as {ctx.guild.get_member(user[0]).mention} is already a Senator of {row[0]}.",
                color=discord.Color.red()
            )
                await ctx.send(embed=embed)
                return

        district = row[0]
        # Check if the voter is in the specified district
        if not any(role.name == district for role in candidate.roles):
            embed = discord.Embed(
            title="Voter Fraud!",
            description=f"{ctx.author.mention}, you can only vote in your own district.",
            color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Check if the voter has already voted
        self.c.execute("SELECT vote_senate FROM users WHERE user_id = ?", (voter_id,))
        row = self.c.fetchone()
        if row and row[0] == 1:
            self.c.execute("UPDATE elections SET candidate = ? WHERE voter = ?", (candidate.id, voter_id))
            self.conn.commit()
            embed = discord.Embed(
            title="Vote Updated",
            description=f"{ctx.author.mention}, your vote has been updated to {candidate.mention}.",
            color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            return

        # Record the vote
        self.c.execute("UPDATE users SET vote_senate = 1 WHERE user_id = ?", (voter_id,))
        self.conn.commit()
        self.c.execute("INSERT INTO elections (voter, candidate, district, chancellor_vote) VALUES (?, ?, ?, 0)", (voter_id, candidate.id, district))
        self.conn.commit()

        embed = discord.Embed(
            title="Vote Recorded",
            description=f"{ctx.author.mention} has voted for {candidate.mention} as Senator of {district}!",
            color=discord.Color.green()
        )
        await channel.send(embed=embed)

        # Check if a candidate has a majority of the votes or if everyone has voted
        self.c.execute("SELECT COUNT(*) FROM users WHERE district = ?", (district,))
        total_voters = self.c.fetchone()[0]
        self.c.execute("SELECT COUNT(voter) FROM elections WHERE district = ?", (district,))
        total_votes = self.c.fetchone()[0]
        self.c.execute("SELECT candidate, COUNT(candidate) as vote_count FROM elections WHERE district = ? GROUP BY candidate ORDER BY vote_count DESC", (district,))
        results = self.c.fetchall()

        if results and (((results[0][1] > (total_voters / 2)) or total_votes == total_voters) and (total_voters != 1 and total_votes >= 3)):
            winner_id = results[0][0]
            await self.assign_senator(ctx, winner_id, district)
            embed = discord.Embed(
            title="Senator Election Result",
            description=f"📢 The election for Senator of {district} has ended! Congratulations to {ctx.guild.get_member(winner_id).mention}!",
            color=discord.Color.green()
            )
            await channel.send(embed=embed) 

    @commands.command(aliases=["dp"])
    async def delete_party(self, ctx, party: str):
        """Deletes a party and removes all members from it."""
        user_id = ctx.author.id

        # Check if the user is the owner of the party
        self.c.execute("SELECT party_head FROM parties WHERE party = ?", (party,))
        row = self.c.fetchone()
        if not row:
            await ctx.send(f"⚠️ Party **{party}** does not exist.")
            return

        if row[0] != user_id:
            await ctx.send(f"⚠️ {ctx.author.mention}, only the party owner can delete the party.")
            return

        self.c.execute("DELETE FROM parties WHERE party = ?", (party,))
        self.c.execute("UPDATE users SET party = NULL WHERE party = ?", (party,))
        self.conn.commit()
        embed = discord.Embed(
            title="Party Deleted",
            description=f"✅ Party **{party}** has been deleted.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

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
            else:
                await ctx.send("Senator role not found in the guild.")
        else:
            await ctx.send("Member not found in the guild.")

    @commands.command()
    @commands.has_role("Chancellor")
    async def set_tax(self, ctx, corporate_rate: float, trade_rate: float):
        """Sets the corporate and trade tax rates in the database. Only the Chancellor can use this command."""
        if corporate_rate < 0 or trade_rate < 0:
            await ctx.send("⚠️ Tax rates must be non-negative values.")
            return
        
        self.c.execute("UPDATE tax_rate SET corporate_rate = ?, trade_rate = ?", (corporate_rate, trade_rate))
        self.conn.commit()
        
        embed = discord.Embed(
            title="Tax Rates Updated",
            description=f"✅ Tax rates updated!\n🏢 Corporate Tax: **{corporate_rate * 100}%**\n💼 Trade Tax: **{trade_rate * 100}%**",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    async def vote_bills(self):
        """Automatically announces voting every Sunday for all proposed bills of the current week."""
        today = datetime.datetime.now(datetime.timezone.utc)
        self.c.execute("SELECT bill_number, bill_name, description, link FROM bills WHERE proposed_date >= ?", 
                    ((today - datetime.timedelta(days=today.weekday())).strftime("%Y-%m-%d"),))
        bills = self.c.fetchall()

        if not bills:
            return  # No bills proposed this week

        bill_list = "\n".join([f"🗳️ **#{bill[0]} {bill[1]}**\n📜 {bill[2]}\n🔗 [Bill Document]({bill[3]})" for bill in bills])

        channel = self.bot.get_channel(1341231889557487739)  # Replace with actual voting channel ID
        if channel:
            embed = discord.Embed(
                title="Weekly Bill Voting",
                description=f"📢 **Senators, voting is now open for the following bills!**\n\n{bill_list}\n\n"
                            f"Use `.vote_bill [Bill Number] aye/nay, [Bill Number] aye/nay, ...` to cast your votes.",
                color=discord.Color.blue()
            )
            await channel.send(embed=embed)

    @commands.command(aliases=["lp"])
    async def leave_party(self,ctx):
        user_id = ctx.author.id

        self.c.execute("SELECT party FROM users WHERE user_id = ?", (user_id,))
        row = self.c.fetchone()
        if not row or not row[0]:
            await ctx.send("⚠️ You are not in a party.")
            return

        self.c.execute("UPDATE users SET party = NULL WHERE user_id = ?", (user_id,))
        self.conn.commit()
        embed = discord.Embed(
            title="Party Left",
            description=f"✅ You have left the party **{row[0]}**.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_role("Senator")
    async def vote_bill(self, ctx, bill_number: int, vote: str):
        """Allows Senators to vote on multiple bills at once."""
        voter_id = ctx.author.id
        if ctx.channel.id != 1343032313763725322:
            await ctx.send("⚠️ Bill voting can only take place in the designated voting channel.")
            return
        today = datetime.datetime.now(datetime.timezone.utc).weekday()
        if today != 6 or today != 0:
            embed = discord.Embed(
                title="Bill Voting",
                description="Bill voting can only take place on Sundays and Mondays.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        # Check if the voter is a Senator
        self.c.execute("SELECT senator FROM users WHERE user_id = ?", (voter_id,))
        row = self.c.fetchone()
        if not row or row[0] == 0:
            await ctx.send(f"{ctx.author.mention}, only Senators can vote on bills.")
            return

        if vote != "aye" and vote != "nay":
            await ctx.send(f"Invalid vote `{vote}`. Use 'aye' or 'nay'.")
            return

        if vote.lower() == "aye":
            self.c.execute("UPDATE bills SET votes = votes + 1 WHERE bill_number = ?", (bill_number,))
        else:
            self.c.execute("UPDATE bills SET votes = votes + 0 WHERE bill_number = ?", (bill_number,))

        self.conn.commit()
        self.c.execute("SELECT bill_name FROM bills WHERE bill_number = ?", (bill_number,))
        bill_name = self.c.fetchone()[0]
        
        embed = discord.Embed(
            title="Vote Recorded",
            description=f"✅ {ctx.author.mention}, your vote on **{bill_name} (#{bill_number})** has been recorded.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        
        # Check if the bill has a majority vote
        self.c.execute("SELECT COUNT(*) FROM users WHERE senator = 1")
        total_senators = self.c.fetchone()[0]
        self.c.execute("SELECT votes FROM bills WHERE bill_number = ?", (bill_number,))
        bill_votes = self.c.fetchone()[0]

        if bill_votes > total_senators / 2:
            self.c.execute("UPDATE bills SET passed = 1 WHERE bill_number = ?", (bill_number,))
            self.conn.commit()
            embed = discord.Embed(
            title="Bill Passed",
            description=f"📜 **{bill_name} (#{bill_number})** has been passed by the Senate and is now law!",
            color=discord.Color.green()
            )
            await ctx.send(embed=embed)

async def setup(bot):
    politics_cog = Politics(bot)
    schedy = AsyncIOScheduler()
    if not schedy.running:
        schedy.add_job(politics_cog.start_elections, "cron", day_of_week='tue', hour=13, minute=0, args=[None], week="2-52/2")  # 12pm EST (5pm UTC)
        print("🔹 Scheduled Senate elections for every other Tuesday at 12pm EST.")
        schedy.add_job(politics_cog.vote_bills, "cron", day_of_week='sun', hour=13, minute=0, week="2-52/2")  # 12pm EST (5pm UTC)
        print("🔹 Scheduled bill voting for every other Sunday at 12pm EST.")
        schedy.start()
    await bot.add_cog(politics_cog)