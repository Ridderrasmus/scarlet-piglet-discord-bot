from discord.ext import commands, tasks
from discord import ui, app_commands, Interaction
from a2squery import A2SQuery
from github import Github
import datetime
import discord
import schedule
import os
import xlsxwriter
import base64
import io
import asyncio
import emoji as emoji_lib
import utils


## Github setup
gh = Github(login_or_token=os.getenv("GITHUB_TOKEN"))

########################
### Helper functions ###
########################

### --- Discord reaction related functions --- ###

async def get_reactions_from_message(message : discord.Message):
    # Get message reactions and return out of the function if there are none
    msg_reactions = message.reactions
    if not msg_reactions:
        return None
    
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
    return ([header_row] + player_rows)

# Get a list of all discord and unicode emojis in the string
# TODO: Fix bug when unicode emojis are used directly after a discord emoji
def get_emojis_in_message(message : str):
    emoji_list = []
    for emoji in message.split():
        if emoji.startswith("<:"):
            tmp = emoji.replace("><", " ").replace(">", " ").replace("<", " ").replace(":", " ").split()
            for e in tmp:
                if str.isnumeric(e):
                    emoji_list.append(int(e))
        else:
            for e in emoji_lib.distinct_emoji_list(emoji):
                emoji_list.append(emoji_lib.demojize(e))
    return emoji_list
    

### --- Formatting related functions --- ###

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

# Formats the list of DLCs into a nice reaction string
def format_dlc_list(dlclist):
    string = ""
    length = 20
    for i in range(1, len(dlclist)):
        dlc = dlclist[i]
        
        string += f"{dlc[2]} - {dlc[0]}\n"
        
    return string


### --- Github related functions --- ###

# Function to copy file from github repo using given file path and then return the file name
def retrieve_file_from_github(file_path: str):
    try:
        data = gh.get_repo(f"MacbainSP/Scarlet-Pigs-Server-Stuff").get_contents(file_path)
        if data == None:
            return None
        
        file_content = data.content
        file_name = data.name

        stream = io.BytesIO()
        os.makedirs("files", exist_ok=True)
        with open(f"files/{file_name}", "wb") as f:
            f.write(base64.decodebytes(file_content.encode('utf-8')))
        return file_name
    except Exception as e:
        print(e)
    
    

###############
### Classes ###
###############

# Define the BOT class
class SPiglet(discord.Client):
    def __init__(self):
        global schedule_msg
        global schedule_channel
        global server_start_time
        schedule_msg = None
        schedule_channel = None
        server_start_time = None
        super().__init__(intents=discord.Intents.default())
        self.synced = False
    
    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced:
            await TREE.sync()
            self.synced = True
        schedule_loop.start()
        activity_loop.start()
    
    async def on_command_error(self, ctx, error):
        await ctx.reply(error, ephemeral = True)

# Define the BOT and command TREE as variables (easier reference)
BOT = SPiglet()
TREE = app_commands.CommandTree(BOT)


################################
### Selects (Dropdown lists) ###
################################

# Define the reserve sunday Select
class DateSelect(discord.ui.Select):
    def __init__(self, opname, opauthor):
        self.opname = opname
        self.opauthor = opauthor
        next_sundays = schedule.get_free_dates()
        options = []
        if len(next_sundays) == 0:
            options.append(discord.SelectOption(label = "No free dates", value = "No free dates"))
        for i in range(0, len(next_sundays)):
            string = next_sundays[i][0]
            options.append(discord.SelectOption(label = string, value = string))
        super().__init__(placeholder = "Choose the date", min_values=1, max_values=1, options = options)
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.values[0] == "No free dates":
            embed = discord.Embed(title = "No free dates", description = "There are no free dates for the next 3 months.", timestamp = datetime.datetime.utcnow(), color = discord.Colour.red())
            embed.set_author(name = interaction.user, icon_url = interaction.user.display_avatar)
            content = "No date picked."
        else:
            schedule.update_op(self.values[0], self.opname, self.opauthor)
            embed = discord.Embed(title = "Reserved a Sunday", description = f"Op named {self.opname} made by {self.opauthor} is booked for {self.values[0]}.", timestamp = datetime.datetime.utcnow(), color = discord.Colour.blue())
            embed.set_author(name = interaction.user, icon_url = interaction.user.display_avatar)
            content = "Date picked."
        await schedule_loop()
        await interaction.edit_original_response(content=content, embed = embed, view=None)

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
        await interaction.response.send_modal(OpEditModal(date[0], date[1], date[2]))


######################
### Modals (Forms) ###
######################

