from discord.ext import commands, tasks
from discord import ui, app_commands, Interaction
import github3
import datetime
import discord
import schedule
import os
import xlsxwriter
import base64
import io

## Github setup
gh = github3.login(username=os.getenv("GITHUB_USERNAME"), password=os.getenv("GITHUB_PASSWORD"), token=os.getenv("GITHUB_TOKEN"))

#########################
### Defined functions ###
#########################

### --- Schedule related functions --- ###

# Function to format schedule message entries
def format_schedule_message_entry(entry : str, entry_type : int):
    lmargin = 1
    # This is gathered from the index of the entry
    match entry_type:
        # Date
        case 0:
            entry = entry[:-4]
            length = 12
            lmargin = 3
        # Op
        case 1:
            length = 33
        # Author
        case 2:
            length = 13
    
    # If the entry is empty, fill it with "Free"
    if entry == "":
        entry = "Free"
    
    # Pad the entry with spaces on the left
    entry = entry.rjust(len(entry) + lmargin)
    
    # If the entry is too long, trim it
    if(len(entry) > length):
        diff = len(entry) - (len(entry) - length)
        diff = diff + 3
        entry = entry[:diff]
        entry += "..."
    
    # Pad the entry with spaces on the right if the entry is too short
    if(len(entry) < length):
        entry = entry.ljust(length)
    
    return entry

# The function to format the schedule message
def format_schedule_message():
    formatted_schedule = ""
    this_schedule = schedule.get_full_schedule()
    for booking in this_schedule:
        date = format_schedule_message_entry(booking[0], 0)
        op = format_schedule_message_entry(booking[1], 1)
        author = format_schedule_message_entry(booking[2], 2)
        formatted_schedule += f'{date}|{author}|{op}\n'
        if this_schedule.index(booking) != len(this_schedule) - 1:
            formatted_schedule += f"\n"
    return f"```{formatted_schedule}```"

### --- Github related functions --- ###

# Function to copy file from github repo using given file path and then return the file name
def retrieve_file_from_github(username : str, repository : str, file_path: str):
    try:
        data = gh.repository(owner=username, repository=repository).file_contents(path=file_path)
        if data == None:
            return None
    except:
        return None
    
    data_dict = data.as_dict()
    file_content = data_dict['content']
    file_name = data_dict['name']

    with open(f"files/{file_name}", "wb") as f:
        f.write(base64.decodebytes(file_content.encode('utf-8')))
    return file_name

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
        await interaction.edit_original_response(content="Date picked.", embed = embed, view=None)

# Define the edit op Select
class OpEditSelect(discord.ui.Select):
    def __init__(self):
        next_booked_ops = schedule.get_booked_dates()
        options = []
        for booked_op in next_booked_ops:
            opname = booked_op[1]
            opdate = booked_op[0]
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
### Currently do not work      ###
##################################

def has_reactions() -> bool:
    async def predicate(ctx : commands.Context):
        return len(ctx.message.reactions) > 0
    return commands.check(predicate)

def is_author() -> bool:
    async def predicate(ctx : commands.Context):
        return (ctx.message.author.id == ctx.user.id)
    return commands.check(predicate)

def bot_is_author() -> bool:
    async def predicate(ctx : commands.Context):
        return (ctx.message.author.id == 1012077296515039324)
    return commands.check(predicate)

###############################
### Hybrid commands section ###
###############################

# Register the send message
@tree.command(name="send", description="Send a message")
@app_commands.checks.has_role("ServerOps")
async def send(interaction: Interaction, message: str):
    channel = await interaction.channel._get_channel()
    await interaction.response.send_message(content="Message sent.", ephemeral=True)
    await channel.send(message)

