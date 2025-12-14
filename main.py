# -*- coding: utf-8 -*-
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Select, Modal, TextInput
import os
import asyncio
import sqlite3
import json
import random
import datetime
from typing import Optional
import logging

# إعدادات البوت
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.all()
bot = commands.Bot(
    command_prefix=['!', '.', '/', 'بوت '],
    intents=intents,
    help_command=None,
    case_insensitive=True
)

# ألوان متنوعة
COLORS = {
    "SUCCESS": 0x00ff00,
    "ERROR": 0xff0000,
    "WARNING": 0xffaa00,
    "INFO": 0x0088ff,
    "PURPLE": 0x9b59b6,
    "GOLD": 0xf1c40f,
    "BLUE": 0x3498db,
    "GREEN": 0x2ecc71,
    "RED": 0xe74c3c
}

# قاعدة البيانات
DB_NAME = "bot_database.db"

def init_db():
    """تهيئة قاعدة البيانات"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # جدول الأعضاء
    c.execute('''CREATE TABLE IF NOT EXISTS members
                 (user_id TEXT PRIMARY KEY,
                  coins INTEGER DEFAULT 1000,
                  level INTEGER DEFAULT 1,
                  xp INTEGER DEFAULT 0,
                  warnings INTEGER DEFAULT 0,
                  join_date TEXT)''')
    
    # جدول التحذيرات
    c.execute('''CREATE TABLE IF NOT EXISTS warnings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT,
                  moderator_id TEXT,
                  reason TEXT,
                  timestamp DATETIME)''')
    
    # جدول التذاكر
    c.execute('''CREATE TABLE IF NOT EXISTS tickets
                 (ticket_id TEXT PRIMARY KEY,
                  user_id TEXT,
                  status TEXT DEFAULT 'open',
                  created_at DATETIME,
                  closed_at DATETIME)''')
    
    # جدول الألعاب
    c.execute('''CREATE TABLE IF NOT EXISTS games
                 (game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  game_type TEXT,
                  player1_id TEXT,
                  player2_id TEXT,
                  winner_id TEXT,
                  bet_amount INTEGER,
                  played_at DATETIME)''')
    
    conn.commit()
    conn.close()

# تهيئة قاعدة البيانات عند التشغيل
init_db()

# ========== أنظمة البوت ==========

# ---------- نظام المستويات والاقتصاد ----------
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
        c.execute("INSERT INTO members (user_id, coins, level, xp, join_date) VALUES (?, ?, ?, ?, ?)",
                 (str(user_id), 1000, 1, 0, datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return (str(user_id), 1000, 1, 0, 0, datetime.datetime.now().isoformat())
    
    return data

def add_xp(user_id, xp_amount):
    """إضافة نقاط خبرة"""
    data = get_member_data(user_id)
    current_xp = data[3]
    current_level = data[2]
    
    new_xp = current_xp + xp_amount
    needed_xp = current_level * 100
    
    if new_xp >= needed_xp:
        new_level = current_level + 1
        new_xp = new_xp - needed_xp
        level_up = True
    else:
        new_level = current_level
        level_up = False
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE members SET xp = ?, level = ? WHERE user_id = ?",
             (new_xp, new_level, str(user_id)))
    conn.commit()
    conn.close()
    
    return level_up, new_level

def add_coins(user_id, amount):
    """إضافة عملات"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE members SET coins = coins + ? WHERE user_id = ?",
             (amount, str(user_id)))
    conn.commit()
    conn.close()