# Define the edit op modal
class OpEditModal(discord.ui.Modal, title = "Edit an op"):
    opname = ui.TextInput(label='OP Name', min_length=1, max_length=31)
    author = ui.TextInput(label='Author', min_length=1, max_length=15)
    
    def __init__(self, date, opnamevalue, authorvalue):
        self.opname.default = opnamevalue
        self.author.default = authorvalue
        self.date = date
        super().__init__()

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        schedule.update_op(self.date, self.opname.value, self.author.value)
        await schedule_loop()
        embed = discord.Embed(title = "Edited a Sunday", description = f"Op named {self.opname.value} made by {self.author.value} is booked for {self.date}.", timestamp = datetime.datetime.utcnow(), color = discord.Colour.blue())
        await interaction.followup.send(content="Op edited", embed = embed, ephemeral = True)
        
# Define the edit BOT message modal with the given variable when called (the message to edit)
class BOTMessageEditModal(discord.ui.Modal, title = "Edit BOT message"):
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

def BOT_is_author() -> bool:
    async def predicate(ctx : commands.Context):
        return (ctx.message.author.id == 1012077296515039324)
    return commands.check(predicate)

###############################
### Hybrid commands section ###
###############################

# Register the send message
@TREE.command(name="send", description="Send a message")
@app_commands.checks.has_role("ServerOps")
async def send(interaction: Interaction, message: str):
    channel = await interaction.channel._get_channel()
    await interaction.response.send_message(content="Message sent.", ephemeral=True)
    await channel.send(message)

# Register the reserve sunday command 
@TREE.command(name="reservesunday", description="Reserve a sunday")
@app_commands.checks.has_role("Mission Maker")
async def reservesunday(interaction: discord.Interaction, opname: str, authorname: str):
    await interaction.response.defer(ephemeral=True)
    view = discord.ui.View(timeout=180).add_item(DateSelect(opname, authorname))
    await interaction.followup.send(content="Reserved an op. Now pick the date: ", view=view)

