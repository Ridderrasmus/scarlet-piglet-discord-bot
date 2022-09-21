import datetime
import discord
import schedule
from discord.ext import commands, tasks
from discord import ui, app_commands
import os
import xlsxwriter


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
class SPiglet(discord.Client):
    def __init__(self):
        global schedule_msg
        global schedule_channel
        schedule_msg = None
        schedule_channel = None
        super().__init__(intents=discord.Intents.default())
        self.synced = False
        
    
    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced:
            await tree.sync()
            self.synced = True
        await schedule_loop.start()
    
    async def on_command_error(self, ctx, error):
        await ctx.reply(error, ephemeral = True)

# Define the bot and command tree as variables (easier reference)
bot = SPiglet()
tree = app_commands.CommandTree(bot)



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



##################################
### Command conditions section ###
##################################

def has_reactions():
    def predicate(ctx):
        return (len(ctx.message.reactions) > 0)
    return commands.check(predicate)



###############################
### Hybrid commands section ###
###############################

# Register the send message
@tree.command(name="send", description="Send a message")
@app_commands.checks.has_role("ServerOps")
async def send(interaction: discord.Interaction, message: str = None):
    channel = await interaction.channel._get_channel()
    await interaction.response.send_message(content="Message sent.", ephemeral=True)
    await channel.send(message)

# Register the reserve sunday command 
@tree.command(name="reservesunday", description="Reserve a sunday")
@app_commands.checks.has_role("Mission Maker")
async def reservesunday(interaction: discord.Interaction, opname: str = None, authorname: str = None):
    BookedOp.OPName = opname
    BookedOp.OPAuthor = authorname
    view = discord.ui.View(timeout=180).add_item(DateSelect())
    await interaction.response.send_message("Reserved an op. Now pick the date: ", view=view)

# Register the edit op command
@tree.command(name="editsunday", description="Edit a booked op")
@app_commands.checks.has_role("Mission Maker")
async def editsunday(interaction: discord.Interaction):
    view = discord.ui.View(timeout=180).add_item(OpEditSelect())
    await interaction.response.send_message("Which op do you want to edit? ", view=view)

# Register the create schedule message command
@tree.command(name="createschedule", description="Create op schedule in this channel")
@app_commands.checks.has_role("Unit Organizer")
async def createschedule(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    channel = interaction.channel
    schedule_messages = schedule.get_schedule_messages()
    guild_ids = [server['guild_id'] for server in schedule_messages['servers']]
    await interaction.response.send_message("Op schedule being created...", ephemeral=True)
    
    if (guild_id in guild_ids):
        index = guild_ids.index(guild_id)
        old_channel = bot.get_channel(schedule_messages['servers'][index]['channel_id'])
        try:
            old_msg = await old_channel.fetch_message(schedule_messages['servers'][index]['message_id'])
            await old_msg.delete()
        except:
            print("Couldn't delete old message")
        
    new_msg = await channel.send(content=format_schedule())
    
    schedule.set_schedule_message_id(guild_id, channel.id, new_msg.id)
    await interaction.edit_original_response(content="Op schedule created.")
    
    
    


################################
### Context commands section ###
################################

# Register the get signups context menu command
@tree.context_menu(name="Get signups")
@app_commands.checks.has_role("Mission Maker")
async def get_signups(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.send_message(content="Blegh", ephemeral=True)
    reactions = message.reactions
    users = []
    for i in range(0, len(reactions)):
        reacters = [user.display_name async for user in reactions[i].users()]
        users = users + reacters
    users = list(set(users))
    
    first_row = ["Name"]
    for i in reactions:
        if(i.is_custom_emoji()):
            emoji = i.emoji.name
        else:
            emoji = i.emoji
        first_row.append(f'{emoji}')
        
    player_rows = []
    for i in users:
        player_row = [i]
        for j in reactions:
            if(i in [user.display_name async for user in j.users()]):
                player_row.append("X")
            else:
                player_row.append("")
        player_rows.append(player_row)

    workbook = xlsxwriter.Workbook('reactions.xlsx')
    sheet = workbook.add_worksheet()
    sheet.write_row(0, 0, first_row)
    for i in player_rows:
        sheet.write_row(player_rows.index(i)+1, 0, i)
    workbook.close()

    await interaction.edit_original_response(content="Signups exported to CSV.", attachments=[discord.File('reactions.xlsx')])
    os.remove('reactions.xlsx')


#####################
### Error Handler ###
#####################

@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(error, ephemeral=True)
    elif isinstance(error, app_commands.MissingRole):
        await interaction.response.send_message(error, ephemeral=True)
    else:
        print("An error occured!")
        print(error)
        raise error


##################
### Task Loops ###
##################


# Register the schedule loop task
@tasks.loop(hours=1)
async def schedule_loop():
    await bot.wait_until_ready()
    
    if not bot.is_closed():
        
        
        schedule_messages = schedule.get_schedule_messages()
        
        for x in schedule_messages['servers']:
            guild_id = x['guild_id']
            guild = await bot.fetch_guild(guild_id)
            channel_id = x['channel_id']
            channel = bot.get_channel(channel_id)
            message_id = x['message_id']
            
            try:
                print(f'Updating schedule for {guild.name} in channel {channel.name}')
                msg = await channel.fetch_message(message_id)
                await msg.edit(content=format_schedule())
            except:
                print("Couldn't update schedule message")
            

    
        
# Run the bot
bot.run(os.getenv('DISCORD_TOKEN'))