# ---------- نظام التحذيرات ----------
def add_warning(user_id, moderator_id, reason):
    """إضافة تحذير"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # إضافة التحذير
    c.execute("INSERT INTO warnings (user_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?)",
             (str(user_id), str(moderator_id), reason, datetime.datetime.now().isoformat()))
    
    # تحديث عدد التحذيرات
    c.execute("UPDATE members SET warnings = warnings + 1 WHERE user_id = ?", (str(user_id),))
    
    # حساب العدد الجديد
    c.execute("SELECT warnings FROM members WHERE user_id = ?", (str(user_id),))
    warning_count = c.fetchone()[0]
    
    conn.commit()
    conn.close()
    
    return warning_count

# ---------- نظام التذاكر ----------
def create_ticket(user_id):
    """إنشاء تذكرة جديدة"""
    ticket_id = f"TICKET-{random.randint(1000, 9999)}"
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO tickets (ticket_id, user_id, created_at) VALUES (?, ?, ?)",
             (ticket_id, str(user_id), datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    return ticket_id

# ========== أحداث البوت ==========

@bot.event
async def on_ready():
    """حدث تشغيل البوت"""
    logger.info(f'✅ تم تسجيل الدخول باسم: {bot.user.name}')
    logger.info(f'🆔 رقم البوت: {bot.user.id}')
    logger.info(f'📊 عدد السيرفرات: {len(bot.guilds)}')
    
    # تحديث حالة البوت
    activity = discord.Activity(
        type=discord.ActivityType.playing,
        name=f"!مساعدة | في {len(bot.guilds)} سيرفر"
    )
    await bot.change_presence(activity=activity)
    
    # تشغيل المهام التلقائية
    update_status.start()
    logger.info("🚀 البوت جاهز للعمل!")

@bot.event
async def on_member_join(member):
    """ترحيب بالأعضاء الجدد"""
    channel = discord.utils.get(member.guild.text_channels, name="ترحيب")
    if not channel:
        channel = discord.utils.get(member.guild.text_channels, name="عام")
    
    if channel:
        embed = discord.Embed(
            title=f"🎉 أهلاً وسهلاً {member.name}!",
            description=f"مرحباً بك في **{member.guild.name}**\n\nأنت العضو رقم **#{member.guild.member_count}**",
            color=COLORS["SUCCESS"]
        )
        
        embed.add_field(name="📚 القواعد", value="اقرأ قواعد السيرفر في #القواعد", inline=True)
        embed.add_field(name="💡 نصائح", value="استخدم الأوامر بكثرة!", inline=True)
        embed.add_field(name="🎮 ألعاب", value="العب بأوامر !ألعاب", inline=True)
        
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.set_footer(text=f"تاريخ الانضمام: {member.joined_at.strftime('%Y-%m-%d')}")
        
        view = View()
        
        # زر اختيار الرتب
        roles_button = Button(label="🎭 اختر رتبتك", style=discord.ButtonStyle.primary)
        
        async def roles_callback(interaction):
            if interaction.user != member:
                await interaction.response.send_message("هذا الزر ليس لك!", ephemeral=True)
                return
            
            select = Select(
                placeholder="اختر رتبة الاهتمام",
                options=[
                    discord.SelectOption(label="بايثون", value="python", emoji="🐍"),
                    discord.SelectOption(label="جافا سكريبت", value="js", emoji="📜"),
                    discord.SelectOption(label="تطوير الويب", value="web", emoji="🌐"),
                    discord.SelectOption(label="تطوير ألعاب", value="game", emoji="🎮"),
                    discord.SelectOption(label="قواعد بيانات", value="db", emoji="💾")
                ]
            )
            
            async def select_callback(interaction):
                role_names = {
                    "python": "مبرمج بايثون",
                    "js": "مبرمج جافا سكريبت",
                    "web": "مطور ويب",
                    "game": "مطور ألعاب",
                    "db": "مبرمج قواعد بيانات"
                }
                
                role_name = role_names.get(select.values[0], select.values[0])
                role = discord.utils.get(interaction.guild.roles, name=role_name)
                
                if not role:
                    role = await interaction.guild.create_role(
                        name=role_name,
                        color=discord.Color.random(),
                        mentionable=True
                    )
                
                await member.add_roles(role)
                await interaction.response.send_message(
                    f"✅ تمت إضافة رتبة {role.mention} لك!",
                    ephemeral=True
                )
            
            select.callback = select_callback
            view2 = View()
            view2.add_item(select)
            
            await interaction.response.send_message(
                "اختر رتبة اهتماماتك البرمجية:",
                view=view2,
                ephemeral=True
            )
        
        roles_button.callback = roles_callback
        view.add_item(roles_button)
        
        await channel.send(embed=embed, view=view)
        
        # إرسال رسالة ترحيبية خاصة
        try:
            welcome_dm = discord.Embed(
                title=f"مرحباً بك في {member.guild.name}!",
                description="شكراً لانضمامك إلى مجتمعنا البرمجي",
                color=COLORS["INFO"]
            )
            welcome_dm.add_field(name="🔗 روابط مهمة", value="#القواعد #مساعدة #عام", inline=False)
            welcome_dm.add_field(name="🎮 أوامر ممتعة", value="!ألعاب - !روليت - !مسابقة", inline=False)
            welcome_dm.add_field(name="💰 النظام الاقتصادي", value="اكسب عملات بالألعاب والنشاط!", inline=False)
            await member.send(embed=welcome_dm)
        except:
            pass

@bot.event
async def on_message(message):
    """معالجة الرسائل"""
    if message.author.bot:
        return
    
    # إضافة نقاط للمستخدم
    level_up, new_level = add_xp(message.author.id, random.randint(5, 15))
    
    if level_up:
        embed = discord.Embed(
            title="🎉 ترقية مستوى!",
            description=f"{message.author.mention} لقد ارتقت إلى المستوى **{new_level}**!",
            color=COLORS["GOLD"]
        )
        await message.channel.send(embed=embed)
    
    # ردود ذكية
    responses = {
        "مرحبا": ["أهلاً وسهلاً! 👋", "مرحباً بك! 🎉", "أهلين! 😊"],
        "شكرا": ["العفو! 🤗", "أي خدمة! 🫡", "بكل سرور! ✨"],
        "بوت": ["نعم؟ 🤖", "أنا هنا! 🚀", "تحدث! 📢"],
        "كيف الحال": ["بخير الحمدلله! 😄", "تمام وأنت؟ 👍", "أفضل بوت! 😎"]
    }
    
    for keyword, response_list in responses.items():
        if keyword in message.content.lower():
            await message.channel.send(random.choice(response_list))
            break
    
    await bot.process_commands(message)

# ========== المهام التلقائية ==========

@tasks.loop(minutes=5)
async def update_status():
    """تحديث حالة البوت"""
    statuses = [
        f"!مساعدة | {len(bot.guilds)} سيرفر",
        f"مع {len(bot.users)} مستخدم",
        "مجتمع المبرمجين العرب",
        "ألعاب !ألعاب"
    ]
    
    activity = discord.Activity(
        type=discord.ActivityType.playing,
        name=random.choice(statuses)
    )
    await bot.change_presence(activity=activity)

# ========== الأوامر الأساسية ==========

@bot.command(name="مساعدة")
async def help_command(ctx):
    """عرض جميع الأوامر"""
    embed = discord.Embed(
        title="🎮 مركز مساعدة البوت",
        description="**جميع أوامر البوت المتاحة:**",
        color=COLORS["PURPLE"]
    )
    
    embed.add_field(
        name="🛡️ **أوامر الإدارة**",
        value="""```
!تحذير @المستخدم السبب
!إزالة_تحذير @المستخدم
!مسح عدد
!تأديب @المستخدم السبب
!رتب السيرفر
```""",
        inline=False
    )
    
    embed.add_field(
        name="🎮 **أوامر الألعاب**",
        value="""```
!ألعاب
!حجر_ورقة_مقص
!روليت مبلغ
!تخمين رقم
!سؤال
!مسابقة
```""",
        inline=False
    )
    
    embed.add_field(
        name="💰 **النظام الاقتصادي**",
        value="""```
!رصيدي
!تحويل @المستخدم مبلغ
!المتصدرين
!مستواي
!شراء عنصر
```""",
        inline=False
    )
    
    embed.add_field(
        name="🎫 **نظام التذاكر**",
        value="```!تذكرة\n!إغلاق_تذكرة\n!تذاكري```",
        inline=True
    )
    
    embed.add_field(
        name="📊 **معلومات**",
        value="```!معلومات\n!معلوماتي\n!سيرفر\n!بانر```",
        inline=True
    )
    
    embed.set_footer(text=f"طلب بواسطة: {ctx.author.name} | إجمالي الأوامر: 25+")
    
    view = View()
    
    # أزرار المساعدة
    buttons = [
        Button(label="الإدارة", style=discord.ButtonStyle.red, custom_id="help_admin"),
        Button(label="الألعاب", style=discord.ButtonStyle.green, custom_id="help_games"),
        Button(label="الاقتصاد", style=discord.ButtonStyle.blurple, custom_id="help_economy")
    ]
    
    for button in buttons:
        view.add_item(button)
    
    await ctx.send(embed=embed, view=view)

# ========== أوامر الإدارة ==========

@bot.command(name="تحذير")
@commands.has_permissions(manage_messages=True)
async def warn_command(ctx, member: discord.Member, *, reason="بدون سبب"):
    """تحذير عضو"""
    warning_count = add_warning(member.id, ctx.author.id, reason)
    
    embed = discord.Embed(
        title="⚠️ تحذير جديد",
        color=COLORS["WARNING"]
    )
    
    embed.add_field(name="👤 المستخدم", value=member.mention, inline=True)
    embed.add_field(name="🛡️ المشرف", value=ctx.author.mention, inline=True)
    embed.add_field(name="📝 السبب", value=reason, inline=False)
    embed.add_field(name="🔢 عدد التحذيرات", value=f"{warning_count}/3", inline=True)
    
    if warning_count >= 3:
        embed.add_field(
            name="🚨 إجراء تلقائي",
            value="تم حظر المستخدم تلقائياً (بان مؤقت 24 ساعة)",
            inline=False
        )
        await member.timeout(datetime.timedelta(hours=24), reason="تجاوز الحد الأقصى للتحذيرات")
    
    await ctx.send(embed=embed)
    
    # إرسال تنبيه للمستخدم
    try:
        dm_embed = discord.Embed(
            title="⚠️ لقد تلقيت تحذيراً",
            description=f"في سيرفر: {ctx.guild.name}",
            color=COLORS["WARNING"]
        )
        dm_embed.add_field(name="السبب", value=reason, inline=False)
        dm_embed.add_field(name="عدد التحذيرات", value=f"{warning_count}/3", inline=False)
        await member.send(embed=dm_embed)
    except:
        pass

@bot.command(name="مسح")
@commands.has_permissions(manage_messages=True)
async def clear_command(ctx, amount: int = 10):
    """مسح الرسائل"""
    if amount > 100:
        await ctx.send("❌ الحد الأقصى 100 رسالة")
        return
    
    deleted = await ctx.channel.purge(limit=amount + 1)
    
    embed = discord.Embed(
        title="🧹 تنظيف الرسائل",
        description=f"✅ تم مسح **{len(deleted)-1}** رسالة",
        color=COLORS["SUCCESS"]
    )
    
    msg = await ctx.send(embed=embed)
    await asyncio.sleep(3)
    await msg.delete()

@bot.command(name="تأديب")
@commands.has_permissions(kick_members=True)
async def timeout_command(ctx, member: discord.Member, duration: str, *, reason="بدون سبب"):
    """تايم آوت لعضو"""
    time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    unit = duration[-1].lower()
    
    if unit not in time_units:
        await ctx.send("❌ استخدم: 10s, 30m, 1h, 1d")
        return
    
    try:
        amount = int(duration[:-1])
        seconds = amount * time_units[unit]
        
        await member.timeout(datetime.timedelta(seconds=seconds), reason=reason)
        
        embed = discord.Embed(
            title="⏸️ تايم آوت",
            color=COLORS["WARNING"]
        )
        embed.add_field(name="المستخدم", value=member.mention, inline=True)
        embed.add_field(name="المدة", value=duration, inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ خطأ: {e}")

# ========== أوامر الألعاب ==========

@bot.command(name="ألعاب")
async def games_menu(ctx):
    """قائمة الألعاب"""
    embed = discord.Embed(
        title="🎮 مركز الألعاب",
        description="**اختر لعبة للعب:**",
        color=COLORS["GOLD"]
    )
    
    games = [
        {"name": "✊✋✌️ حجر ورقة مقص", "desc": "!حجر_ورقة_مقص", "prize": "0-100 عملة"},
        {"name": "🎲 الروليت", "desc": "!روليت [المبلغ]", "prize": "حتى 35x"},
        {"name": "🎯 التخمين", "desc": "!تخمين [1-100]", "prize": "50 عملة"},
        {"name": "❓ مسابقة", "desc": "!مسابقة", "prize": "100 عملة"},
        {"name": "🧠 سؤال برمجي", "desc": "!سؤال", "prize": "75 عملة"},
        {"name": "🎴 بطاقات", "desc": "!بطاقة", "prize": "عشوائي"}
    ]
    
    for game in games:
        embed.add_field(
            name=f"{game['name']}",
            value=f"{game['desc']}\n💰 الجائزة: {game['prize']}",
            inline=False
        )
    
    view = View()
    
    # أزرار الألعاب
    game_buttons = [
        Button(label="✊✋✌️", style=discord.ButtonStyle.green, emoji="🎮"),
        Button(label="🎲", style=discord.ButtonStyle.blurple, emoji="🎲"),
        Button(label="🎯", style=discord.ButtonStyle.gray, emoji="🎯")
    ]
    
    for button in game_buttons:
        view.add_item(button)
    
    await ctx.send(embed=embed, view=view)

@bot.command(name="حجر_ورقة_مقص")
async def rock_paper_scissors(ctx):
    """لعبة حجر ورقة مقص"""
    embed = discord.Embed(
        title="✊✋✌️ حجر ورقة مقص",
        description="**اختر حركتك:**",
        color=COLORS["GOLD"]
    )
    
    view = View()
    
    choices = ["✊", "✋", "✌️"]
    
    for choice in choices:
        button = Button(label=choice, style=discord.ButtonStyle.primary)
        
        async def callback(interaction, player_choice=choice):
            if interaction.user != ctx.author:
                await interaction.response.send_message("هذه اللعبة ليست لك!", ephemeral=True)
                return
            
            bot_choice = random.choice(choices)
            
            # تحديد الفائز
            if player_choice == bot_choice:
                result = "⚖️ تعادل!"
                coins = 10
            elif (player_choice == "✊" and bot_choice == "✌️") or \
                 (player_choice == "✋" and bot_choice == "✊") or \
                 (player_choice == "✌️" and bot_choice == "✋"):
                result = "🎉 فزت!"
                coins = 50
            else:
                result = "💥 خسرت!"
                coins = 0
            
            # إضافة العملات
            if coins > 0:
                add_coins(ctx.author.id, coins)
            
            embed = discord.Embed(
                title="🎮 نتيجة اللعبة",
                color=COLORS["SUCCESS"] if coins > 0 else COLORS["ERROR"]
            )
            embed.add_field(name="اختيارك", value=player_choice, inline=True)
            embed.add_field(name="اختيار البوت", value=bot_choice, inline=True)
            embed.add_field(name="النتيجة", value=result, inline=False)
            
            if coins > 0:
                embed.add_field(name="🎁 الجائزة", value=f"{coins} عملة", inline=True)
            
            await interaction.response.edit_message(embed=embed, view=None)
        
        button.callback = lambda i, c=choice: callback(i, c)
        view.add_item(button)
    
    await ctx.send(embed=embed, view=view)

@bot.command(name="روليت")
async def roulette(ctx, bet: int = 100):
    """لعبة الروليت"""
    if bet <= 0:
        await ctx.send("❌ الرهان يجب أن يكون أكبر من صفر")
        return
    
    # التحقق من الرصيد
    user_data = get_member_data(ctx.author.id)
    user_coins = user_data[1]
    
    if bet > user_coins:
        await ctx.send(f"❌ ليس لديك عملات كافية! رصيدك: {user_coins}")
        return
    
    # خصم الرهان
    add_coins(ctx.author.id, -bet)
    
    # لعب الروليت
    result = random.randint(0, 36)
    colors = ["🟢" if result == 0 else "🔴" if result % 2 == 1 else "⚫"]
    
    # تحديد الفوز
    if result == random.randint(0, 36):  # فرصة 1/37
        win_amount = bet * 35
        add_coins(ctx.author.id, win_amount)
        
        embed = discord.Embed(
            title="🎲 الروليت - فوز كبير!",
            description=f"**🎊🎊🎊 جاكبوت! 🎊🎊🎊**",
            color=COLORS["GOLD"]
        )
        embed.add_field(name="الرقم الفائز", value=f"{result} {colors[0]}", inline=True)
        embed.add_field(name="💰 رهانك", value=f"{bet} عملة", inline=True)
        embed.add_field(name="💰 فوزك", value=f"{win_amount} عملة", inline=True)
        embed.add_field(name="💎 المضاعف", value="35x", inline=True)
    elif result % 2 == 0:  # رهان على زوجي
        win_amount = bet * 2
        add_coins(ctx.author.id, win_amount)
        
        embed = discord.Embed(
            title="🎲 الروليت - فوز!",
            description=f"**🎉 فزت! الرقم زوجي**",
            color=COLORS["SUCCESS"]
        )
        embed.add_field(name="الرقم الفائز", value=f"{result} {colors[0]}", inline=True)
        embed.add_field(name="💰 رهانك", value=f"{bet} عملة", inline=True)
        embed.add_field(name="💰 فوزك", value=f"{win_amount} عملة", inline=True)
    else:
        embed = discord.Embed(
            title="🎲 الروليت - خسارة",
            description=f"**💥 خسرت!**",
            color=COLORS["ERROR"]
        )
        embed.add_field(name="الرقم", value=f"{result} {colors[0]}", inline=True)
        embed.add_field(name="💰 رهانك", value=f"{bet} عملة", inline=True)
        embed.add_field(name="💸 الخسارة", value=f"{bet} عملة", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name="سؤال")
async def programming_question(ctx):
    """سؤال برمجي"""
    questions = [
        {
            "question": "ما هي لغة البرمجة الأشهر للذكاء الاصطناعي؟",
            "options": ["بايثون", "جافا", "سي++", "جافا سكريبت"],
            "answer": 0,
            "difficulty": "سهل"
        },
        {
            "question": "ما هي مكتبة React مبنية عليها؟",
            "options": ["بايثون", "جافا سكريبت", "سي#", "روبي"],
            "answer": 1,
            "difficulty": "متوسط"
        },
        {
            "question": "أي من هذه ليست لغة برمجة؟",
            "options": ["HTML", "بايثون", "جافا", "سي++"],
            "answer": 0,
            "difficulty": "سهل"
        }
    ]
    
    q = random.choice(questions)
    
    embed = discord.Embed(
        title="🧠 سؤال برمجي",
        description=f"**{q['question']}**\n\n📊 الصعوبة: {q['difficulty']}\n💰 الجائزة: 75 عملة",
        color=COLORS["INFO"]
    )
    
    for i, option in enumerate(q['options']):
        embed.add_field(name=f"الخيار {i+1}", value=option, inline=True)
    
    await ctx.send(embed=embed)
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content in ["1", "2", "3", "4"]
    
    try:
        msg = await bot.wait_for("message", timeout=30.0, check=check)
        
        if int(msg.content) - 1 == q["answer"]:
            add_coins(ctx.author.id, 75)
            await ctx.send(f"✅ **إجابة صحيحة!**\n🎁 ربحت **75 عملة**!")
        else:
            correct_answer = q['options'][q['answer']]
            await ctx.send(f"❌ **إجابة خاطئة!**\n✅ الإجابة الصحيحة هي: **{correct_answer}**")
    except asyncio.TimeoutError:
        await ctx.send("⏰ **انتهى الوقت!**")

# ========== النظام الاقتصادي ==========

@bot.command(name="رصيدي")
async def balance_command(ctx, member: discord.Member = None):
    """عرض رصيد العضو"""
    if not member:
        member = ctx.author
    
    user_data = get_member_data(member.id)
    
    embed = discord.Embed(
        title=f"💰 رصيد {member.name}",
        color=member.color
    )
    
    embed.add_field(name="💎 العملات", value=f"**{user_data[1]}** عملة", inline=True)
    embed.add_field(name="📈 المستوى", value=f"**{user_data[2]}**", inline=True)
    embed.add_field(name="⚡ الخبرة", value=f"**{user_data[3]}/{user_data[2]*100}**", inline=True)
    
    # شريط التقدم
    progress = int((user_data[3] / (user_data[2] * 100)) * 20)
    progress_bar = "█" * progress + "░" * (20 - progress)
    embed.add_field(name="📊 شريط التقدم", value=f"`{progress_bar}`", inline=False)
    
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    
    await ctx.send(embed=embed)

@bot.command(name="تحويل")
async def transfer_command(ctx, member: discord.Member, amount: int):
    """تحويل عملات لعضو آخر"""
    if amount <= 0:
        await ctx.send("❌ المبلغ يجب أن يكون أكبر من صفر")
        return
    
    sender_data = get_member_data(ctx.author.id)
    
    if sender_data[1] < amount:
        await ctx.send(f"❌ ليس لديك عملات كافية! رصيدك: {sender_data[1]}")
        return
    
    # خصم من المرسل
    add_coins(ctx.author.id, -amount)
    # إضافة للمستقبل
    add_coins(member.id, amount)
    
    embed = discord.Embed(
        title="💸 تحويل ناجح",
        description=f"تم تحويل **{amount}** عملة",
        color=COLORS["SUCCESS"]
    )
    
    embed.add_field(name="👤 المرسل", value=ctx.author.mention, inline=True)
    embed.add_field(name="👥 المستقبل", value=member.mention, inline=True)
    embed.add_field(name="💰 المبلغ", value=f"{amount} عملة", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name="المتصدرين")
async def leaderboard_command(ctx):
    """لوحة المتصدرين"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("SELECT user_id, coins, level FROM members ORDER BY coins DESC LIMIT 10")
    top_users = c.fetchall()
    
    embed = discord.Embed(
        title="🏆 لوحة المتصدرين",
        description="**أفضل 10 لاعبين حسب العملات:**",
        color=COLORS["GOLD"]
    )
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, (user_id, coins, level) in enumerate(top_users):
        try:
            user = await bot.fetch_user(int(user_id))
            username = user.name
        except:
            username = "مستخدم غير معروف"
        
        embed.add_field(
            name=f"{medals[i]} {username}",
            value=f"💰 {coins} عملة | 📈 المستوى {level}",
            inline=False
        )
    
    conn.close()
    
    embed.set_footer(text="اكسب العملات بالألعاب والنشاط!")
    await ctx.send(embed=embed)