# Register the reserve sunday command 
@tree.command(name="reservesunday", description="Reserve a sunday")
@app_commands.checks.has_role("Mission Maker")
async def reservesunday(interaction: discord.Interaction, opname: str, authorname: str):
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
@tree.command(name="createschedule", description="Create an op schedule in this channel")
@app_commands.checks.has_role("Unit Organizer")
async def createschedule(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild_id
    channel = interaction.channel
    schedule_messages = schedule.get_schedule_messages()
    guild_ids = [server['guild_id'] for server in schedule_messages['servers']]
    
    if (guild_id in guild_ids):
        index = guild_ids.index(guild_id)
        old_channel = bot.get_channel(schedule_messages['servers'][index]['channel_id'])
        try:
            old_msg = await old_channel.fetch_message(schedule_messages['servers'][index]['message_id'])
            await old_msg.delete()
        except:
            print("Couldn't delete old message")
        
    new_msg = await channel.send(content=format_schedule_message())
    
    schedule.set_schedule_message_id(guild_id, channel.id, new_msg.id)
    await interaction.followup.send(content="Op schedule created.")
    
# Register the create modlist message command
@tree.command(name="createmodlist", description="Create a modlist message in this channel")
@app_commands.checks.has_role("Unit Organizer")
async def createmodlist(interaction: discord.Interaction, repofilepath : str):
    await interaction.response.defer(ephemeral=True)
    
    channel = interaction.channel
    guild_id = interaction.guild_id

    file = retrieve_file_from_github("MacbainSP", "Scarlet-Pigs-Server-Stuff", repofilepath)
    if (file == None):
        await interaction.followup.send(content="Couldn't find the file. Make sure the file exists and the path is correct. (An example path format would be Modlists/ScarletBannerKAT.html)", ephemeral=True)
        return
    
    msg = await channel.send(content=f"The modlist file: {file}", files=[discord.File(f"files/{file}")])
    os.remove(f"files/{file}")
    
    schedule.add_modlist_message(guild_id, channel.id, msg.id, repofilepath)

    await interaction.followup.send(content="Modlist message created.", ephemeral=True)

    
    

################################
### Context commands section ###
################################

# Register the get signups context menu command
# Get reactions from a message and returns them as a nice excel sheet
@tree.context_menu(name="Get signups")
@app_commands.checks.has_role("Mission Maker")
@app_commands.checks.cooldown(rate=1, per=120)
@has_reactions()
async def get_signups(interaction : discord.Interaction, message: discord.Message):
    await interaction.response.defer(ephemeral=True)
    
    # TODO: Make this also use the roles tags to show trainings
    # message.channel.members
    
    # Get message reactions and return out of the function if there are none
    msg_reactions = message.reactions
    if not msg_reactions:
        await interaction.followup.send(content="Message has no reactions...")
        return
    
    # For each reaction create dict with reaction name and list of users
    reactions = []
    for reaction in msg_reactions:
        name = reaction.emoji if not reaction.is_custom_emoji() else reaction.emoji.name
        reactions.append({
            'emoji_name': name,
            'reactors' : set([user async for user in reaction.users()])
        })
    
    # Get all the users that reacted to the message
    all_reactors = set()
    for reaction in reactions:
        all_reactors.update(reaction['reactors'])
    all_reactors = list(all_reactors)
    
    # Create a dictionary mapping each user to a list of their reactions
    user_reactions = {reactor: set() for reactor in all_reactors}
    for reaction in reactions:
        for reactor in reaction['reactors']:
            user_reactions[reactor].add(reaction['emoji_name'])
    
    # Create header row
    header_row = ["Name"]
    for reaction in reactions:
        header_row.append(reaction["emoji_name"])
        
    # Create rows for each player with their reactions
    player_rows = []
    for reactor in all_reactors:
        player_row = [reactor.display_name]
        for reaction in reactions:
            player_row.append("X" if reaction['emoji_name'] in user_reactions[reactor] else "")
        player_rows.append(player_row)
        
    # Combine the header row and player rows into one list
    all_rows = [header_row] + player_rows
        
    # Create an in-memory stream for the Excel file
    stream = io.BytesIO()

    #Create excel file, sheet, and formatting to use in the file
    workbook = xlsxwriter.Workbook(stream)
    sheet = workbook.add_worksheet()
    workbook.set_custom_property("Encoding", "utf-8-sig")
    
    # Write the data to the sheet, close it, and then reset the stream pointer
    for row, data in enumerate(all_rows):
        sheet.write_row(row, 0, data)
    workbook.close()
    stream.seek(0)
    
    #Send the excel file to the user and close the stream
    await interaction.followup.send(content="Signups exported to Excel sheet.", files=[discord.File(stream, "signups.xlsx")])
    stream.close()
    
# Register the replace message context menu command
# Command will copy selected message and send it as the bot
@tree.context_menu(name="Replace message")
@app_commands.checks.has_role("ServerOps")
@is_author()
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
@bot_is_author()
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

async def update_scheduled_messages(category : str, messages : dict):
    for server in messages['servers']:
                # Check if the bot is in the server
                guild_id = server['guild_id']
                guild = bot.get_guild(guild_id)
                if guild_id not in [guild.id for guild in bot.guilds]:
                    continue
                
                # Check if the bot is in the channel
                channel_id = server['channel_id']
                channel = guild.get_channel(channel_id)
                if channel == None:
                    continue
                
                # Check if the bot has access to the message
                message_id = server['message_id']
                msg = await channel.fetch_message(message_id)
                if msg == None:
                    print(f'The {category} message for {guild.name} in channel {channel.name} could not be found! Removing it from the database.')
                    if category == "schedule":
                        schedule.remove_schedule_message(message_id)
                    elif category == "modlist":
                        schedule.remove_modlist_message(message_id)
                    continue
                
                # Check if the bot is the author of the message
                if msg.author.id != bot.user.id:
                    continue
                
                # Update the message
                print(f'Updating {category} for {guild.name} in channel {channel.name}')
                if category == "schedule":
                    await msg.edit(content=format_schedule_message())
                elif category == "modlist":
                    file_path = server['file_path']
                    file = retrieve_file_from_github("MacbainSP", "Scarlet-Pigs-Server-Stuff", file_path)
                    await msg.edit(attachments=[discord.File(f"files/{file}")])
                    os.remove(f"files/{file}")


# Register the schedule loop task
@tasks.loop(hours=1)
async def schedule_loop():
    await bot.wait_until_ready()
    
    if not bot.is_closed():        
        await update_scheduled_messages("schedule", schedule.get_schedule_messages())
        await update_scheduled_messages("modlist", schedule.get_modlist_messages())
        
# Run the bot
bot.run(os.getenv('DISCORD_TOKEN'))
