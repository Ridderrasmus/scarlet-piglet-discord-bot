from discord.ext import commands, tasks
from discord import ui, app_commands, Interaction
from discord.guild import GuildChannel
from a2squery import A2SQuery
from github import Github
import datetime
import discord
import schedule
import scarletpigsapi
import logging
import asyncio
import os
import xlsxwriter
import base64
import io
import emoji as emoji_lib

# Github setup
gh = Github(login_or_token=os.getenv("GITHUB_TOKEN"))

########################
### Helper functions ###
########################

### --- Discord reaction related functions --- ###


async def get_reactions_from_message(message: discord.Message):
    # Get message reactions and return out of the function if there are none
    msg_reactions = message.reactions
    if not msg_reactions:
        return None

    # For each reaction create dict with reaction name and list of users
    reactions = []
    for reaction in msg_reactions:
        name = reaction.emoji if not reaction.is_custom_emoji(
        ) else reaction.emoji.name  # type: ignore
        reactions.append({
            'emoji_name': name,
            'reactors': set([user async for user in reaction.users()])
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
            player_row.append(
                "X" if reaction['emoji_name'] in user_reactions[reactor] else "")
        player_rows.append(player_row)

    # Combine the header row and player rows into one list
    return ([header_row] + player_rows)

# Get a list of all discord and unicode emojis in the string
# TODO: Fix bug when unicode emojis are used directly after a discord emoji


def get_emojis_in_message(message: str):
    emoji_list = []
    for emoji in message.split():
        if emoji.startswith("<:"):
            tmp = emoji.replace("><", " ").replace(
                ">", " ").replace("<", " ").replace(":", " ").split()
            for e in tmp:
                if str.isnumeric(e):
                    emoji_list.append(int(e))
        else:
            for e in emoji_lib.distinct_emoji_list(emoji):
                emoji_list.append(emoji_lib.demojize(e))
    return emoji_list

# Remove reactions from a message by users not in a server


async def remove_reaction_if_not_member(message, reaction, user):
    guild = message.guild
    try:
        await guild.fetch_member(user.id)
    except discord.NotFound:
        await message.remove_reaction(reaction.emoji, user)
        return user
    return None

# Process reactions for a message


async def process_reaction(message, reaction: discord.Reaction):
    users = [user async for user in reaction.users()]
    for user in users:
        await remove_reaction_if_not_member(message, reaction, user)

    count = reaction.count
    updated_count = count - 1
    return updated_count


### --- Formatting related functions --- ###

# Function to format schedule message entries
def format_schedule_message_entry(entry: str, entry_type: int):
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
    if (len(entry) > length):  # type: ignore
        diff = len(entry) - (len(entry) - length)  # type: ignore
        diff = diff + 3
        entry = entry[:diff]
        entry += "..."

    # Pad the entry with spaces on the right if the entry is too short
    if (len(entry) < length):  # type: ignore
        entry = entry.ljust(length)  # type: ignore

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
        data = gh.get_repo(
            f"MacbainSP/Scarlet-Pigs-Server-Stuff").get_contents(file_path)
        if data == None:
            return None

        file_content = data.content  # type: ignore
        file_name = data.name  # type: ignore

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
        schedule_msg = None
        schedule_channel = None
        self.server_start_time: int | None = None  # type: ignore
        super().__init__(intents=discord.Intents.default())
        self.synced = False
        self.server_status = "offline"

    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced:
            print("Syncing commands...")
            for com in TREE.get_commands():
                print(f"Syncing {com.name}")
            await TREE.sync()
            self.synced = True
        loop_tasks.start()

    async def on_command_error(self, ctx, error):
        await ctx.reply(str(error), ephemeral=True)


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
            options.append(discord.SelectOption(
                label="No free dates", value="No free dates"))
        for i in range(0, len(next_sundays)):
            string = next_sundays[i][0]
            options.append(discord.SelectOption(label=string, value=string))
        super().__init__(placeholder="Choose the date",
                         min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.values[0] == "No free dates":
            embed = discord.Embed(title="No free dates", description="There are no free dates for the next 3 months.",
                                  timestamp=datetime.datetime.utcnow(), color=discord.Colour.red())
            embed.set_author(name=interaction.user,
                             icon_url=interaction.user.display_avatar)
            content = "No date picked."
        else:
            schedule.update_op(self.values[0], self.opname, self.opauthor)
            embed = discord.Embed(title="Reserved a Sunday", description=f"Op named {self.opname} made by {
                                  self.opauthor} is booked for {self.values[0]}.", timestamp=datetime.datetime.utcnow(), color=discord.Colour.blue())
            embed.set_author(name=interaction.user,
                             icon_url=interaction.user.display_avatar)
            content = "Date picked."

            # Add event to the API
            starttime = datetime.datetime.strptime(
                self.values[0], "%b %d (%y)").replace(hour=15, minute=0, second=0)
            endtime = datetime.datetime.strptime(
                self.values[0], "%b %d (%y)").replace(hour=18, minute=0, second=0)
            description = f"Op made by {self.opauthor}"
            authorid = interaction.user.id
            # Try API, fallback to just updating schedule
            try:
                scarletpigsapi.create_event(
                    self.opname, description, self.opauthor, authorid, starttime, endtime)
            except Exception as e:
                print(e)
        await update_scheduled_messages("schedule", schedule.get_schedule_messages())
        await interaction.edit_original_response(content=content, embed=embed, view=None)

# Define the edit op Select


class OpEditSelect(discord.ui.Select):
    def __init__(self, isDelete: bool = False):
        self.isDelete = isDelete
        next_booked_ops = schedule.get_booked_dates()
        options = []
        for booked_op in next_booked_ops:
            opname = booked_op[1]
            opdate = booked_op[0]
            options.append(discord.SelectOption(label=opname, value=opdate))
        super().__init__(placeholder="Choose the op",
                         min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        op = schedule.get_op_data(date=self.values[0])
        if op is None or len(op) < 3:
            await interaction.response.send_message(content="Could not find op data.", ephemeral=True)
            return
        if (self.isDelete):
            op_date = op[0]
            try:
                dt = datetime.datetime.strptime(
                    op_date, "%b %d (%y)").replace(hour=16, minute=0, second=0)
            except Exception:
                await interaction.response.send_message(content="Invalid op date format.", ephemeral=True)
                return
            event = scarletpigsapi.get_event_at_date(dt)
            if not event or "id" not in event:
                await interaction.response.send_message(content="Could not find event to delete.", ephemeral=True)
                return
            event_id = event["id"]
            scarletpigsapi.delete_event(event_id)
            schedule.delete_op(op_date)
            await interaction.response.send_message(content=f"Op {op[1]} deleted", ephemeral=True)
        else:
            await interaction.response.send_modal(OpEditModal(op[0], op[1], op[2]))


######################
### Modals (Forms) ###
######################

# Define the edit op modal
class OpEditModal(discord.ui.Modal, title="Edit an op"):
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

        # Try API, fallback to just updating schedule
        try:
            isodate = datetime.datetime.strptime(
                self.date, "%b %d (%y)").replace(hour=16, minute=0, second=0)
        except Exception:
            await interaction.followup.send(content="Invalid date format for event.", ephemeral=True)
            return
        event = try_api_call(scarletpigsapi.get_event_at_date, isodate)
        if event:
            event["name"] = self.opname.value
            event["description"] = f"Op made by {self.author.value}"
            try_api_call(scarletpigsapi.edit_event, event)

        await schedule_loop()
        embed = discord.Embed(title="Edited a Sunday", description=f"Op named {self.opname.value} made by {
                              self.author.value} is booked for {self.date}.", timestamp=datetime.datetime.utcnow(), color=discord.Colour.blue())
        await interaction.followup.send(content="Op edited (API fallback if needed)", embed=embed, ephemeral=True)

# Define the edit BOT message modal with the given variable when called (the message to edit)


class BOTMessageEditModal(discord.ui.Modal, title="Edit BOT message"):
    edit_message_textfield = ui.TextInput(
        style=discord.TextStyle.paragraph, label='Message', min_length=1, max_length=2000)
    # Get the message to edit

    def __init__(self, message):
        self.message = message
        self.edit_message_textfield.default = message.content
        super().__init__()

    async def on_submit(self, interaction: discord.Interaction):
        await self.message.edit(content=self.edit_message_textfield.value)
        await interaction.response.send_message("Message edited", ephemeral=True)


##################################
### Command conditions section ###
##################################
### Currently do not work      ###
##################################

# def has_reactions() -> bool:
#     async def predicate(ctx : commands.Context):
#         return len(ctx.message.reactions) > 0
#     return commands.check(predicate)

# def is_author() -> bool:
#     async def predicate(ctx : commands.Context):
#         return (ctx.message.author.id == ctx.user.id)
#     return commands.check(predicate)

# def BOT_is_author() -> bool:
#     async def predicate(ctx : commands.Context):
#         return (ctx.message.author.id == 1012077296515039324)
#     return commands.check(predicate)

###############################
### Hybrid commands section ###
###############################

# Register the send message
@TREE.command(name="send", description="Send a message")
@app_commands.checks.has_role("ServerOps")
async def send(interaction: Interaction, message: str):
    channel = getattr(interaction, 'channel', None)
    if channel is None or not hasattr(channel, 'send'):
        await interaction.response.send_message(content="Could not resolve channel to send message.", ephemeral=True)
        return
    await interaction.response.send_message(content="Message sent.", ephemeral=True)
    await channel.send(message)

# Register the reserve sunday command


@TREE.command(name="reservesunday", description="Reserve a sunday")
@app_commands.checks.has_role("Mission Maker")
async def reservesunday(interaction: discord.Interaction, opname: str, authorname: str):
    await interaction.response.defer(ephemeral=True)
    view = discord.ui.View(timeout=180).add_item(
        DateSelect(opname, authorname))
    await interaction.followup.send(content="Reserved an op. Now pick the date: ", view=view)

# Register the edit op command


@TREE.command(name="editsunday", description="Edit a booked op")
@app_commands.checks.has_role("Mission Maker")
async def editsunday(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    view = discord.ui.View(timeout=180).add_item(OpEditSelect())
    await interaction.followup.send(content="Which op do you want to edit? ", view=view)


# Register the delete op command


@TREE.command(name="deletesunday", description="Delete a booked op")
@app_commands.checks.has_role("Mission Maker")
async def deletesunday(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    view = discord.ui.View(timeout=180).add_item(OpEditSelect(isDelete=True))
    await interaction.followup.send(content="Which op do you want to delete? ", view=view)


# Register the create schedule message command


@TREE.command(name="createschedule", description="Create an op schedule in this channel")
@app_commands.checks.has_role("Unit Organizer")
async def createschedule(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild_id
    channel = getattr(interaction, 'channel', None)
    if channel is None or not hasattr(channel, 'send'):
        await interaction.followup.send(content="Could not resolve channel to send schedule.", ephemeral=True)
        return
    schedule_messages = schedule.get_schedule_messages()
    guild_ids = [server['guild_id'] for server in schedule_messages['servers']]

    if (guild_id in guild_ids):
        index = guild_ids.index(guild_id)
        old_channel = BOT.get_channel(
            schedule_messages['servers'][index]['channel_id'])
        if old_channel is not None and isinstance(old_channel, discord.TextChannel):
            try:
                old_msg = await old_channel.fetch_message(schedule_messages['servers'][index]['message_id'])
                await old_msg.delete()
            except Exception:
                print("Couldn't delete old message")

    new_msg = await channel.send(content=format_schedule_message())
    if guild_id is None or not hasattr(channel, 'id') or not hasattr(new_msg, 'id'):
        await interaction.followup.send(content="Could not resolve guild/channel/message id.", ephemeral=True)
        return
    schedule.set_schedule_message_id(guild_id, channel.id, new_msg.id)
    await interaction.followup.send(content="Op schedule created.")

# Register the create modlist message command


@TREE.command(name="createmodlist", description="Create a modlist message in this channel")
@app_commands.checks.has_role("Unit Organizer")
async def createmodlist(interaction: discord.Interaction, repofilepath: str):
    await interaction.response.defer(ephemeral=True)
    channel = getattr(interaction, 'channel', None)
    guild_id = interaction.guild_id
    if channel is None or not hasattr(channel, 'send'):
        await interaction.followup.send(content="Could not resolve channel to send modlist.", ephemeral=True)
        return
    file_name = retrieve_file_from_github(repofilepath)
    if (file_name == None):
        await interaction.followup.send(content="Couldn't find the file. Make sure the file exists and the path is correct. (An example path format would be Modlists/ScarletBannerKAT.html)", ephemeral=True)
        return
    msg = await channel.send(content=f"The modlist file: {file_name}", files=[discord.File(f"files/{file_name}")])
    os.remove(f"files/{file_name}")
    if guild_id is None or not hasattr(channel, 'id') or not hasattr(msg, 'id'):
        await interaction.followup.send(content="Could not resolve guild/channel/message id.", ephemeral=True)
        return
    schedule.add_modlist_message(guild_id, channel.id, msg.id, repofilepath)
    await interaction.followup.send(content="Modlist message created.", ephemeral=True)

# Register the create questionnaire message command


@TREE.command(name="createquestionnaire", description="Create DLC questionnaire in channel. (WARNING: Will delete any previous questionnaire messages)")
@app_commands.checks.has_role("Unit Organizer")
async def createquestionnaire(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild_id
    channel = getattr(interaction, 'channel', None)
    if channel is None or not hasattr(channel, 'send'):
        await interaction.followup.send(content="Could not resolve channel to send questionnaire.", ephemeral=True)
        return
    questionnaire_message = schedule.get_questionnaire_message()
    if (not questionnaire_message == None):
        # Check if the bot has access to the previous questionnaire message
        if ('guild_id' not in questionnaire_message or questionnaire_message['guild_id'] not in [guild.id for guild in BOT.guilds]):
            await interaction.followup.send(content="I do not have access to the previous questionnaire message.", ephemeral=True)
            return
        # Attempt to delete previous questionnaire message
        old_channel = BOT.get_channel(questionnaire_message['channel_id'])
        if old_channel is not None and hasattr(old_channel, 'fetch_message') and isinstance(old_channel, discord.TextChannel):
            try:
                old_msg = await old_channel.fetch_message(questionnaire_message['message_id'])
                await old_msg.delete()
            except Exception:
                print("Couldn't delete old message")
                pass
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
    if guild_id is None or not hasattr(channel, 'id') or not hasattr(new_msg, 'id'):
        await interaction.followup.send(content="Could not resolve guild/channel/message id.", ephemeral=True)
        return
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
async def add_signups(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(ephemeral=True)

    # Get all emojis from the message and from the guild
    emojis = get_emojis_in_message(message.content)

    if (len(emojis) == 0):
        await interaction.followup.send(content="Message has no emojis...")
        return

    # Add reactions to the message
    for emoji in emojis:
        if type(emoji) == int:
            if isinstance(interaction.guild, discord.Guild):
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
async def get_signups(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(ephemeral=True)

    # TODO: Make this also use the roles tags to show trainings
    # message.channel.members

    all_rows = await get_reactions_from_message(message)

    if (all_rows == None):
        await interaction.followup.send(content="Message has no reactions...")
        return

    # Create an in-memory stream for the Excel file
    stream = io.BytesIO()

    # Create excel file, sheet, and formatting to use in the file
    workbook = xlsxwriter.Workbook(stream)
    sheet = workbook.add_worksheet()
    workbook.set_custom_property("Encoding", "utf-8-sig")

    # Write the data to the sheet, close it, and then reset the stream pointer
    for i, row in enumerate(all_rows):
        sheet.write_row(i, 0, row)
    workbook.close()
    stream.seek(0)

    # Send the excel file to the user and close the stream
    await interaction.followup.send(content="Signups exported to Excel sheet.", files=[discord.File(stream, "signups.xlsx")])
    stream.close()

# Register the copy message context menu command
# Command will copy selected message and send it as the BOT


@TREE.context_menu(name="Copy message")
@app_commands.checks.has_role("ServerOps")
async def copy_message(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(ephemeral=True)
    message_content = message.content
    message_attachments = message.attachments
    message_embeds = message.embeds
    channel = getattr(interaction, 'channel', None)
    if channel is None or not hasattr(channel, 'send'):
        await interaction.followup.send(content="Could not resolve channel to send copied message.", ephemeral=True)
        return
    # Only send attachments that are of type discord.File
    files = []
    for att in message_attachments:
        if isinstance(att, discord.File):
            files.append(att)
    await interaction.followup.send(content="Message replaced.", ephemeral=True)
    await channel.send(content=message_content, files=files, embeds=message_embeds)

# Register the replace message context menu command
# Command will copy selected message and send it as the BOT


@TREE.context_menu(name="Edit message")
@app_commands.checks.has_role("ServerOps")
async def edit_message(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.send_modal(BOTMessageEditModal(message))


#####################
### Error Handler ###
#####################

# Error message function
async def error_response(interaction: discord.Interaction, message: str, expected: bool = True):
    try:
        await interaction.response.send_message(content=message, ephemeral=True)
    except Exception:
        await interaction.followup.send(content=message, ephemeral=True)
    finally:
        if not expected:
            creator_id = os.getenv('CREATOR_ID')
            try:
                creator_id_int = int(
                    creator_id) if creator_id is not None else None
            except Exception:
                creator_id_int = None
            if creator_id_int:
                creator = await BOT.fetch_user(creator_id_int)
                await creator.send(f"[{datetime.datetime.now()}] - {interaction.user} tried to use a command. Something went wrong! \n({message})")
            raise Exception(message)


@TREE.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await error_response(interaction, f'This command is on cooldown. Try again in {round(error.retry_after)} seconds.')
    elif isinstance(error, app_commands.MissingRole):
        await error_response(interaction, "You do not have the required role for this command")
    else:
        await error_response(interaction, str(error), False)


##################
### Task Loops ###
##################

# Function to update the scheduled messages (Modlists, OP schedules, etc.)
async def update_scheduled_messages(category: str, messages: dict):
    print(f'Updating {category} messages...')
    for server in messages['servers']:
        # Check if the BOT is in the server
        guild_id = server['guild_id']
        guild = BOT.get_guild(guild_id)
        if guild is None:
            continue
        # Check if the BOT is in the channel
        channel_id = server['channel_id']
        channel = guild.get_channel(channel_id)
        if channel is None or not hasattr(channel, 'fetch_message'):
            continue
        # Check if the BOT has access to the message
        message_id = server['message_id']
        try:
            if isinstance(channel, discord.TextChannel):
                msg = await channel.fetch_message(message_id)
        except Exception:
            print(f'The {category} message for {getattr(guild, "name", "?")} in channel {getattr(channel, "name", "?")} could not be found! Removing it from the database.')
            if category == "schedule":
                schedule.remove_schedule_message(message_id)
            elif category == "modlist":
                schedule.remove_modlist_message(message_id)
            continue
        # Check if the BOT is the author of the message
        if not hasattr(msg, 'author') or not hasattr(BOT, 'user') or msg.author is None or BOT.user is None or msg.author.id != BOT.user.id:
            continue
        # Update the message
        print(
            f'Updating {category} for {getattr(guild, "name", "?")} in channel {getattr(channel, "name", "?")}')
        if category == "schedule":
            await msg.edit(content=format_schedule_message())
        elif category == "modlist":
            file_path = server['file_path']
            file_name = retrieve_file_from_github(file_path)
            await msg.edit(attachments=[discord.File(f"files/{file_name}")])
            os.remove(f"files/{file_name}")

# Function that checks DLC message


async def check_dlc_message():
    print('Updating DLC graph...')
    questionnaire_message = schedule.get_questionnaire_message()
    if questionnaire_message is None or 'guild_id' not in questionnaire_message or 'channel_id' not in questionnaire_message or 'message_id' not in questionnaire_message:
        return
    questionnaire_info = schedule.get_questionnaire_info()
    guild = BOT.get_guild(questionnaire_message['guild_id'])
    if guild is None:
        return
    channel = guild.get_channel(questionnaire_message['channel_id'])
    # Only proceed if channel has fetch_message (TextChannel, not Forum/Category)
    if channel is None or not hasattr(channel, 'fetch_message'):
        return
    fetch_message_fn = getattr(channel, 'fetch_message', None)
    if not callable(fetch_message_fn):
        return
    try:
        # Use typing.cast to help Pylance recognize this as a coroutine function
        import typing
        fetch_message_coro = typing.cast(
            "typing.Callable[[int], typing.Awaitable[discord.Message]]", fetch_message_fn)
        message = await fetch_message_coro(questionnaire_message['message_id'])
    except Exception:
        return
    reactions = message.reactions
    updated_counts = await asyncio.gather(*(process_reaction(message, reaction) for reaction in reactions))
    updated_questionnaire_info = [questionnaire_info[0]] + [
        [info[0], updated_counts[i], info[2]] for i, info in enumerate(questionnaire_info[1:])]
    schedule.set_questionnaire_info(updated_questionnaire_info)


# The main bulk of the schedule loop
async def schedule_loop():
    await BOT.wait_until_ready()

    if not BOT.is_closed():
        try:
            asyncio.create_task(check_dlc_message())
        except Exception as e:
            print(e)
            pass

        try:
            asyncio.create_task(update_scheduled_messages(
                "schedule", schedule.get_schedule_messages()))
        except Exception as e:
            print(e)
            pass

        try:
            asyncio.create_task(update_scheduled_messages(
                "modlist", schedule.get_modlist_messages()))
        except Exception as e:
            print(e)
            pass


# The main bulk of the activity loop
async def activity_loop():

    if not BOT.is_closed():

        print("Updating server status...")

        server_ip = os.getenv("SERVER_IP")
        server_port = os.getenv("SERVER_PORT")
        if not server_ip or not server_port:
            await BOT.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"an offline server"))
            print("SERVER_IP or SERVER_PORT not set.")
            return
        try:
            port_int = int(server_port) + 1
        except Exception:
            await BOT.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"an offline server"))
            print("SERVER_PORT is not a valid integer.")
            return
        try:
            with A2SQuery(server_ip, port_int, timeout=7) as a2s:
                if BOT.server_status == "offline":
                    BOT.server_start_time = int(datetime.datetime.now().replace(
                        # type: ignore
                        tzinfo=datetime.timezone.utc).timestamp() * 1000)
                    BOT.server_status = "online"
                num_players = a2s.info().players
                mission = a2s.info().game
                plural_str = "s" if num_players != 1 else ""
                await BOT.change_presence(activity=discord.Activity(application_id=1035166922033082468, assets={"large_image": "pigs_patch", "large_text": "The Scarlet Pigs Server", "small_image": "pigs_patch", "small_text": "The Scarlet Pigs Server"}, type=discord.ActivityType.watching, name=f"{num_players} player" + plural_str + f" on {mission}", state="Running", timestamps={"start": BOT.server_start_time, "end": None}))
                print("Updated server status to online - Start time set to " +
                      str(BOT.server_start_time))
        except TimeoutError:
            await BOT.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"an offline server"))
            if BOT.server_status == "online":
                BOT.server_start_time = None
                BOT.server_status = "offline"
                print("Updated server status to offline")
            pass
        except Exception as e:
            if BOT.server_status == "online":
                BOT.server_start_time = None
                BOT.server_status = "offline"
            print(e)
            print("Something went wrong while updating the server status")
            await BOT.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"an offline server"))
            pass

        print("Checked server status")


@tasks.loop(minutes=1)
async def loop_tasks():
    await BOT.wait_until_ready()
    i = loop_tasks.current_loop
    if i == 0:
        print("Started loop tasks")
    if (i % 2) == 0:
        await activity_loop()
    if (i % 60) == 0:
        await schedule_loop()
        await activity_loop()

# Utility: fallback API call wrapper


def try_api_call(api_func, *args, **kwargs):
    try:
        return api_func(*args, **kwargs)
    except Exception as e:
        logging.error(f"API call failed: {e}")
        return None