# ========== نظام التذاكر ==========

@bot.command(name="تذكرة")
async def ticket_command(ctx):
    """إنشاء تذكرة دعم"""
    ticket_id = create_ticket(ctx.author.id)
    
    # البحث عن قسم التذاكر
    category = discord.utils.get(ctx.guild.categories, name="🎫 التذاكر")
    
    if not category:
        # إنشاء قسم جديد
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.guild.me: discord.PermissionOverwrite(read_messages=True),
            ctx.guild.owner: discord.PermissionOverwrite(read_messages=True)
        }
        
        category = await ctx.guild.create_category(
            "🎫 التذاكر",
            overwrites=overwrites
        )
    
    # إنشاء رتبة للمشرفين
    admin_role = discord.utils.get(ctx.guild.roles, name="مشرف التذاكر")
    if not admin_role:
        admin_role = await ctx.guild.create_role(
            name="مشرف التذاكر",
            color=discord.Color.blue(),
            mentionable=True
        )
    
    # إنشاء قناة التذكرة
    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        admin_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    
    ticket_channel = await ctx.guild.create_text_channel(
        name=f"تذكرة-{ctx.author.name}-{ticket_id[-4:]}",
        category=category,
        overwrites=overwrites,
        topic=f"تذكرة دعم لـ {ctx.author.mention} | ID: {ticket_id}"
    )
    
    # رسالة الترحيب
    embed = discord.Embed(
        title="🎫 تذكرة دعم فني",
        description=f"**مرحباً {ctx.author.mention}!**\n\nشكراً لفتحك تذكرة دعم. فريق الدعم سيساعدك قريباً.",
        color=COLORS["INFO"]
    )
    
    embed.add_field(name="🆔 رقم التذكرة", value=ticket_id, inline=True)
    embed.add_field(name="📅 تاريخ الإنشاء", value=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), inline=True)
    embed.add_field(name="👤 المستخدم", value=ctx.author.mention, inline=True)
    
    embed.add_field(
        name="📝 التعليمات",
        value="""1. صف مشكلتك بوضوح
2. أرفق صور إذا لزم الأمر
3. انتظر رد فريق الدعم""",
        inline=False
    )
    
    embed.add_field(
        name="⏱️ وقت الاستجابة",
        value="عادةً خلال 24 ساعة",
        inline=True
    )
    
    # زر إغلاق التذكرة
    view = View()
    close_button = Button(label="🔒 إغلاق التذكرة", style=discord.ButtonStyle.red)
    
    async def close_callback(interaction):
        if any(role.permissions.manage_channels for role in interaction.user.roles):
            await interaction.response.send_message("🔒 جاري إغلاق التذكرة...")
            
            # تحديث قاعدة البيانات
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE tickets SET status = 'closed', closed_at = ? WHERE ticket_id = ?",
                     (datetime.datetime.now().isoformat(), ticket_id))
            conn.commit()
            conn.close()
            
            await asyncio.sleep(2)
            await interaction.channel.delete()
        else:
            await interaction.response.send_message("❌ ليس لديك صلاحية إغلاق التذاكر!", ephemeral=True)
    
    close_button.callback = close_callback
    view.add_item(close_button)
    
    await ticket_channel.send(embed=embed, view=view)
    await ctx.send(f"✅ تم إنشاء تذكرة الدعم: {ticket_channel.mention}")

