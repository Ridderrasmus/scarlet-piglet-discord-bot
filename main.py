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
        await interaction.response.defer()
        schedule.update_op(self.values[0], BookedOp.OPName, BookedOp.OPAuthor)
        embed = discord.Embed(title = "Reserved a Sunday", description = f"Op named {BookedOp.OPName} made by {BookedOp.OPAuthor} is booked for {self.values[0]}.", timestamp = datetime.datetime.utcnow(), color = discord.Colour.blue())
        embed.set_author(name = interaction.user, icon_url = interaction.user.display_avatar)
        await schedule_loop()
        await interaction.edit_original_response(content="Date picked.", embed = embed)

# Define the edit op Select
class OpEditSelect(discord.ui.Select):
    def __init__(self):
        next_booked_ops = schedule.get_booked_dates()
        options = []
        for i in range(0, len(next_booked_ops)):
            opname = next_booked_ops[i][1]
            opdate = next_booked_ops[i][0]
            options.append(discord.SelectOption(label = opname, value = opdate))
        super().__init__(placeholder = "Choose the op", min_values=1, max_values=1, options = options)
    async def callback(self, interaction: discord.Interaction):
        date = schedule.get_op_data(date=self.values[0])
        await interaction.response.send_modal(OpEditModal(date[1], date[2]))
        BookedOp.OPDate = date[0]
        BookedOp.OPName = date[1]
        BookedOp.OPAuthor = date[2]
        
######################
### Modals (Forms) ###
######################

# Define the edit op modal
class OpEditModal(discord.ui.Modal, title = "Edit an op"):
    opname = ui.TextInput(label='OP Name', min_length=1, max_length=31)
    author = ui.TextInput(label='Author', min_length=1, max_length=15)
    
    def __init__(self, opnamevalue, authorvalue):
        self.opname.default = opnamevalue
        self.author.default = authorvalue
        super().__init__()

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        BookedOp.OPName = self.opname.value
        BookedOp.OPAuthor = self.author.value
        schedule.update_op(BookedOp.OPDate, BookedOp.OPName, BookedOp.OPAuthor)
        await schedule_loop()
        embed = discord.Embed(title = "Edited a Sunday", description = f"Op named {self.opname.value} made by {self.author.value} is booked for {BookedOp.OPDate}.", timestamp = datetime.datetime.utcnow(), color = discord.Colour.blue())
        await interaction.followup.send(content="Op edited", embed = embed)
        
# Define the edit bot message modal with the given variable when called (the message to edit)
class BotMessageEditModal(discord.ui.Modal, title = "Edit bot message"):
    edit_message_textfield = ui.TextInput(style=discord.TextStyle.paragraph, label='Message', min_length=1, max_length=2000)
    # Get the message to edit
    def __init__(self, message):
        self.message = message
        self.edit_message_textfield.default = message.content
        super().__init__()    

    async def on_submit(self, interaction: discord.Interaction):
        await self.message.edit(content = self.edit_message_textfield.value)
        await interaction.response.send_message("Message edited", ephemeral = True)
        



##################################
### Command conditions section ###
##################################

def has_reactions() -> bool:
    def predicate(ctx: discord.Interaction) -> bool:
        return (len(ctx.message.reactions) > 0)
    return app_commands.check(predicate)

def is_author() -> bool:
    def predicate(ctx: discord.Interaction) -> bool:
        return (ctx.message.author.id == ctx.user.id)
    return app_commands.check(predicate)

def bot_is_author() -> bool:
    def predicate(ctx: discord.Interaction) -> bool:
        return (ctx.message.author.id == 1012077296515039324)
    return app_commands.check(predicate)

###############################
### Hybrid commands section ###
###############################

# Register the send message
@tree.command(name="send", description="Send a message")
#@app_commands.describe(send="Message to send")
@app_commands.checks.has_role("ServerOps")
async def send(interaction: discord.Interaction, message: str):
    channel = await interaction.channel._get_channel()
    await interaction.response.send_message(content="Message sent.", ephemeral=True)
    await channel.send(message)

# Register the reserve sunday command 
@tree.command(name="reservesunday", description="Reserve a sunday")
#@app_commands.describe(opname="Name of the operation")
#@app_commands.describe(authorname="Your discord name")
@app_commands.checks.has_role("Mission Maker")
async def reservesunday(
        interaction: discord.Interaction, 
        opname: str, 
        authorname: str
    ):
    await interaction.response.defer(ephemeral=True)
    BookedOp.OPName = opname
    BookedOp.OPAuthor = authorname
    view = discord.ui.View(timeout=180).add_item(DateSelect())
    await interaction.followup.send(content="Reserved an op. Now pick the date: ", view=view)

