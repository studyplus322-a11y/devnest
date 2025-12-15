# -*- coding: utf-8 -*-
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Select
import os
import sqlite3
import json
import random
import datetime
import asyncio
import logging
from typing import Optional

# ========== إعدادات البوت ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.all()
bot = commands.Bot(
    command_prefix=['!', '.', '?', '/', 'بوت '],
    intents=intents,
    help_command=None,
    case_insensitive=True
)

# ألوان متنوعة للاستخدام
COLORS = {
    "SUCCESS": 0x00ff00,
    "ERROR": 0xff0000,
    "WARNING": 0xffaa00,
    "INFO": 0x0088ff,
    "PURPLE": 0x9b59b6,
    "GOLD": 0xf1c40f,
    "BLUE": 0x3498db,
    "GREEN": 0x2ecc71,
    "RED": 0xe74c3c,
    "ORANGE": 0xe67e22,
    "DARK": 0x2c3e50
}

# قاعدة البيانات
DB_NAME = "bot_database.db"

# ========== نظام قاعدة البيانات ==========
def init_db():
    """تهيئة جميع جداول قاعدة البيانات"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # جدول الأعضاء الرئيسي
    c.execute('''CREATE TABLE IF NOT EXISTS members
                 (user_id TEXT PRIMARY KEY,
                  username TEXT,
                  coins INTEGER DEFAULT 1000,
                  level INTEGER DEFAULT 1,
                  xp INTEGER DEFAULT 0,
                  warnings INTEGER DEFAULT 0,
                  daily_claimed DATETIME,
                  created_at DATETIME,
                  messages INTEGER DEFAULT 0)''')
    
    # جدول التحذيرات
    c.execute('''CREATE TABLE IF NOT EXISTS warnings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT,
                  moderator_id TEXT,
                  reason TEXT,
                  timestamp DATETIME,
                  status TEXT DEFAULT 'active')''')
    
    # جدول التذاكر
    c.execute('''CREATE TABLE IF NOT EXISTS tickets
                 (ticket_id TEXT PRIMARY KEY,
                  user_id TEXT,
                  channel_id TEXT,
                  status TEXT DEFAULT 'open',
                  created_at DATETIME,
                  closed_at DATETIME,
                  closed_by TEXT)''')
    
    # جدول الألعاب
    c.execute('''CREATE TABLE IF NOT EXISTS games
                 (game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  game_type TEXT,
                  player1_id TEXT,
                  player2_id TEXT,
                  winner_id TEXT,
                  bet_amount INTEGER,
                  result TEXT,
                  played_at DATETIME)''')
    
    # جدول المتجر
    c.execute('''CREATE TABLE IF NOT EXISTS shop
                 (item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  description TEXT,
                  price INTEGER,
                  role_id TEXT,
                  emoji TEXT,
                  category TEXT)''')
    
    # جدول المشتريات
    c.execute('''CREATE TABLE IF NOT EXISTS purchases
                 (purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT,
                  item_id INTEGER,
                  purchased_at DATETIME)''')
    
    # جدول الإحصائيات
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  stat_key TEXT UNIQUE,
                  stat_value INTEGER DEFAULT 0,
                  updated_at DATETIME)''')
    
    # جدول الردود التلقائية
    c.execute('''CREATE TABLE IF NOT EXISTS auto_replies
                 (reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  trigger TEXT UNIQUE,
                  response TEXT,
                  added_by TEXT,
                  added_at DATETIME)''')
    
    # جدول الـ VIP
    c.execute('''CREATE TABLE IF NOT EXISTS vip_users
                 (user_id TEXT PRIMARY KEY,
                  expires_at DATETIME,
                  purchased_at DATETIME)''')
    
    conn.commit()
    conn.close()
    logger.info("✅ تم تهيئة قاعدة البيانات")

# تهيئة قاعدة البيانات عند الاستيراد
init_db()

# ========== وظائف قاعدة البيانات ==========
def get_member_data(user_id):
    """الحصول على بيانات العضو"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM members WHERE user_id = ?", (str(user_id),))
    data = c.fetchone()
    conn.close()
    
    if not data:
        # إنشاء بيانات جديدة
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO members (user_id, coins, level, xp, created_at) VALUES (?, ?, ?, ?, ?)",
                 (str(user_id), 1000, 1, 0, datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM members WHERE user_id = ?", (str(user_id),))
        data = c.fetchone()
        conn.close()
    
    return data

def update_member_xp(user_id, xp_amount):
    """تحديث خبرة العضو"""
    data = get_member_data(user_id)
    current_xp = data[4]
    current_level = data[3]
    
    new_xp = current_xp + xp_amount
    needed_xp = current_level * 100
    
    level_up = False
    if new_xp >= needed_xp:
        new_level = current_level + 1
        new_xp = new_xp - needed_xp
        level_up = True
    else:
        new_level = current_level
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE members SET xp = ?, level = ? WHERE user_id = ?",
             (new_xp, new_level, str(user_id)))
    conn.commit()
    conn.close()
    
    return level_up, new_level, new_xp

def add_coins(user_id, amount):
    """إضافة/خصم عملات"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE members SET coins = coins + ? WHERE user_id = ?",
             (amount, str(user_id)))
    conn.commit()
    conn.close()

def add_warning(user_id, moderator_id, reason):
    """إضافة تحذير للعضو"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # إضافة التحذير
    c.execute("INSERT INTO warnings (user_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?)",
             (str(user_id), str(moderator_id), reason, datetime.datetime.now().isoformat()))
    
    # زيادة عدد التحذيرات
    c.execute("UPDATE members SET warnings = warnings + 1 WHERE user_id = ?", (str(user_id),))
    
    # الحصول على عدد التحذيرات الجديد
    c.execute("SELECT warnings FROM members WHERE user_id = ?", (str(user_id),))
    warning_count = c.fetchone()[0]
    
    conn.commit()
    conn.close()
    
    return warning_count