# ========== أوامر المعلومات ==========

@bot.command(name="معلومات")
async def info_command(ctx):
    """معلومات السيرفر"""
    guild = ctx.guild
    
    embed = discord.Embed(
        title=f"📊 معلومات السيرفر: {guild.name}",
        color=COLORS["BLUE"]
    )
    
    # الإحصائيات الأساسية
    embed.add_field(name="👑 المالك", value=guild.owner.mention, inline=True)
    embed.add_field(name="🆔 الرقم", value=guild.id, inline=True)
    embed.add_field(name="📅 تاريخ الإنشاء", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    
    # الإحصائيات
    embed.add_field(name="👥 الأعضاء", value=guild.member_count, inline=True)
    embed.add_field(name="📁 القنوات", value=len(guild.channels), inline=True)
    embed.add_field(name="🎭 الرتب", value=len(guild.roles), inline=True)
    
    # معلومات البوت
    embed.add_field(name="🤖 البوت", value=bot.user.mention, inline=True)
    embed.add_field(name="⏰ وقت التشغيل", value=f"{len(bot.guilds)} سيرفر", inline=True)
    embed.add_field(name="⚡ البينج", value=f"{round(bot.latency * 1000)}ms", inline=True)
    
    # إحصائيات إضافية
    online = len([m for m in guild.members if m.status != discord.Status.offline])
    bots = len([m for m in guild.members if m.bot])
    
    embed.add_field(name="🟢 الأعضاء النشطين", value=online, inline=True)
    embed.add_field(name="🤖 البوتات", value=bots, inline=True)
    embed.add_field(name="📈 نسبة النشاط", value=f"{(online/guild.member_count)*100:.1f}%", inline=True)
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    embed.set_footer(text=f"طلب بواسطة: {ctx.author.name}")
    
    await ctx.send(embed=embed)

@bot.command(name="معلوماتي")
async def my_info_command(ctx):
    """معلومات العضو"""
    member = ctx.author
    user_data = get_member_data(member.id)
    
    embed = discord.Embed(
        title=f"👤 معلومات {member.name}",
        color=member.color
    )
    
    # المعلومات الأساسية
    embed.add_field(name="🆔 الرقم", value=member.id, inline=True)
    embed.add_field(name="📛 الاسم الكامل", value=member.display_name, inline=True)
    embed.add_field(name="📅 تاريخ الإنشاء", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
    
    # معلومات السيرفر
    embed.add_field(name="📅 تاريخ الانضمام", value=member.joined_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="🎭 أعلى رتبة", value=member.top_role.mention, inline=True)
    
    # النظام الاقتصادي
    embed.add_field(name="💰 العملات", value=f"{user_data[1]} عملة", inline=True)
    embed.add_field(name="📈 المستوى", value=user_data[2], inline=True)
    embed.add_field(name="⚡ الخبرة", value=f"{user_data[3]}/{user_data[2]*100}", inline=True)
    embed.add_field(name="⚠️ التحذيرات", value=user_data[4], inline=True)
    
    # الرتب
    roles = [role.mention for role in member.roles[1:]]  # استبعاد رتبة @everyone
    if roles:
        embed.add_field(
            name=f"🎭 الرتب ({len(roles)})",
            value=" ".join(roles[:10]) + ("..." if len(roles) > 10 else ""),
            inline=False
        )
    
    # الأوسمة
    if member.premium_since:
        embed.add_field(name="🌟 معزز", value=f"منذ {member.premium_since.strftime('%Y-%m-%d')}", inline=True)
    
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.set_footer(text=f"طلب في: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    await ctx.send(embed=embed)

@bot.command(name="بانر")
async def banner_command(ctx):
    """إنشاء بانر شخصي"""
    member = ctx.author
    user_data = get_member_data(member.id)
    
    # إنشاء بانر بصري
    embed = discord.Embed(
        title=f"🎨 بانر {member.name}",
        color=member.color
    )
    
    # إحصائيات
    stats = f"""
    **📊 الإحصائيات:**
    💰 **العملات:** {user_data[1]:,}
    📈 **المستوى:** {user_data[2]}
    ⚡ **الخبرة:** {user_data[3]}/{user_data[2]*100}
    ⚠️ **التحذيرات:** {user_data[4]}
    
    **🎮 الإنجازات:**
    🎯 **النشاط:** {'🌟🌟🌟' if user_data[3] > 1000 else '🌟🌟' if user_data[3] > 500 else '🌟'}
    💎 **الثروة:** {'💰💰💰' if user_data[1] > 5000 else '💰💰' if user_data[1] > 2000 else '💰'}
    🏆 **الخبرة:** {'👑' if user_data[2] > 10 else '⭐' if user_data[2] > 5 else '✨'}
    """
    
    embed.description = stats
    
    # شريط التقدم
    progress = int((user_data[3] / (user_data[2] * 100)) * 30)
    progress_bar = "█" * progress + "░" * (30 - progress)
    embed.add_field(name="📊 شريط التقدم للمستوى التالي", value=f"```{progress_bar}```", inline=False)
    
    # رتب السيرفر
    embed.add_field(
        name="🎭 رتبك في السيرفر",
        value=f"لديك **{len(member.roles)-1}** رتبة",
        inline=True
    )
    
    # تاريخ الانضمام
    days_in_server = (datetime.datetime.now() - member.joined_at).days
    embed.add_field(
        name="📅 مدة العضوية",
        value=f"**{days_in_server}** يوم",
        inline=True
    )
    
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.set_footer(text="تابع النشاط لترتقي في المستويات!")
    
    await ctx.send(embed=embed)

# ========== أوامر مساعدة إضافية ==========

@bot.command(name="سيرفر")
async def server_stats_command(ctx):
    """إحصائيات السيرفر"""
    guild = ctx.guild
    
    # حساب الإحصائيات
    members = guild.member_count
    online = len([m for m in guild.members if m.status != discord.Status.offline])
    bots = len([m for m in guild.members if m.bot])
    humans = members - bots
    
    text_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
    voice_channels = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
    
    embed = discord.Embed(
        title=f"📈 إحصائيات {guild.name}",
        color=COLORS["PURPLE"]
    )
    
    # قسم الأعضاء
    embed.add_field(
        name="👥 الأعضاء",
        value=f"""
        **الإجمالي:** {members}
        **النشطين:** {online}
        **البشر:** {humans}
        **البوتات:** {bots}
        **النسبة:** {(online/members)*100:.1f}%
        """,
        inline=False
    )
    
    # قسم القنوات
    embed.add_field(
        name="📁 القنوات",
        value=f"""
        **النصية:** {text_channels}
        **الصوتية:** {voice_channels}
        **الإجمالي:** {len(guild.channels)}
        **الرتب:** {len(guild.roles)}
        """,
        inline=False
    )
    
    # قسم التواريخ
    embed.add_field(
        name="📅 التواريخ",
        value=f"""
        **تاريخ الإنشاء:** {guild.created_at.strftime('%Y-%m-%d')}
        **مدة التشغيل:** {(datetime.datetime.now() - guild.created_at).days} يوم
        **المستوى:** {guild.premium_tier}
        **المعززون:** {guild.premium_subscription_count}
        """,
        inline=False
    )
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    embed.set_footer(text=f"آخر تحديث: {datetime.datetime.now().strftime('%H:%M')}")
    
    await ctx.send(embed=embed)

@bot.command(name="أوامر")
async def commands_list(ctx):
    """قائمة مختصرة للأوامر"""
    embed = discord.Embed(
        title="📋 أوامر سريعة",
        description="**الأوامر الأكثر استخداماً:**",
        color=COLORS["GREEN"]
    )
    
    embed.add_field(
        name="🎮 **للجميع**",
        value="""
        `!ألعاب` - مركز الألعاب
        `!رصيدي` - عرض رصيدك
        `!معلوماتي` - معلوماتك
        `!تذكرة` - دعم فني
        `!بانر` - بانر شخصي
        """,
        inline=True
    )
    
    embed.add_field(
        name="🛡️ **للمشرفين**",
        value="""
        `!تحذير` - تحذير عضو
        `!مسح` - مسح الرسائل
        `!تأديب` - تايم آوت
        `!معلومات` - معلومات السيرفر
        """,
        inline=True
    )
    
    embed.add_field(
        name="💰 **اقتصاد**",
        value="""
        `!المتصدرين` - أفضل اللاعبين
        `!تحويل` - تحويل عملات
        `!سؤال` - أسئلة برمجية
        `!روليت` - لعبة الروليت
        """,
        inline=True
    )
    
    await ctx.send(embed=embed)

# ========== معالجة الأخطاء ==========

@bot.event
async def on_command_error(ctx, error):
    """معالجة أخطاء الأوامر"""
    if isinstance(error, commands.CommandNotFound):
        embed = discord.Embed(
            title="❌ أمر غير موجود",
            description="هذا الأمر غير موجود!\n\nاستخدم `!مساعدة` لرؤية جميع الأوامر.",
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
            description=f"معطيات الأوامر ناقصة!\n\n**الصيغة الصحيحة:** `{ctx.prefix}{ctx.command.name} {ctx.command.signature}`",
            color=COLORS["WARNING"]
        )
        await ctx.send(embed=embed)
    
    else:
        logger.error(f"خطأ غير متوقع: {error}")
        embed = discord.Embed(
            title="💥 خطأ غير متوقع",
            description="حدث خطأ غير متوقع! تم تسجيل الخطأ وسيتم إصلاحه قريباً.",
            color=COLORS["ERROR"]
        )
        await ctx.send(embed=embed)

# ========== تشغيل البوت ==========

def keep_alive():
    """تشغيل سيرفر ويب بسيط"""
    from flask import Flask
    from threading import Thread
    
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "🚀 بوت مجتمع المبرمجين يعمل بنجاح 24/7!"
    
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
        logger.info("🚀 جاري تشغيل البوت...")
        bot.run(TOKEN)
    else:
        logger.error("❌ لم يتم العثور على توكن البوت!")
        logger.info("✅ تأكد من تعيين متغير البيئة DISCORD_TOKEN")
