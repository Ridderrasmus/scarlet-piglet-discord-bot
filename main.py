import datetime
import discord
import schedule
from discord.ext import commands, tasks
from discord import ui, app_commands


#######################
### Defined methods ###
#######################

# The method to format the schedule message
def format_schedule():
    formatted_schedule = ""
    this_schedule = schedule.get_full_schedule()
    for i in range(0, len(this_schedule)):
        entry = this_schedule[i]
        date = entry[0]
        date = date[:-4]
        for i in range(len(date), 13):
            date += " "
        author = entry[2]
        if author == "":
            author = "Free"
        for i in range(len(author), 12):
            author += " "
        op = entry[1]
        if op == "":
            op = "Free"
        if len(op) > 29:
            for i in range(len(op), 29, -1):
                op = op[:-1]
            op += "..."
        else:
            for i in range(len(op), 32):
                op += " "
        
        formatted_schedule += f'   {date}| {author}| {op}\n'
        if i != len(this_schedule) - 1:
            formatted_schedule += f"\n"
    
    return f"```{formatted_schedule}```"

###############
### Classes ###
###############

# Define a booked op class
class BookedOp():
    OPName = ""
    OPAuthor = ""
    OPDate = ""

# Define the bot class
class SPiglet(commands.Bot):
    def __init__(self):
        global schedule_msg
        global schedule_channel
        schedule_msg = None
        schedule_channel = None
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        await self.tree.sync()
        print("Synced slash commands for {self.user}.")
    
    async def on_ready(self):
        await schedule_loop.start()
    
    async def on_command_error(self, ctx, error):
        await ctx.reply(error, ephemeral = True)

# Define the bot as a variable (easier reference)
bot = SPiglet(); 



################################
### Selects (Dropdown lists) ###
################################

# Define the reserve sunday Select
class DateSelect(discord.ui.Select):
    def __init__(self):
        next_sundays = schedule.get_free_dates()
        options = []
        for i in range(0, len(next_sundays)):
            string = next_sundays[i][0]
            options.append(discord.SelectOption(label = string, value = string))
        super().__init__(placeholder = "Choose the date", min_values=1, max_values=1, options = options)
    async def callback(self, interaction: discord.Interaction):
        schedule.update_op(self.values[0], BookedOp.OPName, BookedOp.OPAuthor)
        embed = discord.Embed(title = "Reserved a Sunday", description = f"Op named {BookedOp.OPName} made by {BookedOp.OPAuthor} is booked for {self.values[0]}.", timestamp = datetime.datetime.utcnow(), color = discord.Colour.blue())
        embed.set_author(name = interaction.user, icon_url = interaction.user.display_avatar)
        await schedule_loop()
        await interaction.response.edit_message(content="Date picked.", view=None, embed=embed)

# Define the edit op Select
class OpEditSelect(discord.ui.Select):
    def __init__(self):
        next_sundays = schedule.get_booked_dates()
        options = []
        for i in range(0, len(next_sundays)):
            opname = next_sundays[i][1]
            opdate = next_sundays[i][0]
            options.append(discord.SelectOption(label = opname, value = opdate))
        super().__init__(placeholder = "Choose the op", min_values=1, max_values=1, options = options)
    async def callback(self, interaction: discord.Interaction):
        date = schedule.get_op_data(date=self.values[0])
        BookedOp.OPDate = date[0]
        BookedOp.OPName = date[1]
        BookedOp.OPAuthor = date[2]
        await interaction.response.send_modal(OpEditModal())
        
######################
### Modals (Forms) ###
######################

# Define the edit op modal
class OpEditModal(discord.ui.Modal, title = "Edit an op"):
    opname = ui.TextInput(label='OP Name', min_length=1, max_length=31, default=BookedOp.OPName, placeholder=BookedOp.OPName)
    author = ui.TextInput(label='Author', min_length=1, max_length=15, default=BookedOp.OPAuthor, placeholder=BookedOp.OPAuthor)

    async def on_submit(self, interaction: discord.Interaction):
        BookedOp.OPName = self.opname.value
        BookedOp.OPAuthor = self.author.value
        schedule.update_op(BookedOp.OPDate, BookedOp.OPName, BookedOp.OPAuthor)
        await schedule_loop()
        await interaction.response.edit_message(content=f'{self.opname.value} edited. Author: {self.author.value}', view=None)




########################
### Commands section ###
########################

# Register the reserve sunday command 
@bot.hybrid_command("reservesunday", with_app_command=True, description="Reserve a sunday")
@app_commands.guilds()
@commands.has_role("Mission Maker")
async def reservesunday(ctx: commands.Context, opname: str = None, authorname: str = None):
    BookedOp.OPName = opname
    BookedOp.OPAuthor = authorname
    view = discord.ui.View(timeout=180).add_item(DateSelect())
    await ctx.send("Reserved an op. Now pick the date: ", view=view)

# Register the edit op command
@bot.hybrid_command("editsunday", with_app_command=True, description="Edit a booked op")
@app_commands.guilds()
@commands.has_role("Mission Maker")
async def editsunday(ctx: commands.Context):
    view = discord.ui.View(timeout=180).add_item(OpEditSelect())
    await ctx.send("Which op do you want to edit? ", view=view)

# Register the create schedule message command
@bot.hybrid_command("createschedule", with_app_command=True, description="Create op schedule in this channel")
@app_commands.guilds()
@commands.has_role("Mission Maker")
async def createschedule(ctx: commands.Context):
    schedule_channel = await ctx._get_channel()
    schedule_msg = schedule.get_schedule_message_id()
    if(schedule_msg != None and schedule_msg != []):
        schedule_msg = schedule_msg[1]
        try: 
            schedule_msg = await schedule_channel.fetch_message(schedule_msg)
            await schedule_msg.delete()
        except:
            schedule.set_schedule_message_id([])
        
        
    schedule_msg = await schedule_channel.send(content=format_schedule())
    schedule.set_schedule_message_id([schedule_channel.id, schedule_msg.id])
    await schedule_loop()
    await ctx.send("Op schedule created.", ephemeral=True)
   
   
##################
### Task Loops ###
##################


# Register the schedule loop task
@tasks.loop(hours=1)
async def schedule_loop():
    await bot.wait_until_ready()
    
    if not bot.is_closed():
        
        
        schedule_msg = schedule.get_schedule_message_id()
        
        if len(schedule_msg) == 2:
            schedule_channel = bot.get_channel(int(schedule_msg[0]))
            schedule_msg = schedule_msg[1]
            if (type(schedule_msg == "int")):
                schedule_msg = await schedule_channel.fetch_message(schedule_msg)
            if schedule_msg != None and schedule_msg != []:
                try:
                    await schedule_msg.edit(content=format_schedule())
                    
                except Exception as e:
                    print(str(e))
            

    
        
# Run the bot
bot.run("MTAxMjA3NzI5NjUxNTAzOTMyNA.GPqhzM.eodwFgc3CporxAAbb7z8uzb03lmxGL3-w1meC4")