def get_leaderboard(limit=10):
    """الحصول على لوحة المتصدرين"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id, coins, level FROM members ORDER BY coins DESC LIMIT ?", (limit,))
    data = c.fetchall()
    conn.close()
    return data

def add_game_record(game_type, player1_id, player2_id, winner_id, bet_amount, result):
    """تسجيل نتيجة لعبة"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""INSERT INTO games 
                 (game_type, player1_id, player2_id, winner_id, bet_amount, result, played_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
             (game_type, str(player1_id), str(player2_id) if player2_id else None, 
              str(winner_id) if winner_id else None, bet_amount, result, 
              datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

def increment_stat(stat_key):
    """زيادة عداد إحصائية"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # التحقق من وجود الإحصائية
    c.execute("SELECT stat_value FROM stats WHERE stat_key = ?", (stat_key,))
    result = c.fetchone()
    
    if result:
        c.execute("UPDATE stats SET stat_value = stat_value + 1, updated_at = ? WHERE stat_key = ?",
                 (datetime.datetime.now().isoformat(), stat_key))
    else:
        c.execute("INSERT INTO stats (stat_key, stat_value, updated_at) VALUES (?, ?, ?)",
                 (stat_key, 1, datetime.datetime.now().isoformat()))
    
    conn.commit()
    conn.close()

# ========== أحداث البوت ==========
@bot.event
async def on_ready():
    """حدث تشغيل البوت"""
    logger.info(f'✅ تم تسجيل الدخول باسم: {bot.user.name}')
    logger.info(f'🆔 رقم البوت: {bot.user.id}')
    logger.info(f'📊 عدد السيرفرات: {len(bot.guilds)}')
    logger.info(f'👥 عدد المستخدمين: {len(bot.users)}')
    
    # تحديث حالة البوت
    await update_bot_status()
    
    # بدء المهام التلقائية
    update_status.start()
    check_expired_vip.start()
    send_daily_announcement.start()
    
    logger.info("🚀 البوت جاهز للعمل 24/7!")

@bot.event
async def on_guild_join(guild):
    """حدث انضمام البوت لسيرفر جديد"""
    logger.info(f'🎉 انضممت لسيرفر جديد: {guild.name} ({guild.id})')
    
    # إرسال رسالة ترحيبية
    channel = guild.system_channel or discord.utils.get(guild.text_channels, name="عام")
    if channel:
        embed = discord.Embed(
            title="🎊 شكراً لإضافتي!",
            description=f"**مرحباً بك في {guild.name}!**\n\n"
                       f"أنا **{bot.user.name}**، بوت متكامل للمجتمعات البرمجية.\n"
                       f"أحتوي على **50+ أمر** مفيد للنشاط والإدارة والترفيه.",
            color=COLORS["SUCCESS"]
        )
        
        embed.add_field(
            name="🎮 مميزاتي الرئيسية",
            value="""• نظام ألعاب متكامل
• اقتصاد وتحديات
• إدارة متقدمة
• تذاكر دعم فني
• نظام مستويات
• متجر وعناصر""",
            inline=False
        )
        
        embed.add_field(
            name="🚀 ابدأ الآن",
            value="اكتب `!مساعدة` لرؤية جميع الأوامر\n"
                 "اكتب `!ألعاب` لبدء اللعب\n"
                 "اكتب `!رصيدي` لفحص حسابك",
            inline=False
        )
        
        embed.set_footer(text=f"إصدار البوت: 2.0 | المطور: @{bot.user.name}")
        
        await channel.send(embed=embed)

@bot.event
async def on_member_join(member):
    """ترحيب بالأعضاء الجدد"""
    # تحديث الإحصائيات
    increment_stat("total_joins")
    
    # البحث عن قناة الترحيب
    welcome_channel = discord.utils.get(member.guild.text_channels, name="🚪-الترحيب")
    if not welcome_channel:
        welcome_channel = discord.utils.get(member.guild.text_channels, name="💬-عام")
    if not welcome_channel:
        welcome_channel = member.guild.system_channel
    
    if welcome_channel:
        embed = discord.Embed(
            title=f"🎊 أهلاً وسهلاً {member.name}!",
            description=f"**مرحباً بك في {member.guild.name}**\n\n"
                       f"أنت العضو رقم **#{member.guild.member_count}**\n"
                       f"نتمنى لك وقتاً ممتعاً معنا!",
            color=COLORS["SUCCESS"]
        )
        
        embed.add_field(
            name="📚 نصائح سريعة",
            value="""1. اقرأ #📜-القواعد أولاً
2. تعرف على الأعضاء في #💬-عام
3. استخدم `!مساعدة` لمعرفة الأوامر
4. العب واستمتع مع `!ألعاب`""",
            inline=False
        )
        
        embed.add_field(
            name="🎁 هدية ترحيبية",
            value="لقد حصلت على **500 عملة** ترحيبية!\n"
                 "استخدم `!رصيدي` للتحقق",
            inline=True
        )
        
        # منح العملات الترحيبية
        add_coins(member.id, 500)
        
        embed.add_field(
            name="🎭 اختر اهتماماتك",
            value="انقر الزر بالأسفل لاختيار رتبتك",
            inline=True
        )
        
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.set_footer(text=f"تاريخ الانضمام: {member.joined_at.strftime('%Y-%m-%d %H:%M')}")
        
        # إنشاء زر اختيار الرتب
        view = View()
        
        role_button = Button(label="🎭 اختر رتبتك", style=discord.ButtonStyle.primary, emoji="⚡")
        
        async def role_button_callback(interaction):
            if interaction.user.id != member.id:
                await interaction.response.send_message("هذا الزر ليس لك!", ephemeral=True)
                return
            
            # إنشاء قائمة اختيار الرتب
            select = Select(
                placeholder="اختر رتبة اهتماماتك",
                options=[
                    discord.SelectOption(label="بايثون", value="python", emoji="🐍", description="لغة بايثون"),
                    discord.SelectOption(label="جافا سكريبت", value="javascript", emoji="📜", description="تطوير الويب"),
                    discord.SelectOption(label="تطوير الألعاب", value="gamedev", emoji="🎮", description="Unity/Unreal"),
                    discord.SelectOption(label="الذكاء الاصطناعي", value="ai", emoji="🤖", description="AI/ML"),
                    discord.SelectOption(label="تطوير الهواتف", value="mobile", emoji="📱", description="Android/iOS"),
                    discord.SelectOption(label="قواعد بيانات", value="database", emoji="💾", description="SQL/NoSQL"),
                    discord.SelectOption(label="الأمن السيبراني", value="cyber", emoji="🛡️", description="Security"),
                    discord.SelectOption(label="تطوير الويب", value="web", emoji="🌐", description="Frontend/Backend")
                ]
            )
            
            async def select_callback(interaction):
                role_mapping = {
                    "python": "🐍 مبرمج بايثون",
                    "javascript": "📜 مبرمج جافا سكريبت",
                    "gamedev": "🎮 مطور ألعاب",
                    "ai": "🤖 ذكاء اصطناعي",
                    "mobile": "📱 مطور هواتف",
                    "database": "💾 قواعد بيانات",
                    "cyber": "🛡️ أمن سيبراني",
                    "web": "🌐 مطور ويب"
                }
                
                selected_role_name = role_mapping.get(select.values[0])
                role = discord.utils.get(interaction.guild.roles, name=selected_role_name)
                
                if not role:
                    # إنشاء الرتبة إذا لم تكن موجودة
                    role_colors = {
                        "python": discord.Color.green(),
                        "javascript": discord.Color.yellow(),
                        "gamedev": discord.Color.purple(),
                        "ai": discord.Color.blue(),
                        "mobile": discord.Color.dark_green(),
                        "database": discord.Color.dark_gray(),
                        "cyber": discord.Color.dark_red(),
                        "web": discord.Color.orange()
                    }
                    
                    role = await interaction.guild.create_role(
                        name=selected_role_name,
                        color=role_colors.get(select.values[0], discord.Color.default()),
                        mentionable=True,
                        hoist=True
                    )
                
                await member.add_roles(role)
                
                success_embed = discord.Embed(
                    title="✅ تمت إضافة الرتبة",
                    description=f"تمت إضافة رتبة {role.mention} لك بنجاح!",
                    color=COLORS["SUCCESS"]
                )
                
                await interaction.response.edit_message(embed=success_embed, view=None)
            
            select.callback = select_callback
            
            select_view = View()
            select_view.add_item(select)
            
            await interaction.response.send_message(
                "اختر رتبة تلائم اهتماماتك البرمجية:",
                view=select_view,
                ephemeral=True
            )
        
        role_button.callback = role_button_callback
        view.add_item(role_button)
        
        await welcome_channel.send(f"{member.mention} 👋", embed=embed, view=view)
    
    # إرسال رسالة ترحيبية خاصة
    try:
        welcome_dm = discord.Embed(
            title=f"مرحباً بك في {member.guild.name}!",
            description="شكراً لانضمامك إلى مجتمعنا البرمجي. إليك بعض المعلومات المهمة:",
            color=COLORS["INFO"]
        )
        
        welcome_dm.add_field(
            name="🎯 بداية سريعة",
            value="""**1.** اكتب `!مساعدة` لرؤية الأوامر
**2.** العب `!ألعاب` لتربح عملات
**3.** تحقق من `!رصيدي` لمتابعة تقدمك
**4.** تعرف على الأعضاء في القنوات النشطة""",
            inline=False
        )
        
        welcome_dm.add_field(
            name="💰 هدية خاصة",
            value="لقد حصلت على **500 عملة** ترحيبية!",
            inline=True
        )
        
        welcome_dm.add_field(
            name="🎮 تحديات يومية",
            value="اكسب عملات إضافية بالتحديات اليومية",
            inline=True
        )
        
        welcome_dm.set_footer(text="نتمنى لك تجربة ممتعة معنا!")
        
        await member.send(embed=welcome_dm)
    except:
        logger.info(f"❌ لا يمكن إرسال رسالة خاصة لـ {member.name}")

@bot.event
async def on_member_remove(member):
    """عند مغادرة العضو"""
    increment_stat("total_leaves")
    
    channel = discord.utils.get(member.guild.text_channels, name="🚪-الترحيب")
    if channel:
        embed = discord.Embed(
            title="👋 وداعاً",
            description=f"{member.mention} غادر السيرفر",
            color=COLORS["WARNING"]
        )
        await channel.send(embed=embed)

@bot.event
async def on_message(message):
    """معالجة جميع الرسائل"""
    if message.author.bot:
        return
    
    # تحديث عدد الرسائل
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE members SET messages = messages + 1 WHERE user_id = ?", (str(message.author.id),))
    conn.commit()
    conn.close()
    
    # إضافة خبرة عشوائية لكل رسالة
    xp_gained = random.randint(5, 15)
    level_up, new_level, new_xp = update_member_xp(message.author.id, xp_gained)
    
    # إرسال رسالة الترقية إذا تم الارتقاء
    if level_up:
        embed = discord.Embed(
            title="🎉 ترقية مستوى!",
            description=f"{message.author.mention} لقد ارتقت إلى المستوى **{new_level}**!",
            color=COLORS["GOLD"]
        )
        
        # مكافأة الترقية
        level_reward = new_level * 100
        add_coins(message.author.id, level_reward)
        
        embed.add_field(
            name="🎁 مكافأة الترقية",
            value=f"لقد حصلت على **{level_reward} عملة** مكافأة!",
            inline=False
        )
        
        embed.set_thumbnail(url=message.author.avatar.url if message.author.avatar else message.author.default_avatar.url)
        
        await message.channel.send(embed=embed)
    
    # التحقق من الردود التلقائية
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT trigger, response FROM auto_replies")
    auto_replies = c.fetchall()
    conn.close()
    
    for trigger, response in auto_replies:
        if trigger.lower() in message.content.lower():
            await message.channel.send(response)
            break
    
    # معالجة الأوامر
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    """معالجة أخطاء الأوامر"""
    if isinstance(error, commands.CommandNotFound):
        embed = discord.Embed(
            title="❌ أمر غير موجود",
            description="هذا الأمر غير موجود!\n\nاستخدم `!مساعدة` لرؤية جميع الأوامر المتاحة.",
            color=COLORS["ERROR"]
        )
        await ctx.send(embed=embed)
    
    elif isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(
            title="⛔ صلاحيات غير كافية",
            description="ليس لديك الصلاحيات الكافية لاستخدام هذا الأمر!",
            color=COLORS["ERROR"]
        )
        await ctx.send(embed=embed)
    
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="⚠️ معطيات ناقصة",
            description=f"معطيات الأمر ناقصة!\n\n**الصيغة الصحيحة:** `{ctx.prefix}{ctx.command.name} {ctx.command.signature}`",
            color=COLORS["WARNING"]
        )
        await ctx.send(embed=embed)
    
    elif isinstance(error, commands.BadArgument):
        embed = discord.Embed(
            title="⚠️ معطيات خاطئة",
            description="المعطيات التي أدخلتها غير صحيحة!\nيرجى التحقق والمحاولة مرة أخرى.",
            color=COLORS["WARNING"]
        )
        await ctx.send(embed=embed)
    
    else:
        logger.error(f"خطأ غير متوقع: {error}")
        embed = discord.Embed(
            title="💥 خطأ غير متوقع",
            description="حدث خطأ غير متوقع أثناء تنفيذ الأمر!\nتم تسجيل الخطأ وسيتم إصلاحه قريباً.",
            color=COLORS["ERROR"]
        )
        await ctx.send(embed=embed)

# ========== المهام التلقائية ==========
@tasks.loop(minutes=5)
async def update_status():
    """تحديث حالة البوت كل 5 دقائق"""
    statuses = [
        f"!مساعدة | {len(bot.guilds)} سيرفر",
        f"مع {len(bot.users)} مستخدم",
        "مجتمع المبرمجين العرب",
        "ألعاب !ألعاب | اقتصاد !رصيدي",
        "50+ أمر متاح | !مساعدة",
        f"نشط في {len(bot.guilds)} مجتمع",
        "طور مهاراتك البرمجية",
        "تحديات يومية جديدة!",
        "اكتسب الخبرة وارتقِ بالمستوى",
        "متجر مميزات !متجر"
    ]
    
    activity = discord.Activity(
        type=discord.ActivityType.playing,
        name=random.choice(statuses)
    )
    await bot.change_presence(activity=activity)

@tasks.loop(hours=24)
async def check_expired_vip():
    """التحقق من انتهاء صلاحية VIP"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    current_time = datetime.datetime.now().isoformat()
    c.execute("SELECT user_id FROM vip_users WHERE expires_at < ?", (current_time,))
    expired_users = c.fetchall()
    
    for user_id, in expired_users:
        c.execute("DELETE FROM vip_users WHERE user_id = ?", (user_id,))
        
        try:
            user = await bot.fetch_user(int(user_id))
            embed = discord.Embed(
                title="VIP انتهت صلاحية اشتراكك",
                description="لقد انتهت صلاحية اشتراك الـ VIP الخاص بك.\n\nيمكنك تجديده من المتجر!",
                color=COLORS["WARNING"]
            )
            await user.send(embed=embed)
        except:
            pass
    
    conn.commit()
    conn.close()

@tasks.loop(hours=24)
async def send_daily_announcement():
    """إرسال إعلان يومي"""
    current_hour = datetime.datetime.now().hour
    
    if current_hour == 12:  # الساعة 12 ظهراً
        for guild in bot.guilds:
            announcement_channel = discord.utils.get(guild.text_channels, name="📢-إعلانات")
            if not announcement_channel:
                announcement_channel = discord.utils.get(guild.text_channels, name="💬-عام")
            
            if announcement_channel:
                embed = discord.Embed(
                    title="📢 إعلان يومي",
                    description="**تحديات اليوم متاحة الآن!**\n\n"
                               "✊✋✌️ العب `!حجر` ضد البوت\n"
                               "🧠 جاوب على `!سؤال` برمجي\n"
                               "🎲 خاطر في `!روليت`\n"
                               "🏆 تصدر `!المتصدرين`",
                    color=COLORS["GOLD"]
                )
                
                embed.add_field(
                    name="💰 مكافأة النشاط",
                    value="أرسل 50 رسالة اليوم تربح 200 عملة إضافية!",
                    inline=False
                )
                
                embed.add_field(
                    name="🎁 هدية خاصة",
                    value="أول 10 لاعبين يربحون اليوم يحصلون على مكافأة مضاعفة!",
                    inline=False
                )
                
                embed.set_footer(text=f"التاريخ: {datetime.datetime.now().strftime('%Y-%m-%d')}")
                
                await announcement_channel.send(embed=embed)

# ========== الأوامر الأساسية ==========
@bot.command(name="مساعدة")
async def help_command(ctx):
    """عرض جميع الأوامر"""
    embed = discord.Embed(
        title="📚 مركز المساعدة الشامل",
        description="**مرحباً بك في مركز مساعدة البوت!**\n\n"
                   "استخدم الأزرار بالأسفل للتنقل بين الأقسام.\n"
                   f"**إجمالي الأوامر: 50+** | **السيرفرات: {len(bot.guilds)}**",
        color=COLORS["PURPLE"]
    )
    
    embed.add_field(
        name="🎮 **قسم الألعاب**",
        value="""```
!ألعاب       - مركز الألعاب
!روليت مبلغ  - لعبة الروليت (حتى 35x)
!حجر        - حجر ورقة مقص
!سؤال       - سؤال برمجي (75 عملة)
!تخمين رقم  - خمن الرص (1-100)
!بطاقة      - سحب بطاقة عشوائية
!تحدي @شخص  - تحدى صديقك
!مسابقة     - مسابقة يومية```""",
        inline=False
    )
    
    embed.add_field(
        name="💰 **النظام الاقتصادي**",
        value="""```
!رصيدي      - رصيدك ومستواك
!تحويل @شخص مبلغ - تحويل عملات
!المتصدرين  - أفضل 10 لاعبين
!مكافأة     - المكافأة اليومية (500 عملة)
!عمل        - عمل إضافي (100-300)
!متجر       - عرض المتجر
!شراء رقم_العنصر - شراء من المتجر```""",
        inline=False
    )
    
    embed.add_field(
        name="📊 **المعلومات والإحصائيات**",
        value="""```
!معلومات    - معلومات السيرفر
!معلوماتي   - معلوماتك الشخصية
!معلومات @شخص - معلومات عن عضو
!سيرفر      - إحصائيات السيرفر
!بانر       - بانر شخصي مخصص
!أفاتار     - عرض صورتك
!أفاتار @شخص - صورة عضو آخر```""",
        inline=False
    )
    
    embed.add_field(
        name="🛡️ **نظام الإدارة**",
        value="""```
!مسح عدد    - مسح الرسائل (حد 100)
!تحذير @شخص السبب - تحذير عضو
!تحذيرات @شخص - عرض تحذيرات العضو
!إزالة_تحذير @شخص - إزالة تحذير
!تأديب @شخص مدة - تايم آوت (1h, 1d)
!كيك @شخص السبب - طرد عضو
!بان @شخص السبب - حظر عضو```""",
        inline=False
    )
    
    embed.add_field(
        name="🎫 **نظام الدعم والتذاكر**",
        value="""```
!تذكرة      - فتح تذكرة دعم
!تذاكري     - تذاكرك المفتوحة
!إغلاق_تذكرة - إغلاق التذكرة الحالية
!مساعدة_فنية - الحصول على مساعدة سريعة
!بلغ @شخص السبب - الإبلاغ عن مشكلة```""",
        inline=False
    )
    
    embed.add_field(
        name="⚙️ **أوامر الإعدادات**",
        value="""```
!إعدادات    - إعدادات السيرفر
!إضافة_رد كلمة رد - إضافة رد تلقائي
!حذف_رد كلمة    - حذف رد تلقائي
!الردود     - عرض الردود التلقائية
!قناة_ترحيب #قناة - تعيين قناة ترحيب
!رسالة_ترحيب نص - تعيين رسالة ترحيب```""",
        inline=False
    )
    
    embed.set_footer(text=f"طلب بواسطة: {ctx.author.name} | إصدار البوت: 2.0")
    
    # إنشاء أزرار التنقل
    view = View()
    
    buttons_data = [
        ("🎮 الألعاب", discord.ButtonStyle.green, "games_help"),
        ("💰 الاقتصاد", discord.ButtonStyle.blurple, "economy_help"),
        ("📊 المعلومات", discord.ButtonStyle.gray, "info_help"),
        ("🛡️ الإدارة", discord.ButtonStyle.red, "admin_help"),
        ("⚙️ الإعدادات", discord.ButtonStyle.gray, "settings_help")
    ]
    
    for label, style, custom_id in buttons_data:
        button = Button(label=label, style=style, custom_id=custom_id)
        view.add_item(button)
    
    await ctx.send(embed=embed, view=view)

@bot.command(name="ألعاب")
async def games_menu(ctx):
    """قائمة مركز الألعاب"""
    embed = discord.Embed(
        title="🎮 مركز الألعاب الشامل",
        description="**مرحباً بك في عالم الألعاب والتحديات!**\n\n"
                   "اختر لعبة للبدء واكتساب الخبرة والعملات.\n"
                   "كل لعبة تمنحك خبرة وعملات مختلفة!",
        color=COLORS["GOLD"]
    )
    
    games = [
        {
            "name": "🎲 **الروليت**",
            "description": "اراهن واربح حتى 35x من رهانك!",
            "command": "!روليت [المبلغ]",
            "prize": "2x-35x",
            "xp": "10-50"
        },
        {
            "name": "✊✋✌️ **حجر ورقة مقص**",
            "description": "العب ضد البوت في اللعبة الكلاسيكية",
            "command": "!حجر",
            "prize": "50 عملة للفوز",
            "xp": "15"
        },
        {
            "name": "🧠 **سؤال برمجي**",
            "description": "اختبر معرفتك البرمجية واربح",
            "command": "!سؤال",
            "prize": "75 عملة",
            "xp": "20"
        },
        {
            "name": "🎯 **التخمين**",
            "description": "خمن الرقم بين 1-100 واربح",
            "command": "!تخمين [الرقم]",
            "prize": "100 عملة",
            "xp": "25"
        },
        {
            "name": "🃏 **البطاقات**",
            "description": "اسحب بطاقة عشوائية واربح جوائز",
            "command": "!بطاقة",
            "prize": "10-200 عملة",
            "xp": "10-30"
        },
        {
            "name": "⚔️ **التحدي**",
            "description": "تحدى صديقك في مباراة",
            "command": "!تحدي @الشخص",
            "prize": "100 عملة للفائز",
            "xp": "30"
        },
        {
            "name": "🏆 **المسابقة**",
            "description": "مسابقة يومية بجوائز كبيرة",
            "command": "!مسابقة",
            "prize": "500 عملة",
            "xp": "50"
        }
    ]
    
    for game in games:
        embed.add_field(
            name=game["name"],
            value=f"**{game['description']}**\n"
                 f"📝 الأمر: `{game['command']}`\n"
                 f"💰 الجائزة: {game['prize']}\n"
                 f"⚡ الخبرة: {game['xp']} نقطة",
            inline=False
        )
    
    embed.add_field(
        name="📊 **إحصائيات الألعاب**",
        value=f"**الألعاب المجنونة:** {len(games)}\n"
              f"**أعلى جائزة:** 35x مضاعف\n"
              f"**أقصى خبرة:** 50 نقطة\n"
              f"**متوسط الجوائز:** 150 عملة",
        inline=False
    )
    
    embed.set_footer(text="اكتب اسم اللعبة للبدء! | كل لعبة تعطيك خبرة مختلفة")
    
    # أزرار الألعاب
    view = View()
    
    game_buttons = [
        ("🎲 الروليت", discord.ButtonStyle.green, "roulette_game"),
        ("✊✋✌️", discord.ButtonStyle.blurple, "rps_game"),
        ("🧠 سؤال", discord.ButtonStyle.gray, "question_game"),
        ("🎯 تخمين", discord.ButtonStyle.green, "guess_game")
    ]
    
    for label, style, custom_id in game_buttons:
        button = Button(label=label, style=style, custom_id=custom_id)
        view.add_item(button)
    
    await ctx.send(embed=embed, view=view)

@bot.command(name="روليت")
async def roulette_game(ctx, bet: int = None):
    """لعبة الروليت الكاملة"""
    if bet is None:
        embed = discord.Embed(
            title="🎲 لعبة الروليت",
            description="**كيف تلعب:**\n"
                       "1. اختر رقماً من 0-36 أو لوناً (أحمر/أسود)\n"
                       "2. اختر مبلغ الرهان\n"
                       "3. انتظر النتيجة!\n\n"
                       "**المضاعفات:**\n"
                       "• رهان على رقم: **35x**\n"
                       "• رهان على لون: **2x**\n"
                       "• رهان على زوجي/فردي: **2x**",
            color=COLORS["GOLD"]
        )
        
        view = View()
        
        # أزرار الرهان
        buttons = [
            ("🔴 أحمر (2x)", discord.ButtonStyle.red, "bet_red"),
            ("⚫ أسود (2x)", discord.ButtonStyle.gray, "bet_black"),
            ("🟢 صفر (35x)", discord.ButtonStyle.green, "bet_zero"),
            ("🎲 رقم محدد (35x)", discord.ButtonStyle.blurple, "bet_number")
        ]
        
        for label, style, custom_id in buttons:
            button = Button(label=label, style=style, custom_id=custom_id)
            view.add_item(button)
        
        await ctx.send(embed=embed, view=view)
        return
    
    # التحقق من الرصيد
    user_data = get_member_data(ctx.author.id)
    user_coins = user_data[2]
    
    if bet <= 0:
        await ctx.send("❌ الرهان يجب أن يكون أكبر من صفر!")
        return
    
    if bet > user_coins:
        await ctx.send(f"❌ ليس لديك عملات كافية! رصيدك: {user_coins}")
        return
    
    # خصم الرهان
    add_coins(ctx.author.id, -bet)
    
    # تدوير الروليت
    winning_number = random.randint(0, 36)
    winning_color = "🔴" if winning_number % 2 == 1 else "⚫" if winning_number != 0 else "🟢"
    
    # تحديد الفوز (فرصة 1/3 للفوز)
    if random.random() < 0.33:
        # فوز
        if winning_number == 0:
            multiplier = 35
            win_type = "🎉 جاكبوت! رقم صفر!"
        else:
            multiplier = 2
            win_type = "🎊 فوز! اللون صحيح!"
        
        win_amount = bet * multiplier
        add_coins(ctx.author.id, win_amount)
        
        embed = discord.Embed(
            title="🎲 الروليت - فوز كبير!",
            description=f"**{win_type}**\n\n"
                       f"الرقم الفائز: **{winning_number} {winning_color}**",
            color=COLORS["SUCCESS"]
        )
        
        embed.add_field(name="💰 رهانك", value=f"{bet} عملة", inline=True)
        embed.add_field(name="🎁 المضاعف", value=f"{multiplier}x", inline=True)
        embed.add_field(name="💎 فوزك", value=f"{win_amount} عملة", inline=True)
        
        # تسجيل اللعبة
        add_game_record("roulette", ctx.author.id, None, ctx.author.id, bet, f"win_{multiplier}x")
        
    else:
        # خسارة
        embed = discord.Embed(
            title="🎲 الروليت - خسارة",
            description=f"**💥 للأسف خسرت!**\n\n"
                       f"الرقم الفائز: **{winning_number} {winning_color}**",
            color=COLORS["ERROR"]
        )
        
        embed.add_field(name="💰 رهانك", value=f"{bet} عملة", inline=True)
        embed.add_field(name="💸 خسرت", value=f"{bet} عملة", inline=True)
        
        # تسجيل اللعبة
        add_game_record("roulette", ctx.author.id, None, None, bet, "loss")
    
    await ctx.send(embed=embed)

@bot.command(name="حجر")
async def rock_paper_scissors(ctx):
    """لعبة حجر ورقة مقص"""
    embed = discord.Embed(
        title="✊✋✌️ حجر ورقة مقص",
        description="**اختر حركتك:**\n\n"
                   "✊ **الحجر** يكسر المقص\n"
                   "✋ **الورقة** تغطي الحجر\n"
                   "✌️ **المقص** يقطع الورقة\n\n"
                   "🎁 **الجائزة:** 50 عملة للفوز",
        color=COLORS["GOLD"]
    )
    
    view = View()
    
    choices = [
        ("✊ حجر", discord.ButtonStyle.primary, "rock"),
        ("✋ ورق", discord.ButtonStyle.primary, "paper"),
        ("✌️ مقص", discord.ButtonStyle.primary, "scissors")
    ]
    
    for label, style, choice in choices:
        button = Button(label=label, style=style, custom_id=choice)
        
        async def button_callback(interaction, player_choice=choice):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ هذه اللعبة ليست لك!", ephemeral=True)
                return
            
            bot_choice = random.choice(["rock", "paper", "scissors"])
            
            # تحديد الفائز
            if player_choice == bot_choice:
                result = "⚖️ **تعادل!**"
                coins_won = 10
            elif (player_choice == "rock" and bot_choice == "scissors") or \
                 (player_choice == "paper" and bot_choice == "rock") or \
                 (player_choice == "scissors" and bot_choice == "paper"):
                result = "🎉 **فزت!**"
                coins_won = 50
            else:
                result = "💥 **خسرت!**"
                coins_won = 0
            
            # منح الجائزة
            if coins_won > 0:
                add_coins(ctx.author.id, coins_won)
            
            # إظهار النتيجة
            choice_emojis = {"rock": "✊", "paper": "✋", "scissors": "✌️"}
            
            result_embed = discord.Embed(
                title="🎮 نتيجة اللعبة",
                color=COLORS["SUCCESS"] if coins_won > 0 else COLORS["ERROR"]
            )
            
            result_embed.add_field(
                name="👤 اختيارك",
                value=f"{choice_emojis[player_choice]}",
                inline=True
            )
            
            result_embed.add_field(
                name="🤖 اختيار البوت",
                value=f"{choice_emojis[bot_choice]}",
                inline=True
            )
            
            result_embed.add_field(
                name="🏆 النتيجة",
                value=result,
                inline=False
            )
            
            if coins_won > 0:
                result_embed.add_field(
                    name="🎁 الجائزة",
                    value=f"{coins_won} عملة",
                    inline=True
                )
            
            # تسجيل اللعبة
            winner = ctx.author.id if coins_won == 50 else None if coins_won == 10 else "bot"
            add_game_record("rps", ctx.author.id, "bot", winner, 0, result)
            
            await interaction.response.edit_message(embed=result_embed, view=None)
        
        button.callback = lambda i, c=choice: button_callback(i, c)
        view.add_item(button)
    
    await ctx.send(embed=embed, view=view)

@bot.command(name="سؤال")
async def programming_question(ctx):
    """سؤال برمجي عشوائي"""
    questions = [
        {
            "question": "ما هي لغة البرمجة الأكثر استخداماً في الذكاء الاصطناعي؟",
            "options": ["بايثون", "جافا", "سي++", "جافا سكريبت"],
            "answer": 0,
            "difficulty": "سهل",
            "category": "لغات البرمجة"
        },
        {
            "question": "ما هي مكتبة React مبنية عليها؟",
            "options": ["بايثون", "جافا سكريبت", "سي#", "روبي"],
            "answer": 1,
            "difficulty": "سهل",
            "category": "تطوير الويب"
        },
        {
            "question": "أي من هذه ليست لغة برمجة؟",
            "options": ["HTML", "بايثون", "جافا", "سي++"],
            "answer": 0,
            "difficulty": "سهل",
            "category": "مفاهيم"
        },
        {
            "question": "ما هي وظيفة الأمر 'git commit'؟",
            "options": ["حفظ التغييرات", "تحميل المشروع", "إنشاء فرع جديد", "حذف الملفات"],
            "answer": 0,
            "difficulty": "متوسط",
            "category": "Git"
        },
        {
            "question": "ما هو الـ API؟",
            "options": ["واجهة برمجة التطبيقات", "مكتبة برمجية", "لغة برمجة", "محرك قاعدة بيانات"],
            "answer": 0,
            "difficulty": "متوسط",
            "category": "مفاهيم"
        }
    ]
    
    q = random.choice(questions)
    
    embed = discord.Embed(
        title="🧠 سؤال برمجي",
        description=f"**{q['question']}**\n\n"
                   f"📊 **الصعوبة:** {q['difficulty']}\n"
                   f"📁 **القسم:** {q['category']}\n"
                   f"💰 **الجائزة:** 75 عملة",
        color=COLORS["INFO"]
    )
    
    for i, option in enumerate(q['options']):
        embed.add_field(name=f"الخيار {i+1}", value=option, inline=True)
    
    await ctx.send(embed=embed)
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content in ["1", "2", "3", "4"]
    
    try:
        msg = await bot.wait_for("message", timeout=30.0, check=check)
        
        user_answer = int(msg.content) - 1
        
        if user_answer == q["answer"]:
            # إجابة صحيحة
            add_coins(ctx.author.id, 75)
            update_member_xp(ctx.author.id, 20)
            
            embed = discord.Embed(
                title="✅ إجابة صحيحة!",
                description=f"**مبروك {ctx.author.mention}!**\n"
                           f"الإجابة **{q['options'][q['answer']]}** صحيحة!",
                color=COLORS["SUCCESS"]
            )
            
            embed.add_field(name="🎁 الجائزة", value="75 عملة", inline=True)
            embed.add_field(name="⚡ الخبرة", value="20 نقطة", inline=True)
            embed.add_field(name="📊 الصعوبة", value=q['difficulty'], inline=True)
            
            await ctx.send(embed=embed)
            
            # تسجيل اللعبة
            add_game_record("quiz", ctx.author.id, None, ctx.author.id, 0, "correct")
            
        else:
            # إجابة خاطئة
            correct_answer = q['options'][q['answer']]
            
            embed = discord.Embed(
                title="❌ إجابة خاطئة!",
                description=f"للأسف {ctx.author.mention}، الإجابة خاطئة.",
                color=COLORS["ERROR"]
            )
            
            embed.add_field(name="🤔 إجابتك", value=q['options'][user_answer], inline=True)
            embed.add_field(name="✅ الإجابة الصحيحة", value=correct_answer, inline=True)
            
            await ctx.send(embed=embed)
            
            # تسجيل اللعبة
            add_game_record("quiz", ctx.author.id, None, None, 0, "wrong")
            
    except asyncio.TimeoutError:
        await ctx.send("⏰ **انتهى الوقت!** لم تجب على السؤال.")
        
        # تسجيل اللعبة
        add_game_record("quiz", ctx.author.id, None, None, 0, "timeout")

@bot.command(name="رصيدي")
async def balance_command(ctx, member: discord.Member = None):
    """عرض رصيد العضو"""
    target_member = member or ctx.author
    user_data = get_member_data(target_member.id)
    
    embed = discord.Embed(
        title=f"💰 رصيد {target_member.name}",
        color=target_member.color
    )
    
    # المعلومات الأساسية
    embed.add_field(name="💎 العملات", value=f"**{user_data[2]:,}** عملة", inline=True)
    embed.add_field(name="📈 المستوى", value=f"**{user_data[3]}**", inline=True)
    embed.add_field(name="⚡ الخبرة", value=f"**{user_data[4]}/{user_data[3]*100}**", inline=True)
    
    # معلومات إضافية
    embed.add_field(name="📨 الرسائل", value=f"**{user_data[8]}** رسالة", inline=True)
    embed.add_field(name="⚠️ التحذيرات", value=f"**{user_data[5]}** تحذير", inline=True)
    
    # شريط التقدم
    progress_percentage = (user_data[4] / (user_data[3] * 100)) * 100
    progress_bar_length = 20
    filled = int(progress_percentage / 100 * progress_bar_length)
    progress_bar = "█" * filled + "░" * (progress_bar_length - filled)
    
    embed.add_field(
        name=f"📊 التقدم للمستوى {user_data[3]+1} ({progress_percentage:.1f}%)",
        value=f"```{progress_bar}```",
        inline=False
    )
    
    # المقارنة مع الأعلى
    leaderboard = get_leaderboard(1)
    if leaderboard:
        top_user_coins = leaderboard[0][1]
        if user_data[2] < top_user_coins:
            needed = top_user_coins - user_data[2]
            embed.add_field(
                name="🏆 تحتاج للتصدر",
                value=f"تحتاج **{needed:,}** عملة للوصول للمركز الأول",
                inline=False
            )
    
    embed.set_thumbnail(url=target_member.avatar.url if target_member.avatar else target_member.default_avatar.url)
    embed.set_footer(text=f"آخر تحديث: {datetime.datetime.now().strftime('%H:%M')}")
    
    await ctx.send(embed=embed)

@bot.command(name="تحويل")
async def transfer_command(ctx, member: discord.Member, amount: int):
    """تحويل عملات لعضو آخر"""
    if amount <= 0:
        embed = discord.Embed(
            title="❌ خطأ",
            description="المبلغ يجب أن يكون أكبر من صفر!",
            color=COLORS["ERROR"]
        )
        await ctx.send(embed=embed)
        return
    
    if member == ctx.author:
        embed = discord.Embed(
            title="❌ خطأ",
            description="لا يمكنك تحويل العملات لنفسك!",
            color=COLORS["ERROR"]
        )
        await ctx.send(embed=embed)
        return
    
    # التحقق من الرصيد
    sender_data = get_member_data(ctx.author.id)
    
    if amount > sender_data[2]:
        embed = discord.Embed(
            title="❌ رصيد غير كافٍ",
            description=f"ليس لديك عملات كافية!\nرصيدك الحالي: **{sender_data[2]:,}** عملة",
            color=COLORS["ERROR"]
        )
        await ctx.send(embed=embed)
        return
    
    # التحقق من الحد الأقصى للتحويل
    max_transfer = 10000
    if amount > max_transfer:
        embed = discord.Embed(
            title="❌ تجاوز الحد",
            description=f"الحد الأقصى للتحويل هو **{max_transfer:,}** عملة!",
            color=COLORS["ERROR"]
        )
        await ctx.send(embed=embed)
        return
    
    # تنفيذ التحويل
    add_coins(ctx.author.id, -amount)
    add_coins(member.id, amount)
    
    # رسالة النجاح
    embed = discord.Embed(
        title="💸 تحويل ناجح",
        description=f"تم تحويل **{amount:,}** عملة بنجاح!",
        color=COLORS["SUCCESS"]
    )
    
    embed.add_field(name="👤 المرسل", value=ctx.author.mention, inline=True)
    embed.add_field(name="👥 المستقبل", value=member.mention, inline=True)
    embed.add_field(name="💰 المبلغ", value=f"{amount:,} عملة", inline=True)
    
    embed.add_field(
        name="📊 الرصيد الجديد",
        value=f"{ctx.author.mention}: **{sender_data[2] - amount:,}** عملة",
        inline=False
    )
    
    # إرسال إشعار للمستقبل
    try:
        notification = discord.Embed(
            title="🎁 تحويل مالي",
            description=f"لقد استلمت **{amount:,}** عملة من {ctx.author.mention}!",
            color=COLORS["INFO"]
        )
        await member.send(embed=notification)
    except:
        pass
    
    await ctx.send(embed=embed)

@bot.command(name="المتصدرين")
async def leaderboard_command(ctx):
    """عرض أفضل 10 لاعبين"""
    leaderboard_data = get_leaderboard(10)
    
    embed = discord.Embed(
        title="🏆 لوحة المتصدرين",
        description="**أفضل 10 لاعبين حسب العملات:**\n",
        color=COLORS["GOLD"]
    )
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, (user_id, coins, level) in enumerate(leaderboard_data):
        try:
            user = await bot.fetch_user(int(user_id))
            username = user.name
        except:
            username = "مستخدم غير معروف"
        
        # البحث عن المستخدم في السيرفر
        member = ctx.guild.get_member(int(user_id))
        if member:
            username = member.display_name
        
        embed.add_field(
            name=f"{medals[i]} {username}",
            value=f"💰 **{coins:,}** عملة | 📈 المستوى **{level}**",
            inline=False
        )
    
    # إحصائيات إضافية
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # إجمالي العملات في السيرفر
    c.execute("SELECT SUM(coins) FROM members")
    total_coins = c.fetchone()[0] or 0
    
    # عدد اللاعبين
    c.execute("SELECT COUNT(*) FROM members")
    total_players = c.fetchone()[0]
    
    conn.close()
    
    embed.add_field(
        name="📊 إحصائيات السيرفر",
        value=f"**إجمالي العملات:** {total_coins:,}\n"
              f"**عدد اللاعبين:** {total_players}\n"
              f"**متوسط العملات:** {total_coins//total_players if total_players > 0 else 0:,}",
        inline=False
    )
    
    # التحقق من موقع المستخدم
    user_data = get_member_data(ctx.author.id)
    user_coins = user_data[2]
    
    # العثور على ترتيب المستخدم
    all_players = get_leaderboard(1000)  # الحصول على جميع اللاعبين
    user_rank = None
    
    for i, (uid, coins, _) in enumerate(all_players, 1):
        if uid == str(ctx.author.id):
            user_rank = i
            break
    
    if user_rank:
        embed.set_footer(
            text=f"ترتيبك: #{user_rank} | عملاتك: {user_coins:,} | اكتب !رصيدي للمزيد"
        )
    
    await ctx.send(embed=embed)

@bot.command(name="مكافأة")
async def daily_reward(ctx):
    """المكافأة اليومية"""
    user_data = get_member_data(ctx.author.id)
    
    # التحقق من آخر مرة استلم فيها المكافأة
    last_claimed = user_data[6]
    now = datetime.datetime.now()
    
    if last_claimed:
        last_claimed_date = datetime.datetime.fromisoformat(last_claimed)
        time_diff = now - last_claimed_date
        
        if time_diff.total_seconds() < 86400:  # أقل من 24 ساعة
            hours_left = 24 - (time_diff.total_seconds() // 3600)
            
            embed = discord.Embed(
                title="⏰ لم يحن الوقت بعد",
                description=f"يمكنك استلام المكافأة التالية بعد **{int(hours_left)}** ساعة!",
                color=COLORS["WARNING"]
            )
            
            await ctx.send(embed=embed)
            return
    
    # حساب المكافأة (500-1000 عملة)
    base_reward = 500
    bonus = random.randint(0, 500)
    total_reward = base_reward + bonus
    
    # مكافأة إضافية للمستويات العالية
    level_bonus = user_data[3] * 10
    total_reward += level_bonus
    
    # منح المكافأة
    add_coins(ctx.author.id, total_reward)
    
    # تحديث وقت آخر مكافأة
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE members SET daily_claimed = ? WHERE user_id = ?",
             (now.isoformat(), str(ctx.author.id)))
    conn.commit()
    conn.close()
    
    # رسالة النجاح
    embed = discord.Embed(
        title="🎁 مكافأة يومية",
        description=f"**مبروك {ctx.author.mention}!**\nلقد استلمت مكافأتك اليومية!",
        color=COLORS["SUCCESS"]
    )
    
    embed.add_field(name="💰 المكافأة الأساسية", value=f"{base_reward} عملة", inline=True)
    
    if bonus > 0:
        embed.add_field(name="🎰 مكافأة عشوائية", value=f"+{bonus} عملة", inline=True)
    
    if level_bonus > 0:
        embed.add_field(name="📈 مكافأة المستوى", value=f"+{level_bonus} عملة", inline=True)
    
    embed.add_field(
        name="💎 الإجمالي",
        value=f"**{total_reward}** عملة",
        inline=False
    )
    
    embed.add_field(
        name="📊 رصيدك الجديد",
        value=f"**{user_data[2] + total_reward:,}** عملة",
        inline=False
    )
    
    embed.set_footer(text="عد مرة أخرى بعد 24 ساعة للمكافأة التالية!")
    
    await ctx.send(embed=embed)

@bot.command(name="عمل")
async def work_command(ctx):
    """عمل إضافي لكسب العملات"""
    user_data = get_member_data(ctx.author.id)
    
    # التحقق من وقت آخر عمل
    last_work_key = f"last_work_{ctx.author.id}"
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT stat_value FROM stats WHERE stat_key = ?", (last_work_key,))
    result = c.fetchone()
    
    now = datetime.datetime.now()
    
    if result:
        last_work_time = datetime.datetime.fromtimestamp(result[0])
        time_diff = now - last_work_time
        
        if time_diff.total_seconds() < 3600:  # أقل من ساعة
            minutes_left = 60 - (time_diff.total_seconds() // 60)
            
            embed = discord.Embed(
                title="⏳ استرح قليلاً",
                description=f"يمكنك العمل مرة أخرى بعد **{int(minutes_left)}** دقيقة!",
                color=COLORS["WARNING"]
            )
            
            await ctx.send(embed=embed)
            conn.close()
            return
    
    # قائمة الوظائف والأجور
    jobs = [
        {"name": "👨‍💻 مبرمج", "min": 150, "max": 300, "emoji": "💻"},
        {"name": "🎨 مصمم", "min": 120, "max": 250, "emoji": "🎨"},
        {"name": "📝 كاتب محتوى", "min": 100, "max": 200, "emoji": "📝"},
        {"name": "🔧 مساعد تقني", "min": 80, "max": 180, "emoji": "🔧"},
        {"name": "🎮 مطور ألعاب", "min": 200, "max": 400, "emoji": "🎮"}
    ]
    
    job = random.choice(jobs)
    earnings = random.randint(job["min"], job["max"])
    
    # مكافأة إضافية بناءً على المستوى
    level_bonus = user_data[3] * 5
    total_earnings = earnings + level_bonus
    
    # منح الأجر
    add_coins(ctx.author.id, total_earnings)
    
    # تحديث وقت آخر عمل
    c.execute("INSERT OR REPLACE INTO stats (stat_key, stat_value, updated_at) VALUES (?, ?, ?)",
             (last_work_key, int(now.timestamp()), now.isoformat()))
    conn.commit()
    conn.close()
    
    # رسالة النجاح
    embed = discord.Embed(
        title=f"{job['emoji']} عملت كـ {job['name']}",
        description=f"**أحسنت {ctx.author.mention}!**\nلقد أكملت عملك بنجاح.",
        color=COLORS["SUCCESS"]
    )
    
    embed.add_field(name="💰 الأجر الأساسي", value=f"{earnings} عملة", inline=True)
    
    if level_bonus > 0:
        embed.add_field(name="📈 مكافأة الخبرة", value=f"+{level_bonus} عملة", inline=True)
    
    embed.add_field(
        name="💎 الإجمالي",
        value=f"**{total_earnings}** عملة",
        inline=False
    )
    
    embed.add_field(
        name="📊 رصيدك الجديد",
        value=f"**{user_data[2] + total_earnings:,}** عملة",
        inline=False
    )
    
    embed.set_footer(text="يمكنك العمل مرة أخرى بعد ساعة!")
    
    await ctx.send(embed=embed)

@bot.command(name="متجر")
async def shop_command(ctx):
    """عرض متجر البوت"""
    embed = discord.Embed(
        title="🛒 متجر البوت",
        description="**مرحباً بك في متجر البوت!**\n\n"
                   "هنا يمكنك شراء عناصر ومميزات خاصة.\n"
                   "استخدم `!شراء [رقم_العنصر]` للشراء.",
        color=COLORS["PURPLE"]
    )
    
    # العناصر الافتراضية
    default_items = [
        {
            "id": 1,
            "name": "💎 حزمة العملات الصغيرة",
            "description": "1000 عملة إضافية لحسابك",
            "price": 0,  # مجاني للعرض
            "emoji": "💰"
        },
        {
            "id": 2,
            "name": "🎁 حزمة العملات المتوسطة",
            "description": "5000 عملة إضافية لحسابك",
            "price": 1000,
            "emoji": "💰💰"
        },
        {
            "id": 3,
            "name": "🏆 حزمة العملات الكبيرة",
            "description": "10000 عملة إضافية لحسابك",
            "price": 1800,
            "emoji": "💰💰💰"
        },
        {
            "id": 4,
            "name": "👑 رتبة VIP لمدة أسبوع",
            "description": "مميزات خاصة لمدة 7 أيام",
            "price": 5000,
            "emoji": "👑"
        },
        {
            "id": 5,
            "name": "🌟 رتبة VIP لمدة شهر",
            "description": "مميزات خاصة لمدة 30 يوماً",
            "price": 15000,
            "emoji": "🌟🌟"
        },
        {
            "id": 6,
            "name": "🎨 لون مخصص للرتبة",
            "description": "اختر لوناً خاصاً لرتبتك",
            "price": 3000,
            "emoji": "🎨"
        },
        {
            "id": 7,
            "name": "🔔 إشعارات مميزة",
            "description": "إشعارات خاصة عند الفوز",
            "price": 2000,
            "emoji": "🔔"
        },
        {
            "id": 8,
            "name": "🎪 بطاقة دخول للمسابقات",
            "description": "دخول حصري للمسابقات الكبيرة",
            "price": 5000,
            "emoji": "🎪"
        }
    ]
    
    # التحقق من العناصر في قاعدة البيانات
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM shop")
    shop_items_count = c.fetchone()[0]
    
    if shop_items_count == 0:
        # إضافة العناصر الافتراضية
        for item in default_items:
            c.execute("""INSERT INTO shop 
                        (name, description, price, emoji, category) 
                        VALUES (?, ?, ?, ?, ?)""",
                     (item["name"], item["description"], item["price"], 
                      item["emoji"], "عام"))
        conn.commit()
    
    # جلب العناصر من قاعدة البيانات
    c.execute("SELECT item_id, name, description, price, emoji FROM shop ORDER BY price")
    shop_items = c.fetchall()
    conn.close()
    
    for item_id, name, description, price, emoji in shop_items:
        embed.add_field(
            name=f"{emoji} **{name}** (#{item_id})",
            value=f"{description}\n"
                  f"💰 **السعر:** {price:,} عملة\n"
                  f"📝 **الشراء:** `!شراء {item_id}`",
            inline=False
        )
    
    # معلومات الرصيد
    user_data = get_member_data(ctx.author.id)
    embed.add_field(
        name="💰 رصيدك الحالي",
        value=f"**{user_data[2]:,}** عملة",
        inline=False
    )
    
    embed.set_footer(text="اكتب !رصيدي للتحقق من رصيدك | !شراء [رقم] للشراء")
    
    await ctx.send(embed=embed)

@bot.command(name="شراء")
async def buy_command(ctx, item_id: int):
    """شراء عنصر من المتجر"""
    # التحقق من الرقم
    if item_id <= 0:
        await ctx.send("❌ رقم العنصر غير صالح!")
        return
    
    # جلب معلومات العنصر
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT item_id, name, description, price FROM shop WHERE item_id = ?", (item_id,))
    item = c.fetchone()
    
    if not item:
        await ctx.send("❌ هذا العنصر غير موجود في المتجر!")
        conn.close()
        return
    
    item_id, name, description, price = item
    
    # التحقق من الرصيد
    user_data = get_member_data(ctx.author.id)
    user_coins = user_data[2]
    
    if user_coins < price:
        embed = discord.Embed(
            title="❌ رصيد غير كافٍ",
            description=f"ليس لديك عملات كافية لشراء **{name}**!\n\n"
                       f"💰 **سعر العنصر:** {price:,} عملة\n"
                       f"💎 **رصيدك الحالي:** {user_coins:,} عملة\n"
                       f"📊 **الناقص:** {price - user_coins:,} عملة",
            color=COLORS["ERROR"]
        )
        await ctx.send(embed=embed)
        conn.close()
        return
    
    # تنفيذ الشراء
    add_coins(ctx.author.id, -price)
    
    # تسجيل الشراء
    c.execute("INSERT INTO purchases (user_id, item_id, purchased_at) VALUES (?, ?, ?)",
             (str(ctx.author.id), item_id, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    # منح المكافآت بناءً على العنصر
    if item_id == 1:  # حزمة العملات الصغيرة
        add_coins(ctx.author.id, 1000)
        bonus = 1000
    elif item_id == 2:  # حزمة العملات المتوسطة
        add_coins(ctx.author.id, 5000)
        bonus = 5000
    elif item_id == 3:  # حزمة العملات الكبيرة
        add_coins(ctx.author.id, 10000)
        bonus = 10000
    elif item_id == 4:  # VIP أسبوع
        # إضافة VIP لمدة أسبوع
        vip_conn = sqlite3.connect(DB_NAME)
        vip_c = vip_conn.cursor()
        expires_at = (datetime.datetime.now() + datetime.timedelta(days=7)).isoformat()
        vip_c.execute("INSERT OR REPLACE INTO vip_users (user_id, expires_at, purchased_at) VALUES (?, ?, ?)",
                     (str(ctx.author.id), expires_at, datetime.datetime.now().isoformat()))
        vip_conn.commit()
        vip_conn.close()
        bonus = "رتبة VIP لمدة أسبوع"
    elif item_id == 5:  # VIP شهر
        # إضافة VIP لمدة شهر
        vip_conn = sqlite3.connect(DB_NAME)
        vip_c = vip_conn.cursor()
        expires_at = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
        vip_c.execute("INSERT OR REPLACE INTO vip_users (user_id, expires_at, purchased_at) VALUES (?, ?, ?)",
                     (str(ctx.author.id), expires_at, datetime.datetime.now().isoformat()))
        vip_conn.commit()
        vip_conn.close()
        bonus = "رتبة VIP لمدة شهر"
    else:
        bonus = "العنصر المختار"
    
    # رسالة النجاح
    embed = discord.Embed(
        title="✅ شراء ناجح",
        description=f"**أحسنت {ctx.author.mention}!**\n"
                   f"لقد اشتريت **{name}** بنجاح.",
        color=COLORS["SUCCESS"]
    )
    
    embed.add_field(name="📦 العنصر", value=name, inline=True)
    embed.add_field(name="💰 السعر", value=f"{price:,} عملة", inline=True)
    
    if isinstance(bonus, int):
        embed.add_field(name="🎁 المكافأة", value=f"+{bonus:,} عملة", inline=True)
    else:
        embed.add_field(name="🎁 المكافأة", value=bonus, inline=True)
    
    embed.add_field(
        name="📊 رصيدك الجديد",
        value=f"**{user_data[2] - price + (bonus if isinstance(bonus, int) else 0):,}** عملة",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name="معلومات")
async def server_info_command(ctx):
    """معلومات السيرفر"""
    guild = ctx.guild
    
    embed = discord.Embed(
        title=f"📊 معلومات السيرفر: {guild.name}",
        color=COLORS["BLUE"]
    )
    
    # المعلومات الأساسية
    embed.add_field(name="👑 المالك", value=guild.owner.mention, inline=True)
    embed.add_field(name="🆔 الرقم", value=guild.id, inline=True)
    embed.add_field(name="📅 تاريخ الإنشاء", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    
    # إحصائيات الأعضاء
    total_members = guild.member_count
    online_members = len([m for m in guild.members if m.status != discord.Status.offline])
    bot_count = len([m for m in guild.members if m.bot])
    human_count = total_members - bot_count
    
    embed.add_field(name="👥 إجمالي الأعضاء", value=total_members, inline=True)
    embed.add_field(name="🟢 الأعضاء النشطين", value=online_members, inline=True)
    embed.add_field(name="🤖 عدد البوتات", value=bot_count, inline=True)
    
    # إحصائيات القنوات
    text_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
    voice_channels = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
    categories = len([c for c in guild.channels if isinstance(c, discord.CategoryChannel)])
    
    embed.add_field(name="📝 القنوات النصية", value=text_channels, inline=True)
    embed.add_field(name="🎤 القنوات الصوتية", value=voice_channels, inline=True)
    embed.add_field(name="📁 الأقسام", value=categories, inline=True)
    
    # إحصائيات الرتب
    roles = len(guild.roles)
    embed.add_field(name="🎭 عدد الرتب", value=roles, inline=True)
    
    # مستوى التعزيز
    if guild.premium_tier > 0:
        embed.add_field(name="🌟 مستوى التعزيز", value=guild.premium_tier, inline=True)
        embed.add_field(name="💎 عدد المعززين", value=guild.premium_subscription_count, inline=True)
    
    # إحصائيات من قاعدة البيانات
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM members")
    bot_members = c.fetchone()[0]
    
    c.execute("SELECT SUM(coins) FROM members")
    total_coins = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(messages) FROM members")
    total_messages = c.fetchone()[0] or 0
    
    conn.close()
    
    embed.add_field(
        name="🤖 إحصائيات البوت",
        value=f"**المستخدمون المسجلون:** {bot_members}\n"
              f"**إجمالي العملات:** {total_coins:,}\n"
              f"**إجمالي الرسائل:** {total_messages:,}",
        inline=False
    )
    
    # معلومات البوت
    embed.add_field(
        name="⚙️ معلومات البوت",
        value=f"**اسم البوت:** {bot.user.name}\n"
              f"**رقم البوت:** {bot.user.id}\n"
              f"**وقت التشغيل:** {len(bot.guilds)} سيرفر\n"
              f"**السرعة:** {round(bot.latency * 1000)}ms",
        inline=False
    )
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    if guild.banner:
        embed.set_image(url=guild.banner.url)
    
    embed.set_footer(text=f"طلب بواسطة: {ctx.author.name} | التاريخ: {datetime.datetime.now().strftime('%Y-%m-%d')}")
    
    await ctx.send(embed=embed)

@bot.command(name="معلوماتي")
async def my_info_command(ctx, member: discord.Member = None):
    """معلومات العضو"""
    target_member = member or ctx.author
    
    user_data = get_member_data(target_member.id)
    
    embed = discord.Embed(
        title=f"👤 معلومات {target_member.display_name}",
        color=target_member.color
    )
    
    # المعلومات الأساسية
    embed.add_field(name="🆔 الرقم", value=target_member.id, inline=True)
    embed.add_field(name="📛 الاسم الكامل", value=target_member.display_name, inline=True)
    embed.add_field(name="📅 تاريخ إنشاء الحساب", value=target_member.created_at.strftime("%Y-%m-%d"), inline=True)
    
    # معلومات السيرفر
    embed.add_field(name="📅 تاريخ الانضمام", value=target_member.joined_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="🎭 أعلى رتبة", value=target_member.top_role.mention, inline=True)
    
    # نظام البوت
    embed.add_field(name="💰 العملات", value=f"{user_data[2]:,} عملة", inline=True)
    embed.add_field(name="📈 المستوى", value=user_data[3], inline=True)
    embed.add_field(name="⚡ الخبرة", value=f"{user_data[4]}/{user_data[3]*100}", inline=True)
    embed.add_field(name="⚠️ التحذيرات", value=user_data[5], inline=True)
    embed.add_field(name="📨 الرسائل", value=user_data[8], inline=True)
    
    # الرتب
    roles = [role for role in target_member.roles if role.name != "@everyone"]
    if roles:
        roles_text = " ".join([role.mention for role in roles[:5]])
        if len(roles) > 5:
            roles_text += f" و{len(roles)-5} أكثر..."
        
        embed.add_field(
            name=f"🎭 الرتب ({len(roles)})",
            value=roles_text,
            inline=False
        )
    
    # الأوسمة (إذا كان معزز)
    if target_member.premium_since:
        premium_days = (datetime.datetime.now() - target_member.premium_since).days
        embed.add_field(
            name="🌟 معزز السيرفر",
            value=f"منذ {premium_days} يوم",
            inline=True
        )
    
    # التحقق من VIP
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT expires_at FROM vip_users WHERE user_id = ?", (str(target_member.id),))
    vip_data = c.fetchone()
    conn.close()
    
    if vip_data:
        expires_at = datetime.datetime.fromisoformat(vip_data[0])
        days_left = (expires_at - datetime.datetime.now()).days
        if days_left > 0:
            embed.add_field(
                name="👑 عضو VIP",
                value=f"متبقي {days_left} يوم",
                inline=True
            )
    
    # شريط التقدم
    progress = int((user_data[4] / (user_data[3] * 100)) * 20)
    progress_bar = "█" * progress + "░" * (20 - progress)
    embed.add_field(
        name=f"📊 تقدم المستوى ({int((user_data[4] / (user_data[3] * 100)) * 100)}%)",
        value=f"```{progress_bar}```",
        inline=False
    )
    
    # إحصائيات إضافية
    embed.add_field(
        name="📊 الإنجازات",
        value=f"{'🌟' * min(user_data[3] // 5, 5)}",
        inline=True
    )
    
    embed.set_thumbnail(url=target_member.avatar.url if target_member.avatar else target_member.default_avatar.url)
    embed.set_footer(text=f"آخر تحديث: {datetime.datetime.now().strftime('%H:%M')}")
    
    await ctx.send(embed=embed)

@bot.command(name="سيرفر")
async def server_stats_command(ctx):
    """إحصائيات السيرفر التفصيلية"""
    guild = ctx.guild
    
    embed = discord.Embed(
        title=f"📈 إحصائيات {guild.name}",
        color=COLORS["PURPLE"]
    )
    
    # قسم الأعضاء
    members = guild.members
    online = len([m for m in members if m.status != discord.Status.offline])
    idle = len([m for m in members if m.status == discord.Status.idle])
    dnd = len([m for m in members if m.status == discord.Status.dnd])
    offline = len([m for m in members if m.status == discord.Status.offline])
    bots = len([m for m in members if m.bot])
    humans = len(members) - bots
    
    embed.add_field(
        name="👥 **تفاصيل الأعضاء**",
        value=f"""**الإجمالي:** {len(members)}
**البشر:** {humans}
**البوتات:** {bots}

**🟢 متصلون:** {online}
**🌙 غير نشطين:** {idle}
**⛔ مشغولون:** {dnd}
**⚫ غير متصلين:** {offline}

**📊 النسبة:** {int((online/len(members))*100)}% نشطين""",
        inline=False
    )
    
    # قسم القنوات
    text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
    voice_channels = [c for c in guild.channels if isinstance(c, discord.VoiceChannel)]
    categories = [c for c in guild.channels if isinstance(c, discord.CategoryChannel)]
    
    embed.add_field(
        name="📁 **تفاصيل القنوات**",
        value=f"""**القنوات النصية:** {len(text_channels)}
**القنوات الصوتية:** {len(voice_channels)}
**الأقسام:** {len(categories)}
**الإجمالي:** {len(guild.channels)}

**🔒 المقيدة:** {len([c for c in guild.channels if c.overwrites])}
**📢 الإعلانات:** {len([c for c in text_channels if 'announcement' in c.name.lower()])}
**🎮 الألعاب:** {len([c for c in text_channels if 'game' in c.name.lower()])}""",
        inline=False
    )
    
    # قسم الرتب
    roles = guild.roles
    embed.add_field(
        name="🎭 **تفاصيل الرتب**",
        value=f"""**عدد الرتب:** {len(roles)}
**أعلى رتبة:** {roles[-1].mention if roles else "لا يوجد"}
**أدنى رتبة:** {roles[0].mention if roles else "لا يوجد"}

**🔝 الرتب العليا:** {len([r for r in roles if r.position > 10])}
**📊 الرتب المتوسطة:** {len([r for r in roles if 5 <= r.position <= 10])}
**🔽 الرتب المنخفضة:** {len([r for r in roles if r.position < 5])}

**🎨 الألوان المميزة:** {len([r for r in roles if r.color.value != 0])}""",
        inline=False
    )
    
    # قسم التعزيز
    if guild.premium_tier > 0:
        embed.add_field(
            name="🌟 **تفاصيل التعزيز**",
            value=f"""**المستوى:** {guild.premium_tier}
**عدد المعززين:** {guild.premium_subscription_count}
**إجمالي التعزيزات:** {guild.premium_subscription_count * 2} شهر

**🎁 المميزات:**
• جودة صوت: {['غير متاحة', '128kbps', '256kbps', '384kbps'][guild.premium_tier]}
• رفع الملفات: {['8MB', '8MB', '50MB', '100MB'][guild.premium_tier]}
• إيموجيات متحركة: {'✅' if guild.premium_tier >= 2 else '❌'}
• خلفية السيرفر: {'✅' if guild.premium_tier >= 2 else '❌'}""",
            inline=False
        )
    
    # إحصائيات البوت
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM members")
    bot_users = c.fetchone()[0]
    
    c.execute("SELECT SUM(coins) FROM members")
    total_coins = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(messages) FROM members")
    total_messages = c.fetchone()[0] or 0
    
    c.execute("SELECT COUNT(*) FROM games")
    total_games = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'")
    open_tickets = c.fetchone()[0]
    
    conn.close()
    
    embed.add_field(
        name="🤖 **إحصائيات البوت**",
        value=f"""**المستخدمون المسجلون:** {bot_users}
**إجمالي العملات:** {total_coins:,}
**إجمالي الرسائل:** {total_messages:,}
**إجمالي الألعاب:** {total_games:,}
**التذاكر المفتوحة:** {open_tickets}

**📈 المتوسطات:**
• متوسط العملات: {total_coins//bot_users if bot_users > 0 else 0:,}
• متوسط الرسائل: {total_messages//bot_users if bot_users > 0 else 0:,}
• الألعاب لكل مستخدم: {total_games//bot_users if bot_users > 0 else 0:,}""",
        inline=False
    )
    
    # المعلومات العامة
    server_age = (datetime.datetime.now() - guild.created_at).days
    embed.add_field(
        name="📅 **المعلومات العامة**",
        value=f"""**عمر السيرفر:** {server_age} يوم
**المنطقة:** {str(guild.region).title()}
**التحقق:** {'✅' if guild.verified else '❌'}
**الشريك:** {'✅' if guild.partnered else '❌'}

**📋 القوانين:** {'✅' if guild.rules_channel else '❌'}
**👋 الترحيب:** {'✅' if guild.system_channel else '❌'}
**📢 الإعلانات:** {'✅' if guild.public_updates_channel else '❌'}""",
        inline=False
    )
    
    embed.set_footer(text=f"آخر تحديث: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    await ctx.send(embed=embed)

@bot.command(name="بانر")
async def banner_command(ctx, member: discord.Member = None):
    """إنشاء بانر شخصي مخصص"""
    target_member = member or ctx.author
    
    user_data = get_member_data(target_member.id)
    
    # إنشاء بانر فني
    embed = discord.Embed(
        title=f"🎨 بانر {target_member.display_name}",
        color=target_member.color
    )
    
    # إحصائيات مفصلة
    stats = f"""
    **📊 الإحصائيات الأساسية:**
    💰 **العملات:** {user_data[2]:,}
    📈 **المستوى:** {user_data[3]}
    ⚡ **الخبرة:** {user_data[4]}/{user_data[3]*100}
    📨 **الرسائل:** {user_data[8]:,}
    
    **🏆 الإنجازات:**
    🎯 **النشاط:** {'🌟🌟🌟' if user_data[8] > 1000 else '🌟🌟' if user_data[8] > 500 else '🌟'}
    💎 **الثروة:** {'💰💰💰' if user_data[2] > 5000 else '💰💰' if user_data[2] > 2000 else '💰'}
    🏅 **الخبرة:** {'👑' if user_data[3] > 10 else '⭐' if user_data[3] > 5 else '✨'}
    📚 **المعرفة:** {'🧠🧠🧠' if user_data[4] > 500 else '🧠🧠' if user_data[4] > 200 else '🧠'}
    """
    
    embed.description = stats
    
    # شريط التقدم
    progress = int((user_data[4] / (user_data[3] * 100)) * 30)
    progress_bar = "█" * progress + "░" * (30 - progress)
    embed.add_field(
        name=f"📊 تقدم المستوى ({int((user_data[4] / (user_data[3] * 100)) * 100)}%)",
        value=f"```{progress_bar}```",
        inline=False
    )
    
    # معلومات إضافية
    join_days = (datetime.datetime.now() - target_member.joined_at).days
    account_age = (datetime.datetime.now() - target_member.created_at).days
    
    embed.add_field(
        name="📅 المعلومات الزمنية",
        value=f"**مدة العضوية:** {join_days} يوم\n"
              f"**عمر الحساب:** {account_age} يوم\n"
              f"**نسبة النشاط:** {min(100, (user_data[8] / max(1, join_days)) * 10):.1f}%",
        inline=True
    )
    
    # الرتب
    roles = [role for role in target_member.roles if role.name != "@everyone"]
    embed.add_field(
        name=f"🎭 الرتب ({len(roles)})",
        value=f"أعلى رتبة: {target_member.top_role.mention}" if roles else "لا توجد رتب",
        inline=True
    )
    
    # التحقق من المركز
    leaderboard = get_leaderboard(100)
    rank = None
    for i, (user_id, _, _) in enumerate(leaderboard, 1):
        if user_id == str(target_member.id):
            rank = i
            break
    
    if rank:
        embed.add_field(
            name="🏅 المركز العالمي",
            value=f"**الترتيب:** #{rank}\n"
                  f"**فوقك:** {rank-1} لاعب\n"
                  f"**تحتك:** {len(leaderboard)-rank} لاعب",
            inline=True
        )
    
    # تصميم البانر
    if rank and rank <= 3:
        rank_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
        embed.add_field(
            name=f"{rank_emojis[rank]} تصنيف متميز!",
            value="أنت من أفضل اللاعبين في السيرفر!",
            inline=False
        )
    
    if user_data[3] >= 10:
        embed.add_field(
            name="👑 محارب قديم",
            value="وصلت للمستوى 10! أنت من المخضرمين.",
            inline=False
        )
    
    if user_data[2] >= 10000:
        embed.add_field(
            name="💎 مليونير",
            value="وصلت لـ 10,000 عملة! أنت من الأغنياء.",
            inline=False
        )
    
    # تخصيص البانر حسب المستوى
    if user_data[3] >= 20:
        banner_style = "✨ **بطل أسطوري** ✨"
    elif user_data[3] >= 15:
        banner_style = "🌟 **محارب متقدم** 🌟"
    elif user_data[3] >= 10:
        banner_style = "⭐ **مقاتل متمرس** ⭐"
    elif user_data[3] >= 5:
        banner_style = "🎯 **مبتدئ نشط** 🎯"
    else:
        banner_style = "🌱 **مبتدئ واعد** 🌱"
    
    embed.add_field(
        name="🎪 نمط البانر",
        value=banner_style,
        inline=False
    )
    
    embed.set_thumbnail(url=target_member.avatar.url if target_member.avatar else target_member.default_avatar.url)
    embed.set_footer(text="تابع التقدم لتحصل على بانر أفضل!")
    
    await ctx.send(embed=embed)

@bot.command(name="أفاتار")
async def avatar_command(ctx, member: discord.Member = None):
    """عرض صورة البروفايل"""
    target_member = member or ctx.author
    
    embed = discord.Embed(
        title=f"🖼️ أفاتار {target_member.display_name}",
        color=target_member.color
    )
    
    avatar_url = target_member.avatar.url if target_member.avatar else target_member.default_avatar.url
    
    embed.set_image(url=avatar_url)
    
    embed.add_field(name="📛 الاسم", value=target_member.display_name, inline=True)
    embed.add_field(name="🆔 الرقم", value=target_member.id, inline=True)
    
    if target_member.avatar:
        embed.add_field(
            name="🔗 الروابط",
            value=f"[الرابط المباشر]({avatar_url})",
            inline=True
        )
    
    embed.set_footer(text=f"طلب بواسطة: {ctx.author.name}")
    
    await ctx.send(embed=embed)

# ========== أوامر الإدارة ==========
@bot.command(name="مسح")
@commands.has_permissions(manage_messages=True)
async def clear_command(ctx, amount: int = 10):
    """مسح الرسائل"""
    if amount <= 0:
        await ctx.send("❌ الرقم يجب أن يكون أكبر من صفر!")
        return
    
    if amount > 100:
        await ctx.send("❌ الحد الأقصى لمسح الرسائل هو 100!")
        return
    
    deleted = await ctx.channel.purge(limit=amount + 1)
    
    embed = discord.Embed(
        title="🧹 تنظيف الرسائل",
        description=f"✅ تم مسح **{len(deleted)-1}** رسالة بنجاح!",
        color=COLORS["SUCCESS"]
    )
    
    embed.add_field(
        name="📝 التفاصيل",
        value=f"**القناة:** {ctx.channel.mention}\n"
              f"**المسؤول:** {ctx.author.mention}\n"
              f"**الوقت:** {datetime.datetime.now().strftime('%H:%M')}",
        inline=False
    )
    
    msg = await ctx.send(embed=embed)
    await asyncio.sleep(3)
    await msg.delete()

@bot.command(name="تحذير")
@commands.has_permissions(manage_messages=True)
async def warn_command(ctx, member: discord.Member, *, reason="بدون سبب"):
    """تحذير عضو"""
    warning_count = add_warning(member.id, ctx.author.id, reason)
    
    embed = discord.Embed(
        title="⚠️ تحذير جديد",
        color=COLORS["WARNING"]
    )
    
    embed.add_field(name="👤 العضو", value=member.mention, inline=True)
    embed.add_field(name="🛡️ المسؤول", value=ctx.author.mention, inline=True)
    embed.add_field(name="📝 السبب", value=reason, inline=False)
    embed.add_field(name="🔢 عدد التحذيرات", value=f"{warning_count}/5", inline=True)
    
    # إجراءات تلقائية بناءً على عدد التحذيرات
    if warning_count >= 5:
        embed.add_field(
            name="🚨 إجراء تلقائي",
            value="تم حظر العضو تلقائياً لمدة 24 ساعة!",
            inline=False
        )
        
        try:
            await member.timeout(
                datetime.timedelta(hours=24),
                reason="تجاوز الحد الأقصى للتحذيرات"
            )
        except:
            embed.add_field(
                name="❌ تحذير",
                value="لا يمكنني تطبيق التايم آوت على هذا العضو",
                inline=False
            )
    elif warning_count >= 3:
        embed.add_field(
            name="⚠️ تنبيه",
            value="تحذيرين إضافيين وسيتم حظره تلقائياً!",
            inline=False
        )
    
    await ctx.send(embed=embed)
    
    # إرسال تنبيه للعضو
    try:
        dm_embed = discord.Embed(
            title="⚠️ لقد تلقيت تحذيراً",
            description=f"في سيرفر: **{ctx.guild.name}**",
            color=COLORS["WARNING"]
        )
        
        dm_embed.add_field(name="📝 السبب", value=reason, inline=False)
        dm_embed.add_field(name="🔢 عدد التحذيرات", value=f"{warning_count}/5", inline=False)
        dm_embed.add_field(name="🛡️ المسؤول", value=ctx.author.name, inline=False)
        
        if warning_count >= 5:
            dm_embed.add_field(
                name="🚨 عقوبة",
                value="لقد تم حظرك لمدة 24 ساعة بسبب تجاوز الحد الأقصى للتحذيرات.",
                inline=False
            )
        
        await member.send(embed=dm_embed)
    except:
        pass

@bot.command(name="تحذيرات")
@commands.has_permissions(manage_messages=True)
async def warnings_command(ctx, member: discord.Member):
    """عرض تحذيرات العضو"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("SELECT reason, timestamp FROM warnings WHERE user_id = ? AND status = 'active' ORDER BY timestamp DESC",
             (str(member.id),))
    warnings = c.fetchall()
    
    c.execute("SELECT warnings FROM members WHERE user_id = ?", (str(member.id),))
    total_warnings = c.fetchone()[0]
    
    conn.close()
    
    embed = discord.Embed(
        title=f"⚠️ تحذيرات {member.display_name}",
        color=COLORS["WARNING"]
    )
    
    embed.add_field(name="👤 العضو", value=member.mention, inline=True)
    embed.add_field(name="🔢 الإجمالي", value=total_warnings, inline=True)
    
    if warnings:
        warnings_text = ""
        for i, (reason, timestamp) in enumerate(warnings[:10], 1):
            time = datetime.datetime.fromisoformat(timestamp).strftime("%Y-%m-%d %H:%M")
            warnings_text += f"**{i}.** {reason} - {time}\n"
        
        embed.add_field(name="📝 آخر 10 تحذيرات", value=warnings_text, inline=False)
    else:
        embed.add_field(name="📝 التحذيرات", value="لا توجد تحذيرات نشطة", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name="إزالة_تحذير")
@commands.has_permissions(manage_messages=True)
async def remove_warning_command(ctx, member: discord.Member, warning_id: int = None):
    """إزالة تحذير من العضو"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    if warning_id:
        # إزالة تحذير محدد
        c.execute("UPDATE warnings SET status = 'removed' WHERE id = ? AND user_id = ?",
                 (warning_id, str(member.id)))
        removed = c.rowcount
        
        if removed > 0:
            c.execute("UPDATE members SET warnings = warnings - 1 WHERE user_id = ?", (str(member.id),))
    else:
        # إزالة آخر تحذير
        c.execute("SELECT id FROM warnings WHERE user_id = ? AND status = 'active' ORDER BY timestamp DESC LIMIT 1",
                 (str(member.id),))
        last_warning = c.fetchone()
        
        if last_warning:
            c.execute("UPDATE warnings SET status = 'removed' WHERE id = ?", (last_warning[0],))
            c.execute("UPDATE members SET warnings = warnings - 1 WHERE user_id = ?", (str(member.id),))
            removed = 1
        else:
            removed = 0
    
    conn.commit()
    
    c.execute("SELECT warnings FROM members WHERE user_id = ?", (str(member.id),))
    remaining_warnings = c.fetchone()[0]
    
    conn.close()
    
    if removed > 0:
        embed = discord.Embed(
            title="✅ تمت إزالة التحذير",
            description=f"تمت إزالة تحذير من {member.mention}",
            color=COLORS["SUCCESS"]
        )
        
        embed.add_field(name="👤 العضو", value=member.mention, inline=True)
        embed.add_field(name="🛡️ المسؤول", value=ctx.author.mention, inline=True)
        embed.add_field(name="🔢 التحذيرات المتبقية", value=remaining_warnings, inline=True)
    else:
        embed = discord.Embed(
            title="❌ خطأ",
            description=f"لا توجد تحذيرات نشطة لـ {member.mention}",
            color=COLORS["ERROR"]
        )
    
    await ctx.send(embed=embed)

@bot.command(name="تأديب")
@commands.has_permissions(manage_messages=True)
async def timeout_command(ctx, member: discord.Member, duration: str, *, reason="بدون سبب"):
    """تايم آوت للعضو"""
    # تحويل المدة إلى ثواني
    time_units = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400
    }
    
    unit = duration[-1].lower()
    if unit not in time_units:
        await ctx.send("❌ وحدة الوقت غير صحيحة! استخدم: s, m, h, d")
        return
    
    try:
        amount = int(duration[:-1])
        seconds = amount * time_units[unit]
        
        if seconds > 2419200:  # 28 يوم الحد الأقصى في ديسكورد
            await ctx.send("❌ الحد الأقصى للتايم آوت هو 28 يوم!")
            return
        
        # تطبيق التايم آوت
        await member.timeout(
            datetime.timedelta(seconds=seconds),
            reason=f"{reason} | بواسطة: {ctx.author}"
        )
        
        # رسالة النجاح
        embed = discord.Embed(
            title="⏸️ تايم آوت",
            description=f"تم تطبيق تايم آوت على {member.mention}",
            color=COLORS["WARNING"]
        )
        
        time_names = {"s": "ثانية", "m": "دقيقة", "h": "ساعة", "d": "يوم"}
        
        embed.add_field(name="👤 العضو", value=member.mention, inline=True)
        embed.add_field(name="⏱️ المدة", value=f"{amount} {time_names[unit]}", inline=True)
        embed.add_field(name="📝 السبب", value=reason, inline=False)
        embed.add_field(name="🛡️ المسؤول", value=ctx.author.mention, inline=True)
        
        # إرسال تنبيه للعضو
        try:
            dm_embed = discord.Embed(
                title="⏸️ لقد تم تأديبك",
                description=f"في سيرفر: **{ctx.guild.name}**",
                color=COLORS["WARNING"]
            )
            
            dm_embed.add_field(name="⏱️ المدة", value=f"{amount} {time_names[unit]}", inline=True)
            dm_embed.add_field(name="📝 السبب", value=reason, inline=False)
            dm_embed.add_field(name="🛡️ المسؤول", value=ctx.author.name, inline=False)
            
            await member.send(embed=dm_embed)
        except:
            pass
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ حدث خطأ: {e}")

@bot.command(name="كيك")
@commands.has_permissions(kick_members=True)
async def kick_command(ctx, member: discord.Member, *, reason="بدون سبب"):
    """طرد عضو من السيرفر"""
    if member == ctx.author:
        await ctx.send("❌ لا يمكنك طرد نفسك!")
        return
    
    if member.guild_permissions.administrator:
        await ctx.send("❌ لا يمكنك طرد مشرف!")
        return
    
    try:
        await member.kick(reason=f"{reason} | بواسطة: {ctx.author}")
        
        embed = discord.Embed(
            title="👢 طرد عضو",
            description=f"تم طرد {member.mention} من السيرفر",
            color=COLORS["ERROR"]
        )
        
        embed.add_field(name="👤 العضو", value=member.name, inline=True)
        embed.add_field(name="🆔 الرقم", value=member.id, inline=True)
        embed.add_field(name="📝 السبب", value=reason, inline=False)
        embed.add_field(name="🛡️ المسؤول", value=ctx.author.mention, inline=True)
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ حدث خطأ: {e}")

@bot.command(name="بان")
@commands.has_permissions(ban_members=True)
async def ban_command(ctx, member: discord.Member, *, reason="بدون سبب"):
    """حظر عضو من السيرفر"""
    if member == ctx.author:
        await ctx.send("❌ لا يمكنك حظر نفسك!")
        return
    
    if member.guild_permissions.administrator:
        await ctx.send("❌ لا يمكنك حظر مشرف!")
        return
    
    try:
        await member.ban(reason=f"{reason} | بواسطة: {ctx.author}", delete_message_days=0)
        
        embed = discord.Embed(
            title="🔒 حظر عضو",
            description=f"تم حظر {member.mention} من السيرفر",
            color=COLORS["ERROR"]
        )
        
        embed.add_field(name="👤 العضو", value=member.name, inline=True)
        embed.add_field(name="🆔 الرقم", value=member.id, inline=True)
        embed.add_field(name="📝 السبب", value=reason, inline=False)
        embed.add_field(name="🛡️ المسؤول", value=ctx.author.mention, inline=True)
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ حدث خطأ: {e}")

# ========== نظام التذاكر ==========
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🎫 فتح تذكرة", style=discord.ButtonStyle.green, custom_id="open_ticket")
    async def open_ticket_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        
        # التحقق من وجود تذكرة مفتوحة
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT ticket_id FROM tickets WHERE user_id = ? AND status = 'open'", (str(interaction.user.id),))
        existing_ticket = c.fetchone()
        conn.close()
        
        if existing_ticket:
            await interaction.followup.send("❌ لديك تذكرة مفتوحة بالفعل!", ephemeral=True)
            return
        
        # إنشاء تذكرة جديدة
        ticket_id = f"TICKET-{random.randint(1000, 9999)}"
        
        # البحث عن قسم التذاكر
        category = discord.utils.get(interaction.guild.categories, name="🎫 التذاكر")
        
        if not category:
            # إنشاء قسم جديد
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                interaction.guild.owner: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            # إضافة صلاحيات للمشرفين
            for role in interaction.guild.roles:
                if role.permissions.administrator or role.permissions.manage_channels:
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            category = await interaction.guild.create_category(
                "🎫 التذاكر",
                overwrites=overwrites
            )
        
        # إنشاء قناة التذكرة
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # إضافة صلاحيات للمشرفين
        for role in interaction.guild.roles:
            if role.permissions.administrator or role.permissions.manage_channels:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        ticket_channel = await interaction.guild.create_text_channel(
            name=f"تذكرة-{interaction.user.name}-{ticket_id[-4:]}",
            category=category,
            overwrites=overwrites,
            topic=f"تذكرة دعم لـ {interaction.user.mention} | ID: {ticket_id}"
        )
        
        # حفظ التذكرة في قاعدة البيانات
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO tickets (ticket_id, user_id, channel_id, created_at) VALUES (?, ?, ?, ?)",
                 (ticket_id, str(interaction.user.id), str(ticket_channel.id), datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        # رسالة الترحيب في التذكرة
        embed = discord.Embed(
            title="🎫 تذكرة دعم فني",
            description=f"**مرحباً {interaction.user.mention}!**\n\n"
                       f"شكراً لفتحك تذكرة دعم. فريق الدعم سيساعدك في أقرب وقت ممكن.",
            color=COLORS["INFO"]
        )
        
        embed.add_field(name="🆔 رقم التذكرة", value=ticket_id, inline=True)
        embed.add_field(name="📅 تاريخ الإنشاء", value=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), inline=True)
        embed.add_field(name="👤 المستخدم", value=interaction.user.mention, inline=True)
        
        embed.add_field(
            name="📝 التعليمات",
            value="""1. صف مشكلتك بوضوح
2. أرفق صور أو ملفات إذا لزم الأمر
3. انتظر رد فريق الدعم
4. لا تتردد في طرح أي أسئلة""",
            inline=False
        )
        
        embed.add_field(
            name="⏱️ وقت الاستجابة",
            value="عادةً خلال 24 ساعة",
            inline=True
        )
        
        embed.add_field(
            name="📞 الدعم",
            value="سيقوم أحد المشرفين بالرد عليك قريباً",
            inline=True
        )
        
        # زر إغلاق التذكرة
        close_view = View()
        close_button = Button(label="🔒 إغلاق التذكرة", style=discord.ButtonStyle.red, custom_id="close_ticket")
        
        async def close_callback(interaction: discord.Interaction):
            if any(role.permissions.manage_channels for role in interaction.user.roles):
                await interaction.response.send_message("🔒 جاري إغلاق التذكرة...")
                
                # تحديث حالة التذكرة
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("UPDATE tickets SET status = 'closed', closed_at = ?, closed_by = ? WHERE ticket_id = ?",
                         (datetime.datetime.now().isoformat(), str(interaction.user.id), ticket_id))
                conn.commit()
                conn.close()
                
                await asyncio.sleep(2)
                await interaction.channel.delete()
            else:
                await interaction.response.send_message("❌ ليس لديك صلاحية إغلاق التذاكر!", ephemeral=True)
        
        close_button.callback = close_callback
        close_view.add_item(close_button)
        
        await ticket_channel.send(embed=embed, view=close_view)
        await interaction.followup.send(f"✅ تم إنشاء تذكرة الدعم: {ticket_channel.mention}", ephemeral=True)

@bot.command(name="لوحة_التذاكر")
@commands.has_permissions(manage_channels=True)
async def ticket_panel_command(ctx):
    """إنشاء لوحة التذاكر"""
    embed = discord.Embed(
        title="🎫 لوحة التذاكر",
        description="**انقر على الزر لفتح تذكرة دعم فني:**\n\n"
                   "• 🛠️ مشاكل تقنية\n"
                   "• ❓ استفسارات عامة\n"
                   "• 🐛 إبلاغ عن أخطاء\n"
                   "• 💡 اقتراحات وتحسينات\n"
                   "• ⚠️ شكاوى ومشاكل",
        color=COLORS["INFO"]
    )
    
    embed.add_field(
        name="📌 التعليمات",
        value="1. اختر نوع المشكلة\n"
              "2. انتظر رد المسؤول\n"
              "3. قدم التفاصيل اللازمة\n"
              "4. أرفق الصور إذا لزم الأمر",
        inline=False
    )
    
    embed.add_field(
        name="⏱️ وقت الاستجابة",
        value="24 ساعة كحد أقصى",
        inline=True
    )
    
    embed.add_field(
        name="📞 الدعم",
        value="@المسؤولين",
        inline=True
    )
    
    embed.set_footer(text="سيتم إنشاء قناة خاصة لك للدعم")
    
    await ctx.send(embed=embed, view=TicketView())

@bot.command(name="تذاكري")
async def my_tickets_command(ctx):
    """عرض التذاكر المفتوحة"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("SELECT ticket_id, channel_id, created_at, status FROM tickets WHERE user_id = ? ORDER BY created_at DESC",
             (str(ctx.author.id),))
    tickets = c.fetchall()
    conn.close()
    
    if not tickets:
        embed = discord.Embed(
            title="🎫 تذاكري",
            description="لا توجد تذاكر مفتوحة.",
            color=COLORS["INFO"]
        )
        await ctx.send(embed=embed)
        return
    
    embed = discord.Embed(
        title=f"🎫 تذاكري ({len(tickets)})",
        color=COLORS["INFO"]
    )
    
    open_tickets = []
    closed_tickets = []
    
    for ticket_id, channel_id, created_at, status in tickets:
        ticket_info = f"**🆔:** {ticket_id}\n**📅:** {datetime.datetime.fromisoformat(created_at).strftime('%Y-%m-%d')}\n"
        
        if status == 'open':
            try:
                channel = ctx.guild.get_channel(int(channel_id))
                if channel:
                    ticket_info += f"**📁:** {channel.mention}"
                open_tickets.append(ticket_info)
            except:
                open_tickets.append(ticket_info)
        else:
            closed_tickets.append(ticket_info)
    
    if open_tickets:
        embed.add_field(
            name="🟢 التذاكر المفتوحة",
            value="\n\n".join(open_tickets[:5]),
            inline=False
        )
    
    if closed_tickets:
        embed.add_field(
            name="🔴 التذاكر المغلقة",
            value="\n\n".join(closed_tickets[:3]),
            inline=False
        )
    
    if len(tickets) > 8:
        embed.set_footer(text=f"عرض {min(8, len(tickets))} من {len(tickets)} تذكرة")
    
    await ctx.send(embed=embed)

# ========== أوامر الإعدادات ==========
@bot.command(name="إعدادات")
@commands.has_permissions(administrator=True)
async def settings_command(ctx):
    """إعدادات البوت والسيرفر"""
    embed = discord.Embed(
        title="⚙️ إعدادات البوت والسيرفر",
        description="**الإعدادات الحالية:**",
        color=COLORS["PURPLE"]
    )
    
    # معلومات السيرفر
    embed.add_field(
        name="🏰 معلومات السيرفر",
        value=f"**الاسم:** {ctx.guild.name}\n"
              f"**المالك:** {ctx.guild.owner.mention}\n"
              f"**الأعضاء:** {ctx.guild.member_count}\n"
              f"**تاريخ الإنشاء:** {ctx.guild.created_at.strftime('%Y-%m-%d')}",
        inline=False
    )
    
    # إحصائيات البوت
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM members")
    bot_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'")
    open_tickets = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM games")
    total_games = c.fetchone()[0]
    
    conn.close()
    
    embed.add_field(
        name="🤖 إحصائيات البوت",
        value=f"**المستخدمون:** {bot_users}\n"
              f"**الألعاب المنفذة:** {total_games}\n"
              f"**التذاكر المفتوحة:** {open_tickets}\n"
              f"**السيرفرات:** {len(bot.guilds)}",
        inline=False
    )
    
    # معلومات النظام
    embed.add_field(
        name="⚡ معلومات النظام",
        value=f"**اللغة:** Python 3\n"
              f"**مكتبة:** discord.py {discord.__version__}\n"
              f"**السرعة:** {round(bot.latency * 1000)}ms\n"
              f"**وقت التشغيل:** {len(bot.guilds)} سيرفر",
        inline=False
    )
    
    # الأوامر المتاحة
    embed.add_field(
        name="📋 الأوامر النشطة",
        value=f"**الإجمالي:** {len(bot.commands)}\n"
              f"**الألعاب:** 10+ أمر\n"
              f"**الإدارة:** 10+ أمر\n"
              f"**الاقتصاد:** 8+ أمر",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name="إضافة_رد")
@commands.has_permissions(administrator=True)
async def add_auto_reply(ctx, trigger: str, *, response: str):
    """إضافة رد تلقائي"""
    if len(trigger) < 2:
        await ctx.send("❌ الكلمة المطلوبة يجب أن تكون أكثر من حرفين!")
        return
    
    if len(response) < 3:
        await ctx.send("❌ الرد يجب أن يكون أكثر من 3 أحرف!")
        return
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # التحقق من وجود الرد مسبقاً
    c.execute("SELECT reply_id FROM auto_replies WHERE trigger = ?", (trigger.lower(),))
    existing = c.fetchone()
    
    if existing:
        await ctx.send("❌ هذا الرد موجود بالفعل!")
        conn.close()
        return
    
    # إضافة الرد الجديد
    c.execute("INSERT INTO auto_replies (trigger, response, added_by, added_at) VALUES (?, ?, ?, ?)",
             (trigger.lower(), response, str(ctx.author.id), datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    embed = discord.Embed(
        title="✅ تمت إضافة رد تلقائي",
        description=f"سيتم الرد تلقائياً عندما يكتب أحد الأعضاء: **{trigger}**",
        color=COLORS["SUCCESS"]
    )
    
    embed.add_field(name="🔤 الكلمة", value=trigger, inline=True)
    embed.add_field(name="💬 الرد", value=response, inline=True)
    embed.add_field(name="👤 المضيف", value=ctx.author.mention, inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name="حذف_رد")
@commands.has_permissions(administrator=True)
async def remove_auto_reply(ctx, trigger: str):
    """حذف رد تلقائي"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("DELETE FROM auto_replies WHERE trigger = ?", (trigger.lower(),))
    deleted = c.rowcount
    
    conn.commit()
    conn.close()
    
    if deleted > 0:
        embed = discord.Embed(
            title="✅ تم حذف الرد التلقائي",
            description=f"تم حذف الرد التلقائي للكلمة: **{trigger}**",
            color=COLORS["SUCCESS"]
        )
    else:
        embed = discord.Embed(
            title="❌ لم يتم العثور على الرد",
            description=f"لا يوجد رد تلقائي للكلمة: **{trigger}**",
            color=COLORS["ERROR"]
        )
    
    await ctx.send(embed=embed)

@bot.command(name="الردود")
async def list_auto_replies(ctx):
    """عرض الردود التلقائية"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("SELECT trigger, response, added_by FROM auto_replies ORDER BY trigger")
    replies = c.fetchall()
    conn.close()
    
    if not replies:
        embed = discord.Embed(
            title="💬 الردود التلقائية",
            description="لا توجد ردود تلقائية مضبوطة.",
            color=COLORS["INFO"]
        )
        await ctx.send(embed=embed)
        return
    
    embed = discord.Embed(
        title=f"💬 الردود التلقائية ({len(replies)})",
        color=COLORS["INFO"]
    )
    
    for i in range(0, len(replies), 5):
        batch = replies[i:i+5]
        replies_text = ""
        
        for trigger, response, added_by in batch:
            # تقصير الرد إذا كان طويلاً
            short_response = response[:50] + "..." if len(response) > 50 else response
            replies_text += f"**{trigger}** → {short_response}\n"
        
        embed.add_field(
            name=f"المجموعة {i//5 + 1}",
            value=replies_text,
            inline=False
        )
    
    await ctx.send(embed=embed)

# ========== وظائف مساعدة ==========
async def update_bot_status():
    """تحديث حالة البوت"""
    activity = discord.Activity(
        type=discord.ActivityType.playing,
        name=f"!مساعدة | {len(bot.guilds)} سيرفر"
    )
    await bot.change_presence(activity=activity)

# ========== تشغيل البوت ==========
def keep_alive():
    """تشغيل سيرفر ويب للحفاظ على التشغيل 24/7"""
    from flask import Flask
    from threading import Thread
    
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return """
        <!DOCTYPE html>
        <html dir="rtl">
        <head>
            <meta charset="UTF-8">
            <title>🤖 بوت مجتمع المبرمجين</title>
            <style>
                body {
                    font-family: 'Arial', sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    text-align: center;
                    padding: 50px;
                    margin: 0;
                }
                .container {
                    background: rgba(255,255,255,0.1);
                    backdrop-filter: blur(10px);
                    border-radius: 20px;
                    padding: 40px;
                    max-width: 900px;
                    margin: 0 auto;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                }
                h1 {
                    font-size: 3em;
                    margin-bottom: 20px;
                    text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
                }
                .status {
                    font-size: 1.5em;
                    color: #4CAF50;
                    margin: 20px 0;
                    padding: 10px;
                    background: rgba(255,255,255,0.2);
                    border-radius: 10px;
                }
                .features {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin-top: 30px;
                }
                .feature {
                    background: rgba(255,255,255,0.2);
                    padding: 20px;
                    border-radius: 10px;
                    transition: transform 0.3s;
                }
                .feature:hover {
                    transform: translateY(-5px);
                    background: rgba(255,255,255,0.3);
                }
                .stats {
                    display: flex;
                    justify-content: center;
                    gap: 30px;
                    margin: 30px 0;
                    flex-wrap: wrap;
                }
                .stat {
                    background: rgba(255,255,255,0.15);
                    padding: 15px 25px;
                    border-radius: 10px;
                    min-width: 150px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 بوت مجتمع المبرمجين</h1>
                <div class="status">✅ البوت يعمل بنجاح 24/7</div>
                <p>نظام بوت ديسكورد متكامل للمجتمعات البرمجية</p>
                
                <div class="stats">
                    <div class="stat">
                        <h3>50+</h3>
                        <p>أمر</p>
                    </div>
                    <div class="stat">
                        <h3>10+</h3>
                        <p>لعبة</p>
                    </div>
                    <div class="stat">
                        <h3>24/7</h3>
                        <p>تشغيل</p>
                    </div>
                    <div class="stat">
                        <h3>100%</h3>
                        <p>عربي</p>
                    </div>
                </div>
                
                <div class="features">
                    <div class="feature">
                        <h3>🎮 نظام الألعاب</h3>
                        <p>ألعاب متنوعة مع جوائز</p>
                    </div>
                    <div class="feature">
                        <h3>💰 النظام الاقتصادي</h3>
                        <p>عملات وتحويلات ومتجر</p>
                    </div>
                    <div class="feature">
                        <h3>🛡️ نظام الإدارة</h3>
                        <p>تحذيرات وتذاكر وإدارة</p>
                    </div>
                    <div class="feature">
                        <h3>📊 نظام المستويات</h3>
                        <p>خبرة وترقيات ومكافآت</p>
                    </div>
                    <div class="feature">
                        <h3>🎫 نظام التذاكر</h3>
                        <p>دعم فني متكامل</p>
                    </div>
                    <div class="feature">
                        <h3>⚙️ نظام الإعدادات</h3>
                        <p>تخصيص كامل للبوت</p>
                    </div>
                </div>
                
                <div style="margin-top: 30px; padding: 20px; background: rgba(0,0,0,0.2); border-radius: 10px;">
                    <h3>🚀 المميزات الرئيسية</h3>
                    <p>• 50+ أمر متكامل • قاعدة بيانات SQLite • واجهات تفاعلية • نظام أمني متقدم • تحديثات تلقائية</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    @app.route('/health')
    def health():
        return {"status": "healthy", "timestamp": datetime.datetime.now().isoformat()}, 200
    
    @app.route('/stats')
    def stats():
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM members")
        users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM games")
        games = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'")
        tickets = c.fetchone()[0]
        
        conn.close()
        
        return {
            "users": users,
            "games_played": games,
            "open_tickets": tickets,
            "guilds": len(bot.guilds),
            "uptime": str(datetime.datetime.now())
        }
    
    def run():
        app.run(host='0.0.0.0', port=8080)
    
    t = Thread(target=run)
    t.daemon = True
    t.start()

if __name__ == "__main__":
    # تشغيل سيرفر الويب
    keep_alive()
    
    # الحصول على التوكن
    TOKEN = os.environ.get('DISCORD_TOKEN')
    
    if TOKEN:
        logger.info("🚀 جاري تشغيل البوت المتكامل...")
        logger.info("📊 نظام كامل بـ 50+ أمر، 10+ لعبة، قاعدة بيانات، واجهات تفاعلية...")
        bot.run(TOKEN)
    else:
        logger.error("❌ لم يتم العثور على توكن البوت!")
        logger.info("✅ تأكد من تعيين متغير البيئة DISCORD_TOKEN على Render")
