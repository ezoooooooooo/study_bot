import discord
from discord.ext import commands, tasks
import datetime
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Data storage
DATA_FILE = 'study_data.json'
study_sessions = {}
pomodoro_sessions = {}

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

user_stats = load_data()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    weekly_reset.start()

@bot.command(name='start')
async def start_session(ctx):
    """Start a study session"""
    user_id = str(ctx.author.id)
    
    if user_id in study_sessions:
        await ctx.send("❌ You already have an active study session!")
        return
    
    study_sessions[user_id] = {
        'start_time': datetime.datetime.now().isoformat(),
        'channel': ctx.channel.id,
        'user_name': ctx.author.display_name
    }
    
    embed = discord.Embed(
        title="📚 Study Session Started",
        description=f"{ctx.author.mention} started studying at {datetime.datetime.now().strftime('%H:%M:%S')}",
        color=0x00ff00
    )
    await ctx.send(embed=embed)

@bot.command(name='end')
async def end_session(ctx):
    """End a study session"""
    user_id = str(ctx.author.id)
    
    if user_id not in study_sessions:
        await ctx.send("❌ No active study session found!")
        return
    
    session = study_sessions[user_id]
    start_time = datetime.datetime.fromisoformat(session['start_time'])
    end_time = datetime.datetime.now()
    duration = end_time - start_time
    hours = duration.total_seconds() / 3600
    
    # Initialize user stats if needed
    if user_id not in user_stats:
        user_stats[user_id] = {
            'daily': 0,
            'weekly': 0,
            'total': 0,
            'last_reset': datetime.date.today().isoformat(),
            'name': ctx.author.display_name
        }
    
    # Check if it's a new day
    today = datetime.date.today().isoformat()
    if user_stats[user_id].get('last_reset') != today:
        user_stats[user_id]['daily'] = 0
        user_stats[user_id]['last_reset'] = today
    
    # Update stats
    user_stats[user_id]['daily'] += hours
    user_stats[user_id]['weekly'] += hours
    user_stats[user_id]['total'] += hours
    user_stats[user_id]['name'] = ctx.author.display_name
    
    save_data(user_stats)
    del study_sessions[user_id]
    
    embed = discord.Embed(
        title="✅ Study Session Completed",
        description=f"Great work, {ctx.author.mention}!",
        color=0x0099ff
    )
    embed.add_field(name="Duration", value=f"{int(hours)}h {int((hours % 1) * 60)}m", inline=True)
    embed.add_field(name="Today's Total", value=f"{user_stats[user_id]['daily']:.1f}h", inline=True)
    embed.add_field(name="Weekly Total", value=f"{user_stats[user_id]['weekly']:.1f}h", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='stats')
async def show_stats(ctx, member: discord.Member = None):
    """Show study statistics"""
    if member is None:
        member = ctx.author
    
    user_id = str(member.id)
    
    if user_id not in user_stats:
        await ctx.send(f"❌ No study data found for {member.display_name}!")
        return
    
    stats = user_stats[user_id]
    
    embed = discord.Embed(
        title=f"📊 Study Stats for {member.display_name}",
        color=0xff9900
    )
    embed.add_field(name="Today", value=f"{stats['daily']:.1f} hours", inline=True)
    embed.add_field(name="This Week", value=f"{stats['weekly']:.1f} hours", inline=True)
    embed.add_field(name="All Time", value=f"{stats['total']:.1f} hours", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='leaderboard')
async def leaderboard(ctx):
    """Show weekly leaderboard"""
    if not user_stats:
        await ctx.send("❌ No study data available!")
        return
    
    # Sort users by weekly hours
    sorted_users = sorted(user_stats.items(), key=lambda x: x[1]['weekly'], reverse=True)
    
    embed = discord.Embed(
        title="🏆 Weekly Study Leaderboard",
        color=0xffd700
    )
    
    for i, (user_id, stats) in enumerate(sorted_users[:10]):
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
        embed.add_field(
            name=f"{medal} {stats.get('name', 'Unknown User')}",
            value=f"{stats['weekly']:.1f} hours",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='pomodoro')
