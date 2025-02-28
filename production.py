import discord
from discord.ext import commands
import sqlite3


class Production(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def setup_production(self):
        conn = sqlite3.connect('production.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS production
                     (user_id INTEGER, production INTEGER)''')
        conn.commit()
        conn.close()