# Register the edit op command
@tree.command(name="editsunday", description="Edit a booked op")
@app_commands.checks.has_role("Mission Maker")
async def editsunday(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    view = discord.ui.View(timeout=180).add_item(OpEditSelect())
    await interaction.followup.send(content="Which op do you want to edit? ", view=view)

# Register the create schedule message command
@tree.command(name="createschedule", description="Create op schedule in this channel")
@app_commands.checks.has_role("Unit Organizer")
async def createschedule(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    channel = interaction.channel
    schedule_messages = schedule.get_schedule_messages()
    guild_ids = [server['guild_id'] for server in schedule_messages['servers']]
    await interaction.response.defer(ephemeral=True)
    
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
    await interaction.followup.send(content="Op schedule created.")
    
    
    


################################
### Context commands section ###
################################

# Register the get signups context menu command
# Get reactions from a message and returns them as a nice excel sheet
@tree.context_menu(name="Get signups")
@app_commands.checks.has_role("Mission Maker")
@app_commands.checks.cooldown(rate=1, per=120)
@has_reactions()
async def get_signups(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(ephemeral=True)
    
    #Get message reactions and return out of the function if there are none
    msg_reactions = message.reactions
    if(len(msg_reactions) == 0):
        await interaction.followup.send(content="Message has no reactions.")
        return None
    
    #For each reaction create dict with reaction name and list of users
    reactions = []
    for x in msg_reactions:
        if x.is_custom_emoji():
            name = x.emoji.name
        else:
            name = x.emoji
        
        reaction = {
            'emoji': x.emoji,
            'emoji_name': name,
            'reactors' : [user.display_name async for user in x.users()]
        }
        reactions.append(reaction)
    
    #Get all the users that reacted to the message
    all_reactors = []
    for x in reactions:
        reacters = [user for user in x['reactors']]
        all_reactors = all_reactors + reacters
    all_reactors = list(set(all_reactors))
    
    #Create header row
    header_row = ["Name"]
    for x in reactions:
        name = x['emoji_name']
        header_row.append(f'{name}')
        
    #This for loop is the slowest part of the code. Need to speed it up. I imagine it's got to do with how we get each player for each reaction.
    #Should probably get everything we need at the beginning of the command to make it easier and hopefully quicker.
    
    #Create rows for each player with their reactions
    player_rows = []
    for reactor in all_reactors:
        player_row = [reactor]
        for x in reactions:
            if(reactor in [user for user in x['reactors']]):
                player_row.append("X")
            else:
                player_row.append("")
        player_rows.append(player_row)

    #Create excel file and write information into it
    workbook = xlsxwriter.Workbook('reactions.xlsx')
    sheet = workbook.add_worksheet()
    sheet.write_row(0, 0, header_row)
    for i in player_rows:
        sheet.write_row(player_rows.index(i)+1, 0, i)
    workbook.close()
    
    #Send the excel file to the user and delete the local file afterwards
    await interaction.followup.send(content="Signups exported to CSV.", attachments=[discord.File('reactions.xlsx')])
    os.remove('reactions.xlsx')
    
    
# Register the replace message context menu command
# Command will copy selected message and send it as the bot
@tree.context_menu(name="Replace message")
@app_commands.checks.has_role("ServerOps")
#@is_author()
async def replace_message(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(ephemeral=True)
    
    # Get the message contents and save them to variables
    message_content = message.content
    message_attachments = message.attachments
    message_embeds = message.embeds
    
    # Edit original message with the copied content
    await interaction.followup.send(content="Message replaced.", ephemeral=True)
    await interaction.channel.send(content=message_content, files=message_attachments, embeds=message_embeds)

# Register the replace message context menu command
# Command will copy selected message and send it as the bot
@tree.context_menu(name="Edit message")
@app_commands.checks.has_role("ServerOps")
#@bot_is_author()
async def edit_message(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.send_modal(BotMessageEditModal(message))


#####################
### Error Handler ###
#####################

@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        try:
            await interaction.response.send_message(content=f'This command is on cooldown. Try again in {error.retry_after} seconds.', ephemeral=True)
        except:
            await interaction.followup.send(content=f'This command is on cooldown. Try again in {error.retry_after} seconds.', ephemeral=True)
    
    elif isinstance(error, app_commands.MissingRole):
        try:
            await interaction.response.send_message("You do not have the required role for this command", ephemeral=True)
        except:
            await interaction.followup.send("You do not have the required role for this command", ephemeral=True)

    else:
        try:
            await interaction.response.send_message(error, ephemeral=True)
        except:
            await interaction.followup.send(error, ephemeral=True)
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