async def pomodoro(ctx, work_minutes: int = 25, break_minutes: int = 5):
    """Start a pomodoro session"""
    user_id = str(ctx.author.id)
    
    if user_id in pomodoro_sessions:
        await ctx.send("❌ You already have an active pomodoro session!")
        return
    
    if work_minutes < 1 or work_minutes > 120 or break_minutes < 1 or break_minutes > 60:
        await ctx.send("❌ Invalid time! Work: 1-120 minutes, Break: 1-60 minutes")
        return
    
    pomodoro_sessions[user_id] = {
        'work_minutes': work_minutes,
        'break_minutes': break_minutes,
        'start_time': datetime.datetime.now(),
        'phase': 'work',
        'channel': ctx.channel
    }
    
    embed = discord.Embed(
        title="🍅 Pomodoro Started",
        description=f"Work time: {work_minutes} minutes\nBreak time: {break_minutes} minutes",
        color=0xff4500
    )
    await ctx.send(embed=embed)
    
    # Start the pomodoro timer
    await run_pomodoro(user_id, ctx.channel)

async def run_pomodoro(user_id, channel):
    """Run the pomodoro timer"""
    session = pomodoro_sessions[user_id]
    
    # Work phase
    await asyncio.sleep(session['work_minutes'] * 60)
    
    if user_id not in pomodoro_sessions:  # Session was cancelled
        return
    
    embed = discord.Embed(
        title="⏰ Break Time!",
        description=f"Take a {session['break_minutes']} minute break!",
        color=0x00ff00
    )
    await channel.send(embed=embed)
    
    # Break phase
    await asyncio.sleep(session['break_minutes'] * 60)
    
    if user_id not in pomodoro_sessions:  # Session was cancelled
        return
    
    embed = discord.Embed(
        title="✅ Pomodoro Complete!",
        description="Great work! Ready for another session?",
        color=0x0099ff
    )
    await channel.send(embed=embed)
    
    del pomodoro_sessions[user_id]

@bot.command(name='stop')
async def stop_pomodoro(ctx):
    """Stop current pomodoro session"""
    user_id = str(ctx.author.id)
    
    if user_id in pomodoro_sessions:
        del pomodoro_sessions[user_id]
        await ctx.send("⏹️ Pomodoro session stopped!")
    else:
        await ctx.send("❌ No active pomodoro session!")

@bot.command(name='weekly')
async def weekly_summary(ctx):
    """Show weekly summary for all users"""
    if not user_stats:
        await ctx.send("❌ No study data available!")
        return
    
    total_hours = sum(stats['weekly'] for stats in user_stats.values())
    active_users = len([s for s in user_stats.values() if s['weekly'] > 0])
    
    embed = discord.Embed(
        title="📈 Weekly Server Summary",
        color=0x9932cc
    )
    embed.add_field(name="Total Hours Studied", value=f"{total_hours:.1f} hours", inline=True)
    embed.add_field(name="Active Studiers", value=f"{active_users} users", inline=True)
    embed.add_field(name="Average per User", value=f"{total_hours/max(active_users, 1):.1f} hours", inline=True)
    
    await ctx.send(embed=embed)

@tasks.loop(hours=24)
async def weekly_reset():
    """Reset weekly stats every Monday"""
    if datetime.datetime.now().weekday() == 0:  # Monday
        for user_id in user_stats:
            user_stats[user_id]['weekly'] = 0
        save_data(user_stats)

@bot.command(name='help_study')
async def help_study(ctx):
    """Show bot commands"""
    embed = discord.Embed(
        title="📚 Study Bot Commands",
        description="Here are all available commands:",
        color=0x7289da
    )
    
    commands_list = [
        ("!start", "Start a study session"),
        ("!end", "End your current study session"),
        ("!stats [user]", "Show study statistics"),
        ("!leaderboard", "Show weekly leaderboard"),
        ("!pomodoro [work] [break]", "Start pomodoro timer (default: 25/5 min)"),
        ("!stop", "Stop current pomodoro session"),
        ("!weekly", "Show server weekly summary"),
        ("!help_study", "Show this help message")
    ]
    
    for command, description in commands_list:
        embed.add_field(name=command, value=description, inline=False)
    
    await ctx.send(embed=embed)


bot.run(os.getenv('DISCORD_TOKEN'))