# Register the edit op command
@TREE.command(name="editsunday", description="Edit a booked op")
@app_commands.checks.has_role("Mission Maker")
async def editsunday(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    view = discord.ui.View(timeout=180).add_item(OpEditSelect())
    await interaction.followup.send(content="Which op do you want to edit? ", view=view)

# Register the create schedule message command
@TREE.command(name="createschedule", description="Create an op schedule in this channel")
@app_commands.checks.has_role("Unit Organizer")
async def createschedule(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild_id
    channel = interaction.channel
    schedule_messages = schedule.get_schedule_messages()
    guild_ids = [server['guild_id'] for server in schedule_messages['servers']]
    
    if (guild_id in guild_ids):
        index = guild_ids.index(guild_id)
        old_channel = BOT.get_channel(schedule_messages['servers'][index]['channel_id'])
        try:
            old_msg = await old_channel.fetch_message(schedule_messages['servers'][index]['message_id'])
            await old_msg.delete()
        except:
            print("Couldn't delete old message")
        
    new_msg = await channel.send(content=format_schedule_message())
    
    schedule.set_schedule_message_id(guild_id, channel.id, new_msg.id)
    await interaction.followup.send(content="Op schedule created.")
    
# Register the create modlist message command
@TREE.command(name="createmodlist", description="Create a modlist message in this channel")
@app_commands.checks.has_role("Unit Organizer")
async def createmodlist(interaction: discord.Interaction, repofilepath : str):
    await interaction.response.defer(ephemeral=True)
    
    channel = interaction.channel
    guild_id = interaction.guild_id

    file_name = retrieve_file_from_github(repofilepath)
    if (file_name == None):
        await interaction.followup.send(content="Couldn't find the file. Make sure the file exists and the path is correct. (An example path format would be Modlists/ScarletBannerKAT.html)", ephemeral=True)
        return
    
    msg = await channel.send(content=f"The modlist file: {file_name}", files=[discord.File(f"files/{file_name}")])
    os.remove(f"files/{file_name}")
    
    schedule.add_modlist_message(guild_id, channel.id, msg.id, repofilepath)

    await interaction.followup.send(content="Modlist message created.", ephemeral=True)
    
# Register the create questionnaire message command
@TREE.command(name="createquestionnaire", description="Create DLC questionnaire in channel. (WARNING: Will delete any previous questionnaire messages)")
@app_commands.checks.has_role("Unit Organizer")
async def createquestionnaire(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild_id
    channel = interaction.channel
    questionnaire_message = schedule.get_questionnaire_message()
    
    if (not questionnaire_message == None):
        # Check if the bot has access to the previous questionnaire message
        if(questionnaire_message['guild_id'] not in [guild.id for guild in BOT.guilds]):
            await interaction.followup.send(content="I do not have access to the previous questionnaire message.", ephemeral=True)
            return
        
        # Attempt to delete previous questionnaire message
        old_channel = BOT.get_channel(questionnaire_message['channel_id'])
        try:
            old_msg = await old_channel.fetch_message(questionnaire_message['message_id'])
            await old_msg.delete()
        except:
            print("Couldn't delete old message")
    
    dlcs = schedule.get_questionnaire_info()
    msg_content = f"**The Scarlet Pigs DLC Questionnaire**\n\nPlease react to this message with the DLCs you have to allow the mission makers to better keep track of which DLCs they can make use of.\n\n*DLCs:*\n{format_dlc_list(dlcs)}\n\n\nResults: https://docs.google.com/spreadsheets/d/e/2PACX-1vQYrmXaRK5P-FatQKhgiy6SEmyTX2sqSBvBxKg5Oz-hTYZMgeh8fFqgRD__mdSn5gC-3LqVC3u02WFJ/pubchart?oid=653336303&format=interactive"
    new_msg = await channel.send(content=msg_content, embeds=[])
    await interaction.followup.send(content="DLC questionnaire created.", ephemeral=True)
    
    await asyncio.sleep(1)
    
    # Add regional indicators as a reaction to the message
    for i, dlc in enumerate(dlcs, start=1):
        emoji = dlc[2]
        try:
            await new_msg.add_reaction(emoji)
        
        except Exception as error:
            print(f"Couldn't add reaction because {error}")
    
    schedule.set_questionnaire_message(guild_id, channel.id, new_msg.id)
    await check_dlc_message()

    
    

################################
### Context commands section ###
################################

# Register the add signups context menu command
# Get emojis from a message and add them to the message as reactions
@TREE.context_menu(name="Add signups")
@app_commands.checks.has_role("Mission Maker")
@app_commands.checks.cooldown(rate=1, per=120)
async def add_signups(interaction : discord.Interaction, message: discord.Message):
    await interaction.response.defer(ephemeral=True)
    
    # Get all emojis from the message and from the guild
    emojis = get_emojis_in_message(message.content)
    
    if (len(emojis) == 0):
        await interaction.followup.send(content="Message has no emojis...")
        return
        
    # Add reactions to the message
    for emoji in emojis:
        if type(emoji) == int:
            emoji = await interaction.guild.fetch_emoji(emoji)
            await message.add_reaction(emoji)
        else:
            try:
                emoji = emoji_lib.emojize(emoji)
                await message.add_reaction(emoji)
            except:
                print("Couldn't convert emoji to unicode")
    
    await interaction.followup.send(content="Reactions added to message.", ephemeral=True)


# Register the get signups context menu command
# Get reactions from a message and returns them as a nice excel sheet
@TREE.context_menu(name="Get signups")
@app_commands.checks.has_role("Mission Maker")
@app_commands.checks.cooldown(rate=1, per=120)
@has_reactions()
async def get_signups(interaction : discord.Interaction, message: discord.Message):
    await interaction.response.defer(ephemeral=True)
    
    # TODO: Make this also use the roles tags to show trainings
    # message.channel.members
    
    all_rows = await get_reactions_from_message(message)
    
    if (all_rows == None):
        await interaction.followup.send(content="Message has no reactions...")
        return
        
    # Create an in-memory stream for the Excel file
    stream = io.BytesIO()

    #Create excel file, sheet, and formatting to use in the file
    workbook = xlsxwriter.Workbook(stream)
    sheet = workbook.add_worksheet()
    workbook.set_custom_property("Encoding", "utf-8-sig")
    
    # Write the data to the sheet, close it, and then reset the stream pointer
    for i, row in enumerate(all_rows):
        sheet.write_row(i, 0, row)
    workbook.close()
    stream.seek(0)
    
    #Send the excel file to the user and close the stream
    await interaction.followup.send(content="Signups exported to Excel sheet.", files=[discord.File(stream, "signups.xlsx")])
    stream.close()
    
# Register the copy message context menu command
# Command will copy selected message and send it as the BOT
@TREE.context_menu(name="Copy message")
@app_commands.checks.has_role("ServerOps")
@is_author()
async def copy_message(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(ephemeral=True)
    
    # Get the message contents and save them to variables
    message_content = message.content
    message_attachments = message.attachments
    message_embeds = message.embeds
    
    # Edit original message with the copied content
    await interaction.followup.send(content="Message replaced.", ephemeral=True)
    await interaction.channel.send(content=message_content, files=message_attachments, embeds=message_embeds)

# Register the replace message context menu command
# Command will copy selected message and send it as the BOT
@TREE.context_menu(name="Edit message")
@app_commands.checks.has_role("ServerOps")
@BOT_is_author()
async def edit_message(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.send_modal(BOTMessageEditModal(message))


#####################
### Error Handler ###
#####################

# Error message function
async def error_response(interaction: discord.Interaction, message: str, expected: bool = True):
    try:
        await interaction.response.send_message(content=message, ephemeral=True)
    except:
        await interaction.followup.send(content=message, ephemeral=True)
    finally:
        if not expected:
            creator = await BOT.fetch_user(os.getenv('CREATOR_ID'))
            await creator.send(f"[{datetime.datetime.now()}] - {interaction.user} tried to use a command. Something went wrong! \n({message})")
            raise message

@TREE.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await error_response(interaction, f'This command is on cooldown. Try again in {round(error.retry_after)} seconds.')
    
    elif isinstance(error, app_commands.MissingRole):
        await error_response(interaction, "You do not have the required role for this command")
        
    else:
        await error_response(interaction, error, False)
        

##################
### Task Loops ###
##################

## Function to update the scheduled messages (Modlists, OP schedules, etc.)
async def update_scheduled_messages(category : str, messages : dict):
    for server in messages['servers']:
                # Check if the BOT is in the server
                guild_id = server['guild_id']
                guild = BOT.get_guild(guild_id)
                if guild_id not in [guild.id for guild in BOT.guilds]:
                    continue
                
                # Check if the BOT is in the channel
                channel_id = server['channel_id']
                channel = guild.get_channel(channel_id)
                if channel == None:
                    continue
                
                # Check if the BOT has access to the message
                message_id = server['message_id']
                msg = await channel.fetch_message(message_id)
                if msg == None:
                    print(f'The {category} message for {guild.name} in channel {channel.name} could not be found! Removing it from the database.')
                    if category == "schedule":
                        schedule.remove_schedule_message(message_id)
                    elif category == "modlist":
                        schedule.remove_modlist_message(message_id)
                    continue
                
                # Check if the BOT is the author of the message
                if msg.author.id != BOT.user.id:
                    continue
                
                # Update the message
                print(f'Updating {category} for {guild.name} in channel {channel.name}')
                if category == "schedule":
                    await msg.edit(content=format_schedule_message())
                elif category == "modlist":
                    file_path = server['file_path']
                    file_name = retrieve_file_from_github(file_path)
                    await msg.edit(attachments=[discord.File(f"files/{file_name}")])
                    os.remove(f"files/{file_name}")

# Function that checks DLC message
async def check_dlc_message():
    questionnaire_message = schedule.get_questionnaire_message()
    questionnaire_info = schedule.get_questionnaire_info()
    
    
    if questionnaire_message == None:
        return
    
    if questionnaire_message['guild_id'] not in [guild.id for guild in BOT.guilds]:
        return
    
    guild = BOT.get_guild(questionnaire_message['guild_id'])
    channel = guild.get_channel(questionnaire_message['channel_id'])
    message = await channel.fetch_message(questionnaire_message['message_id'])
    reactions = message.reactions
    
    
    legacy_users = []
    for i, reaction in enumerate(reactions):
        x = [user not in guild.members async for user in reaction.users()]
        if len(x) == 0:
            break
        for user in x:
            await message.remove_reaction(reaction.emoji, user)
        legacy_users.append(x)
        
        count = reaction.count
        questionnaire_info[i+1][1] = count - 1
        
    
    schedule.set_questionnaire_info(questionnaire_info)
    print("Updated DLC poll graph")
    


# Register the schedule loop task
@tasks.loop(hours=1)
async def schedule_loop():
    await BOT.wait_until_ready()
    
    if not BOT.is_closed():        
        try:
            await check_dlc_message()
            await update_scheduled_messages("schedule", schedule.get_schedule_messages())
            await update_scheduled_messages("modlist", schedule.get_modlist_messages())
            
        except:
            pass
        
# Register the bot status loop task
@tasks.loop(minutes=2)
async def activity_loop():
    
    
    if not BOT.is_closed():
        
        try:
            with A2SQuery(os.getenv("SERVER_IP"), int(os.getenv("SERVER_PORT")) + 1, timeout=5) as a2s:
                num_players = a2s.info().players
                duration = a2s.info().duration
                starttime = datetime.datetime.now() - datetime.timedelta(seconds=duration)
                mission = a2s.info().game
                plural_str = "s" if num_players != 1 else ""
                await BOT.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{num_players} player" + plural_str + f" on {mission}", timestamps={"start" : starttime}))
        except TimeoutError:
            await BOT.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"an offline server"))
        except Exception as e:
            print(e)
            await BOT.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"an offline server"))
