# -*- coding: utf-8 -*-
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Select
import os
import asyncio
import aiohttp
import json
import random
import datetime
import sqlite3
from typing import Optional
from keep_alive import keep_alive
import traceback
import logging

# إعدادات متقدمة
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.all()
bot = commands.Bot(
    command_prefix=['!', '?', '.', 'بوت '],
    intents=intents,
    help_command=None,
    case_insensitive=True
)

# قاعدة بيانات SQLite
DB_NAME = "bot_database.db"

# ألوان متنوعة للاستخدام
COLORS = {
    "SUCCESS": 0x00ff00,
    "ERROR": 0xff0000,
    "WARNING": 0xffaa00,
    "INFO": 0x0088ff,
    "PURPLE": 0x9b59b6,
    "GOLD": 0xf1c40f
}

# ---------- نظام قاعدة البيانات ----------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # جدول نظام التحذيرات
    c.execute('''CREATE TABLE IF NOT EXISTS warnings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT,
                  moderator_id TEXT,
                  reason TEXT,
                  timestamp DATETIME)''')
    
    # جدول نظام المستويات
    c.execute('''CREATE TABLE IF NOT EXISTS levels
                 (user_id TEXT PRIMARY KEY,
                  xp INTEGER DEFAULT 0,
                  level INTEGER DEFAULT 1,
                  messages INTEGER DEFAULT 0)''')
    
    # جدول نظام البان/تايم
    c.execute('''CREATE TABLE IF NOT EXISTS bans
                 (user_id TEXT PRIMARY KEY,
                  reason TEXT,
                  moderator_id TEXT,
                  end_time DATETIME,
                  is_temp BOOLEAN)''')
    
    # جدول الإحصائيات
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (key TEXT PRIMARY KEY,
                  value INTEGER)''')
    
    conn.commit()
    conn.close()

# ---------- فئات خاصة ----------
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🎫 فتح تذكرة", style=discord.ButtonStyle.green, custom_id="open_ticket")
    async def open_ticket_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        
        # إنشاء تذكرة
        category = discord.utils.get(interaction.guild.categories, name="🎫 التذاكر")
        if not category:
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True)
            }
            category = await interaction.guild.create_category("🎫 التذاكر", overwrites=overwrites)
        
        ticket_channel = await interaction.guild.create_text_channel(
            f"تذكرة-{interaction.user.name}",
            category=category,
            topic=f"تذكرة دعم لـ {interaction.user.mention}"
        )
        
        await ticket_channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        
        embed = discord.Embed(
            title="🎫 تذكرة دعم فني",
            description=f"**المستخدم:** {interaction.user.mention}\n**التاريخ:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
            color=COLORS["INFO"]
        )
        
        embed.add_field(name="📝 وصف المشكلة", value="يرجى وصف مشكلتك هنا...", inline=False)
        embed.add_field(name="🕒 وقت الاستجابة", value="سيتم الرد خلال 24 ساعة كحد أقصى", inline=False)
        
        close_view = View()
        close_button = Button(label="🔒 إغلاق التذكرة", style=discord.ButtonStyle.red, custom_id="close_ticket")
        
        async def close_callback(interaction: discord.Interaction):
            if any(role.permissions.manage_channels for role in interaction.user.roles) or interaction.user.guild_permissions.manage_channels:
                await interaction.response.send_message("🔒 جاري إغلاق التذكرة...")
                await asyncio.sleep(2)
                await interaction.channel.delete()
            else:
                await interaction.response.send_message("❌ ليس لديك صلاحية إغلاق التذاكر!", ephemeral=True)
        
        close_button.callback = close_callback
        close_view.add_item(close_button)
        
        await ticket_channel.send(embed=embed, view=close_view)
        await interaction.followup.send(f"✅ تم إنشاء تذكرة في {ticket_channel.mention}", ephemeral=True)

class GameView(View):
    def __init__(self, game_type):
        super().__init__(timeout=60)
        self.game_type = game_type
        self.value = None
    
    @discord.ui.button(label="✊", style=discord.ButtonStyle.primary)
    async def rock(self, interaction: discord.Interaction, button: Button):
        self.value = "✊"
        await self.process_choice(interaction)
    
    @discord.ui.button(label="✋", style=discord.ButtonStyle.primary)
    async def paper(self, interaction: discord.Interaction, button: Button):
        self.value = "✋"
        await self.process_choice(interaction)
    
    @discord.ui.button(label="✌️", style=discord.ButtonStyle.primary)
    async def scissors(self, interaction: discord.Interaction, button: Button):
        self.value = "✌️"
        await self.process_choice(interaction)
    
    async def process_choice(self, interaction):
        bot_choice = random.choice(["✊", "✋", "✌️"])
        result = self.get_result(self.value, bot_choice)
        
        embed = discord.Embed(title="🎮 حجر ورقة مقص", color=COLORS["GOLD"])
        embed.add_field(name="اختيارك", value=self.value, inline=True)
        embed.add_field(name="اختيار البوت", value=bot_choice, inline=True)
        embed.add_field(name="النتيجة", value=result, inline=False)
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    def get_result(self, player, bot):
        if player == bot:
            return "⚖️ تعادل!"
        elif (player == "✊" and bot == "✌️") or (player == "✋" and bot == "✊") or (player == "✌️" and bot == "✋"):
            return "🎉 فزت!"
        else:
            return "💥 خسرت!"

# ---------- أحداث البوت ----------
@bot.event
async def on_ready():
    logger.info(f'✅ البوت جاهز: {bot.user.name} ({bot.user.id})')
    logger.info(f'📊 عدد السيرفرات: {len(bot.guilds)}')
    logger.info("✅ تم تهيئة جميع الأنظمة")
    
    # تحديث الحالة
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.playing,
            name=f"في {len(bot.guilds)} سيرفر | !مساعدة"
        )
    )
    
    # 🚨 START THE TASK HERE, AFTER THE BOT IS READY 🚨
    if not daily_backup.is_running():
        daily_backup.start()
        logger.info("✅ تم تشغيل مهمة النسخ الاحتياطي اليومي")
    
    # Also start the other tasks if they exist
    if not update_status.is_running():
        update_status.start()
    if not check_temp_bans.is_running():
        check_temp_bans.start()
    
    logger.info("✅ تم تهيئة جميع الأنظمة")

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="🚪-الترحيب")
    
    if not channel:
        channel = discord.utils.get(member.guild.text_channels, name="general")
    
    if channel:
        embed = discord.Embed(
            title=f"🎊 أهلاً وسهلاً {member.name}!",
            description=f"**مرحباً بك في مجتمع المبرمجين!**\n\n• رتبتك الحالية: {member.top_role.mention}\n• أنت العضو رقم: {member.guild.member_count}",
            color=COLORS["SUCCESS"]
        )
        
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.add_field(name="📚 القواعد", value="اقرأ #📜-القواعد", inline=True)
        embed.add_field(name="💭 التعارف", value="تحدث في #💬-عام", inline=True)
        embed.add_field(name="💡 نصائح", value="شارك معرفتك", inline=True)
        
        embed.set_footer(text=f"تاريخ الانضمام: {member.joined_at.strftime('%Y-%m-%d %H:%M')}")
        
        view = View()
        role_button = Button(label="🎭 اختر رتبتك", style=discord.ButtonStyle.blurple)
        
        async def role_callback(interaction):
            role_menu = Select(
                placeholder="اختر رتبة اهتماماتك",
                options=[
                    discord.SelectOption(label="بايثون", value="python", emoji="🐍"),
                    discord.SelectOption(label="جافا سكريبت", value="js", emoji="📜"),
                    discord.SelectOption(label="تطوير الويب", value="web", emoji="🌐"),
                    discord.SelectOption(label="تطوير الألعاب", value="game", emoji="🎮"),
                    discord.SelectOption(label="الذكاء الاصطناعي", value="ai", emoji="🤖")
                ]
            )
            
            async def select_callback(interaction):
                role_map = {
                    "python": "بايثون",
                    "js": "جافا سكريبت",
                    "web": "تطوير الويب",
                    "game": "تطوير الألعاب",
                    "ai": "الذكاء الاصطناعي"
                }
                
                selected_role = discord.utils.get(interaction.guild.roles, name=role_map[role_menu.values[0]])
                if selected_role:
                    await member.add_roles(selected_role)
                    await interaction.response.send_message(f"✅ تمت إضافة رتبة {selected_role.mention}", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ لم أجد الرتبة!", ephemeral=True)
            
            role_menu.callback = select_callback
            view2 = View()
            view2.add_item(role_menu)
            await interaction.response.send_message("اختر رتبتك:", view=view2, ephemeral=True)
        
        role_button.callback = role_callback
        view.add_item(role_button)
        
        await channel.send(f"{member.mention} 👋", embed=embed, view=view)
        
        # إرسال رسالة ترحيب خاصة
        try:
            welcome_dm = discord.Embed(
                title=f"مرحباً بك في {member.guild.name}!",
                description="شكراً لانضمامك إلينا. إليك بعض المعلومات:",
                color=COLORS["INFO"]
            )
            welcome_dm.add_field(name="📌 نصائح سريعة", value="• اقرأ القواعد أولاً\n• استخدم القنوات المناسبة\n• لا تتردد بالسؤال", inline=False)
            welcome_dm.add_field(name="🔗 روابط مهمة", value="• #📜-القواعد\n• #📚-الموارد\n• #❓-مساعدة", inline=False)
            await member.send(embed=welcome_dm)
        except:
            pass

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # نظام XP والترقية
    if not message.content.startswith(tuple(bot.command_prefix)):
        add_xp(message.author.id, random.randint(10, 25))
    
    # ردود ذكية
    responses = {
        "شكرا": ["العفو! 😊", "أي خدمة! 🤝", "دائماً في الخدمة! 🎯"],
        "مرحبا": ["أهلاً وسهلاً! 👋", "مرحباً بك! 🎉", "أهلين! ✨"],
        "بوت": ["نعم؟ 😊", "أنا هنا! 🚀", "كيف أستطيع مساعدتك؟ 🤖"]
    }
    
    for keyword, response_list in responses.items():
        if keyword in message.content.lower():
            await message.channel.send(random.choice(response_list))
            break
    
    await bot.process_commands(message)

# ---------- المهام التلقائية ----------
@tasks.loop(minutes=5)
async def update_status():
    statuses = [
        f"مع {len(bot.users)} مستخدم",
        "!مساعدة للأوامر",
        "مجتمع المبرمجين العرب",
        f"في {len(bot.guilds)} سيرفر"
    ]
    
    activity = discord.Activity(
        type=discord.ActivityType.playing,
        name=random.choice(statuses)
    )
    await bot.change_presence(activity=activity)

@tasks.loop(minutes=1)
async def check_temp_bans():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("SELECT user_id, end_time FROM bans WHERE is_temp = 1")
    temp_bans = c.fetchall()
    
    for user_id, end_time_str in temp_bans:
        end_time = datetime.datetime.fromisoformat(end_time_str)
        if datetime.datetime.now() > end_time:
            # إلغاء البان
            c.execute("DELETE FROM bans WHERE user_id = ?", (user_id,))
            conn.commit()
            
            # محاولة إلغاء البان من السيرفرات
            for guild in bot.guilds:
                try:
                    user = await bot.fetch_user(int(user_id))
                    await guild.unban(user)
                    logger.info(f"✅ تم إلغاء البان المؤقت للمستخدم {user_id}")
                except:
                    continue
    
    conn.close()

# ---------- وظائف مساعدة ----------
def add_xp(user_id, xp_amount):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("SELECT xp, level FROM levels WHERE user_id = ?", (str(user_id),))
    result = c.fetchone()
    
    if result:
        current_xp, current_level = result
        new_xp = current_xp + xp_amount
        
        # حساب المستوى الجديد
        needed_xp = 100 * (current_level ** 2)
        if new_xp >= needed_xp:
            new_level = current_level + 1
            new_xp = new_xp - needed_xp
        else:
            new_level = current_level
        
        c.execute("UPDATE levels SET xp = ?, level = ? WHERE user_id = ?",
                 (new_xp, new_level, str(user_id)))
    else:
        c.execute("INSERT INTO levels (user_id, xp) VALUES (?, ?)",
                 (str(user_id), xp_amount))
        new_level = 1
    
    conn.commit()
    conn.close()
    return new_level

def add_warning(user_id, moderator_id, reason):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("INSERT INTO warnings (user_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?)",
             (str(user_id), str(moderator_id), reason, datetime.datetime.now()))
    
    # حساب عدد التحذيرات
    c.execute("SELECT COUNT(*) FROM warnings WHERE user_id = ?", (str(user_id),))
    warning_count = c.fetchone()[0]
    
    conn.commit()
    conn.close()
    return warning_count

# ---------- الأوامر الأساسية ----------
@bot.command(name="مساعدة")
async def help_command(ctx):
    embed = discord.Embed(
        title="🎮 مركز مساعدة البوت المتكامل",
        description="**أنظمة البوت المتاحة:**",
        color=COLORS["PURPLE"]
    )
    
    embed.add_field(name="🛡️ **نظام الإدارة**", 
                   value="```!تحذير !بان !تايم !كيك !مسح```", inline=False)
    
    embed.add_field(name="🎭 **نظام الرتب**", 
                   value="```!رتبة !اعطاء_رتبة !سحب_رتبة```", inline=False)
    
    embed.add_field(name="🎮 **نظام الألعاب**", 
                   value="```!لعبة !حجر_ورقة_مقص !روليت !سؤال```", inline=False)
    
    embed.add_field(name="📊 **نظام المستويات**", 
                   value="```!مستواي !المستويات !التصنيف```", inline=False)
    
    embed.add_field(name="🛠️ **نظام التذاكر**", 
                   value="```!تذكرة !لوحة_التذاكر```", inline=False)
    
    embed.add_field(name="⚙️ **إعدادات السيرفر**", 
                   value="```!اعدادات !اعداد_ترحيب !اعداد_سجل```", inline=False)
    
    embed.set_footer(text=f"إجمالي الأوامر: 50+ | الطلب من: {ctx.author.name}")
    
    view = View()
    buttons = [
        Button(label="الإدارة", style=discord.ButtonStyle.green, custom_id="help_admin"),
        Button(label="الألعاب", style=discord.ButtonStyle.blurple, custom_id="help_games"),
        Button(label="التخصيص", style=discord.ButtonStyle.gray, custom_id="help_custom")
    ]
    
    for button in buttons:
        view.add_item(button)
    
    await ctx.send(embed=embed, view=view)

# ---------- نظام الإدارة المتقدم ----------
@bot.command(name="تحذير")
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="بدون سبب"):
    warning_count = add_warning(member.id, ctx.author.id, reason)
    
    embed = discord.Embed(
        title="⚠️ تحذير جديد",
        color=COLORS["WARNING"]
    )
    
    embed.add_field(name="المستخدم", value=member.mention, inline=True)
    embed.add_field(name="المشرف", value=ctx.author.mention, inline=True)
    embed.add_field(name="السبب", value=reason, inline=False)
    embed.add_field(name="عدد التحذيرات", value=f"{warning_count}/5", inline=True)
    
    if warning_count >= 5:
        embed.add_field(name="🚨 إجراء تلقائي", value="تم حظر المستخدم تلقائياً", inline=False)
        await member.ban(reason="تجاوز الحد الأقصى للتحذيرات")
    
    await ctx.send(embed=embed)
    
    # إرسال تنبيه للمستخدم
    try:
        dm_embed = discord.Embed(
            title="⚠️ لقد تلقيت تحذيراً",
            description=f"في سيرفر: {ctx.guild.name}",
            color=COLORS["WARNING"]
        )
        dm_embed.add_field(name="السبب", value=reason, inline=False)
        dm_embed.add_field(name="عدد التحذيرات", value=f"{warning_count}/5", inline=False)
        await member.send(embed=dm_embed)
    except:
        pass

@bot.command(name="بان")
@commands.has_permissions(ban_members=True)
async def ban_command(ctx, member: discord.Member, duration: str = None, *, reason="بدون سبب"):
    if duration:
        # بان مؤقت
        time_units = {
            "m": 60, "min": 60, "دقيقة": 60,
            "h": 3600, "hour": 3600, "ساعة": 3600,
            "d": 86400, "day": 86400, "يوم": 86400
        }
        
        unit = duration[-1] if duration[-1].isalpha() else duration[-2:]
        amount = int(''.join(filter(str.isdigit, duration)))
        
        if unit in time_units:
            seconds = amount * time_units[unit]
            end_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
            
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO bans VALUES (?, ?, ?, ?, ?)",
                     (str(member.id), reason, str(ctx.author.id), end_time.isoformat(), True))
            conn.commit()
            conn.close()
            
            embed = discord.Embed(
                title="⏳ حظر مؤقت",
                color=COLORS["WARNING"]
            )
            embed.add_field(name="المستخدم", value=member.mention, inline=True)
            embed.add_field(name="المدة", value=duration, inline=True)
            embed.add_field(name="السبب", value=reason, inline=False)
            embed.add_field(name="ينتهي في", value=end_time.strftime("%Y-%m-%d %H:%M"), inline=True)
            
            await member.ban(reason=f"مؤقت: {reason} | المدة: {duration}")
        else:
            await ctx.send("❌ وحدة الزمن غير صحيحة! استخدم: m/h/d")
            return
    else:
        # بان دائم
        embed = discord.Embed(
            title="🔒 حظر دائم",
            color=COLORS["ERROR"]
        )
        embed.add_field(name="المستخدم", value=member.mention, inline=True)
        embed.add_field(name="المشرف", value=ctx.author.mention, inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        
        await member.ban(reason=reason)
    
    await ctx.send(embed=embed)

@bot.command(name="تايم")
@commands.has_permissions(manage_roles=True)
async def timeout(ctx, member: discord.Member, duration: str, *, reason="بدون سبب"):
    time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    unit = duration[-1]
    
    if unit not in time_units:
        await ctx.send("❌ استخدم: 10s, 30m, 1h, 1d")
        return
    
    seconds = int(duration[:-1]) * time_units[unit]
    
    try:
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

@bot.command(name="كيك")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="بدون سبب"):
    embed = discord.Embed(
        title="👢 طرد عضو",
        color=COLORS["WARNING"]
    )
    embed.add_field(name="المستخدم", value=member.mention, inline=True)
    embed.add_field(name="المشرف", value=ctx.author.mention, inline=True)
    embed.add_field(name="السبب", value=reason, inline=False)
    
    await member.kick(reason=reason)
    await ctx.send(embed=embed)

@bot.command(name="مسح")
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 10):
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

# ---------- نظام الرتب المتقدم ----------
@bot.command(name="رتبة")
async def role_info(ctx, *, role_name: str = None):
    if not role_name:
        # عرض جميع الرتب
        roles = [role for role in ctx.guild.roles if not role.is_default()]
        
        embed = discord.Embed(
            title="🎭 رتب السيرفر",
            description=f"**إجمالي الرتب:** {len(roles)}",
            color=COLORS["PURPLE"]
        )
        
        # تقسيم الرتب إلى مجموعات
        chunks = [roles[i:i+10] for i in range(0, len(roles), 10)]
        
        for i, chunk in enumerate(chunks[:3]):  # عرض 3 صفحات كحد أقصى
            role_list = "\n".join([f"{role.mention} - {len(role.members)} عضو" for role in chunk])
            embed.add_field(name=f"المجموعة {i+1}", value=role_list or "لا توجد رتب", inline=False)
        
        await ctx.send(embed=embed)
    else:
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if role:
            embed = discord.Embed(
                title=f"معلومات رتبة: {role.name}",
                color=role.color
            )
            embed.add_field(name="🆔 الرقم", value=role.id, inline=True)
            embed.add_field(name="🎨 اللون", value=str(role.color), inline=True)
            embed.add_field(name="👥 عدد الأعضاء", value=len(role.members), inline=True)
            embed.add_field(name="📅 تاريخ الإنشاء", value=role.created_at.strftime("%Y-%m-%d"), inline=True)
            embed.add_field(name="🔑 الصلاحيات", value=f"{len(role.permissions)} صلاحية", inline=True)
            
            if role.permissions.administrator:
                embed.add_field(name="⚡ ملاحظة", value="هذه الرتبة لديها صلاحيات المدير", inline=False)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ الرتبة غير موجودة")

@bot.command(name="اعطاء_رتبة")
@commands.has_permissions(manage_roles=True)
async def add_role(ctx, member: discord.Member, *, role_name: str):
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    
    if not role:
        await ctx.send("❌ الرتبة غير موجودة")
        return
    
    if role.position >= ctx.guild.me.top_role.position:
        await ctx.send("❌ لا يمكنني إعطاء هذه الرتبة")
        return
    
    await member.add_roles(role)
    
    embed = discord.Embed(
        title="✅ تم إضافة الرتبة",
        color=COLORS["SUCCESS"]
    )
    embed.add_field(name="المستخدم", value=member.mention, inline=True)
    embed.add_field(name="الرتبة", value=role.mention, inline=True)
    embed.add_field(name="المشرف", value=ctx.author.mention, inline=True)
    
    await ctx.send(embed=embed)

# ---------- نظام الألعاب المتقدم ----------
@bot.command(name="لعبة")
async def games_menu(ctx):
    embed = discord.Embed(
        title="🎮 مركز الألعاب",
        description="**اختر لعبة للعب:**",
        color=COLORS["GOLD"]
    )
    
    games = [
        {"name": "🎮 حجر ورقة مقص", "desc": "!حجر_ورقة_مقص"},
        {"name": "🎲 الروليت", "desc": "!روليت [المبلغ]"},
        {"name": "❓ مسابقة برمجية", "desc": "!مسابقة"},
        {"name": "💭 سؤال وجواب", "desc": "!سؤال"},
        {"name": "🎯 التخمين", "desc": "!تخمين [1-100]"},
        {"name": "♟️ شطرنج", "desc": "!شطرنج @الخصم"}
    ]
    
    for game in games:
        embed.add_field(name=game["name"], value=game["desc"], inline=False)
    
    view = View()
    
    # أزرار الألعاب
    game_buttons = [
        Button(label="✊✋✌️", style=discord.ButtonStyle.green, custom_id="play_rps"),
        Button(label="🎲", style=discord.ButtonStyle.blurple, custom_id="play_roulette"),
        Button(label="❓", style=discord.ButtonStyle.gray, custom_id="play_quiz")
    ]
    
    for button in game_buttons:
        view.add_item(button)
    
    await ctx.send(embed=embed, view=view)

@bot.command(name="حجر_ورقة_مقص")
async def rps(ctx):
    embed = discord.Embed(
        title="🎮 حجر ورقة مقص",
        description="**اختر حركتك:**",
        color=COLORS["GOLD"]
    )
    
    await ctx.send(embed=embed, view=GameView("rps"))

@bot.command(name="روليت")
async def roulette(ctx, bet: int = 100):
    if bet <= 0:
        await ctx.send("❌ الرقم يجب أن يكون أكبر من صفر")
        return
    
    # تحقق من رصيد المستخدم (هنا يمكنك ربطه بنظام اقتصاد)
    result = random.randint(1, 37)
    color = "🔴" if result % 2 == 1 else "⚫" if result != 0 else "🟢"
    
    if result == random.randint(1, 37):
        win_amount = bet * 35
        embed = discord.Embed(
            title="🎲 الروليت",
            description=f"**🎉 فزت!**\nالرقم: {result} {color}",
            color=COLORS["SUCCESS"]
        )
        embed.add_field(name="💰 رهانك", value=f"{bet} نقطة", inline=True)
        embed.add_field(name="💰 فوزك", value=f"{win_amount} نقطة", inline=True)
    else:
        embed = discord.Embed(
            title="🎲 الروليت",
            description=f"**💥 خسرت!**\nالرقم: {result} {color}",
            color=COLORS["ERROR"]
        )
        embed.add_field(name="💰 رهانك", value=f"{bet} نقطة", inline=True)
        embed.add_field(name="💸 الخسارة", value=f"{bet} نقطة", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name="سؤال")
async def programming_quiz(ctx):
    questions = [
        {
            "question": "ما لغة البرمجة التي تستخدم للذكاء الاصطناعي بشكل كبير؟",
            "options": ["بايثون", "جافا", "سي++", "جافا سكريبت"],
            "answer": 0
        },
        {
            "question": "ما هي مكتبة React المستخدمة فيها؟",
            "options": ["بايثون", "جافا سكريبت", "سي#", "روبي"],
            "answer": 1
        },
        {
            "question": "ما هي أقدم لغة برمجة؟",
            "options": ["فورتران", "بايثون", "جافا", "سي++"],
            "answer": 0
        }
    ]
    
    q = random.choice(questions)
    
    embed = discord.Embed(
        title="❓ سؤال برمجي",
        description=q["question"],
        color=COLORS["INFO"]
    )
    
    for i, option in enumerate(q["options"]):
        embed.add_field(name=f"الخيار {i+1}", value=option, inline=True)
    
    await ctx.send(embed=embed)
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content in ["1", "2", "3", "4"]
    
    try:
        msg = await bot.wait_for("message", timeout=30.0, check=check)
        
        if int(msg.content) - 1 == q["answer"]:
            await ctx.send("✅ إجابة صحيحة! +50 نقطة")
        else:
            await ctx.send(f"❌ إجابة خاطئة! الإجابة الصحيحة هي: {q['options'][q['answer']]}")
    except asyncio.TimeoutError:
        await ctx.send("⏰ انتهى الوقت!")

# ---------- نظام المستويات ----------
@bot.command(name="مستواي")
async def my_level(ctx, member: discord.Member = None):
    if not member:
        member = ctx.author
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("SELECT xp, level FROM levels WHERE user_id = ?", (str(member.id),))
    result = c.fetchone()
    
    if result:
        xp, level = result
        needed_xp = 100 * (level ** 2)
        
        embed = discord.Embed(
            title=f"📊 مستوى {member.name}",
            color=member.color
        )
        
        embed.add_field(name="📈 المستوى", value=f"**{level}**", inline=True)
        embed.add_field(name="⚡ النقاط", value=f"**{xp}/{needed_xp}**", inline=True)
        embed.add_field(name="🏆 التقدم", value=f"{int((xp/needed_xp)*100)}%", inline=True)
        
        # شريط التقدم
        progress_bar = "█" * int((xp/needed_xp) * 20) + "░" * (20 - int((xp/needed_xp) * 20))
        embed.add_field(name="📊 شريط التقدم", value=f"`{progress_bar}`", inline=False)
        
        # الرتبة في السيرفر
        rank_query = """
        SELECT COUNT(*) FROM levels 
        WHERE xp > (SELECT xp FROM levels WHERE user_id = ?)
        """
        c.execute(rank_query, (str(member.id),))
        rank = c.fetchone()[0] + 1
        embed.add_field(name="🏅 المرتبة", value=f"#{rank}", inline=True)
        
        conn.close()
        
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ لم يتم العثور على بيانات المستخدم")

@bot.command(name="التصنيف")
async def leaderboard(ctx):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("SELECT user_id, level, xp FROM levels ORDER BY xp DESC LIMIT 10")
    top_users = c.fetchall()
    
    embed = discord.Embed(
        title="🏆 لوحة المتصدرين",
        description="**أفضل 10 لاعبين حسب النقاط:**",
        color=COLORS["GOLD"]
    )
    
    for i, (user_id, level, xp) in enumerate(top_users, 1):
        try:
            user = await bot.fetch_user(int(user_id))
            username = user.name
        except:
            username = "مستخدم غير معروف"
        
        embed.add_field(
            name=f"{i}. {username}",
            value=f"المستوى: {level} | النقاط: {xp}",
            inline=False
        )
    
    conn.close()
    
    await ctx.send(embed=embed)

# ---------- نظام التذاكر المتقدم ----------
@bot.command(name="لوحة_التذاكر")
@commands.has_permissions(manage_channels=True)
async def ticket_panel(ctx):
    embed = discord.Embed(
        title="🎫 لوحة التذاكر",
        description="**انقر على الزر لفتح تذكرة دعم فني:**\n\n• مشاكل تقنية\n• استفسارات\n• اقتراحات\n• شكاوى",
        color=COLORS["INFO"]
    )
    
    embed.add_field(name="📌 التعليمات", value="1. اختر نوع المشكلة\n2. انتظر رد المسؤول\n3. قدم التفاصيل اللازمة", inline=False)
    embed.add_field(name="⏱️ وقت الاستجابة", value="24 ساعة كحد أقصى", inline=True)
    embed.add_field(name="📞 الدعم", value="@المسؤولين", inline=True)
    
    await ctx.send(embed=embed, view=TicketView())

# ---------- نظام الإعدادات ----------
@bot.command(name="اعدادات")
@commands.has_permissions(administrator=True)
async def server_settings(ctx):
    embed = discord.Embed(
        title="⚙️ إعدادات السيرفر",
        color=COLORS["PURPLE"]
    )
    
    # إحصائيات السيرفر
    embed.add_field(name="👥 الأعضاء", value=ctx.guild.member_count, inline=True)
    embed.add_field(name="📁 القنوات", value=len(ctx.guild.channels), inline=True)
    embed.add_field(name="🎭 الرتب", value=len(ctx.guild.roles), inline=True)
    
    # إعدادات النظام
    embed.add_field(name="🛡️ نظام التحذيرات", value="✅ مفعل", inline=True)
    embed.add_field(name="📊 نظام المستويات", value="✅ مفعل", inline=True)
    embed.add_field(name="🎮 نظام الألعاب", value="✅ مفعل", inline=True)
    
    # معلومات البوت
    embed.add_field(name="🤖 صلاحيات البوت", 
                   value="\n".join([perm for perm, value in ctx.guild.me.guild_permissions if value]), 
                   inline=False)
    
    view = View()
    buttons = [
        Button(label="تحديث الإحصائيات", style=discord.ButtonStyle.green, custom_id="refresh_stats"),
        Button(label="إعدادات الترحيب", style=discord.ButtonStyle.blurple, custom_id="welcome_settings"),
        Button(label="إعدادات السجل", style=discord.ButtonStyle.gray, custom_id="log_settings")
    ]
    
    for button in buttons:
        view.add_item(button)
    
    await ctx.send(embed=embed, view=view)

# ---------- نظام السجل (Logging) ----------
@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    
    log_channel = discord.utils.get(message.guild.text_channels, name="📜-السجل")
    if log_channel:
        embed = discord.Embed(
            title="🗑️ حذف رسالة",
            color=COLORS["WARNING"]
        )
        embed.add_field(name="المستخدم", value=message.author.mention, inline=True)
        embed.add_field(name="القناة", value=message.channel.mention, inline=True)
        
        if message.content:
            embed.add_field(name="المحتوى", value=message.content[:1024], inline=False)
        
        embed.set_footer(text=f"ID: {message.id}")
        await log_channel.send(embed=embed)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return
    
    log_channel = discord.utils.get(before.guild.text_channels, name="📜-السجل")
    if log_channel:
        embed = discord.Embed(
            title="✏️ تعديل رسالة",
            color=COLORS["INFO"]
        )
        embed.add_field(name="المستخدم", value=before.author.mention, inline=True)
        embed.add_field(name="القناة", value=before.channel.mention, inline=True)
        embed.add_field(name="قبل", value=before.content[:500] or "لا يوجد نص", inline=False)
        embed.add_field(name="بعد", value=after.content[:500] or "لا يوجد نص", inline=False)
        embed.add_field(name="الرابط", value=f"[اذهب للرسالة]({after.jump_url})", inline=True)
        
        await log_channel.send(embed=embed)

# ---------- نظام الباك أب التلقائي ----------
async def backup_data():
    """نظام نسخ احتياطي تلقائي"""
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backup_{timestamp}.db"
        
        import shutil
        shutil.copy2(DB_NAME, backup_file)
        
        # حفظ آخر 5 نسخ فقط
        backups = sorted([f for f in os.listdir() if f.startswith("backup_")])
        for old_backup in backups[:-5]:
            os.remove(old_backup)
            
        logger.info(f"✅ تم إنشاء نسخة احتياطية: {backup_file}")
    except Exception as e:
        logger.error(f"❌ فشل النسخ الاحتياطي: {e}")

# ---------- تشغيل البوت ----------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ الأمر غير موجود! اكتب `!مساعدة` لرؤية الأوامر المتاحة")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ ليس لديك الصلاحيات الكافية لهذا الأمر!")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ هناك معطيات ناقصة! اكتب `!مساعدة` لمعرفة كيفية الاستخدام")
    else:
        logger.error(f"خطأ غير متوقع: {error}")
        await ctx.send("❌ حدث خطأ غير متوقع!")

# مهمة النسخ الاحتياطي اليومي
@tasks.loop(hours=24)
async def daily_backup():
    await backup_data()

if __name__ == "__main__":
    keep_alive()
    
    # تشغيل المهام التلقائية
    daily_backup.start()
    
    TOKEN = os.environ.get('DISCORD_TOKEN')
    if TOKEN:
        logger.info("🚀 جاري تشغيل البوت المتكامل...")
        bot.run(TOKEN)
    else:

        logger.error("❌ لم يتم العثور على توكن البوت!")
