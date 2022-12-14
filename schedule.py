from genericpath import isfile
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
import os
import gspread
import datetime
import json



# Load environment variables
load_dotenv()
keyvar = {
    "type": os.getenv('TYPE'),
    "project_id": os.getenv('PROJECT_ID'),
    "private_key_id": os.getenv('PRIVATE_KEY_ID'),
    "private_key": os.getenv('PRIVATE_KEY').replace('\\n', '\n'),
    "client_email": os.getenv('CLIENT_EMAIL'),
    "client_id": os.getenv('CLIENT_ID'),
    "auth_uri": os.getenv('AUTH_URI'),
    "token_uri": os.getenv('TOKEN_URI'),
    "auth_provider_x509_cert_url": os.getenv('AUTH_PROVIDER_X509_CERT_URL'),
    "client_x509_cert_url": os.getenv('CLIENT_X509_CERT_URL')
}

# Set up sheets credentials
scope = ['https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict=keyvar, scopes=scope)
client = gspread.authorize(creds)

# Set up sheets
sheets = client.open("Scarlet Pigs OP Schedule").worksheets()
sheet1 = sheets[0]
archive_sheet = sheets[1]
entire_sheet = sheet1.get_all_values()

# Get cell entry
def get_cell_entry(row: int, column: int):
    return entire_sheet[row-1][column-1]

# Set cell entry
def set_cell_entry(row: int, column: int, value: str):
    entire_sheet[row-1][column-1] = value

# Settings entered on the sheet
date_amount = int (get_cell_entry(2, 7))
schedule_message_info = get_cell_entry(3, 7)
modlist_message_info = get_cell_entry(4, 7)
        
# Update local sheet
def update_local_sheet():
    global entire_sheet
    global date_amount
    global schedule_message_info
    global modlist_message_info
    entire_sheet = sheet1.get_all_values()
    date_amount = int (get_cell_entry(2, 7))
    schedule_message_info = get_cell_entry(3, 7)
    modlist_message_info = get_cell_entry(4, 7)
    
# Update online sheet
def update_online_sheet():
    sheet1.update(entire_sheet)

# Get schedule messages
def get_schedule_messages():
    if schedule_message_info == "" or schedule_message_info == None: 
        return { "servers": []}
    else:
        return json.loads(schedule_message_info)
    
# Save schedule message
def set_schedule_message_id(guild_id: int, channel_id: int, message_id: int):
    serverdata = get_schedule_messages()
    guild_ids = [server["guild_id"] for server in serverdata["servers"]]
    
    if (guild_id in guild_ids):
        index = guild_ids.index(guild_id)
        serverdata["servers"][index]["channel_id"] = channel_id
        serverdata["servers"][index]["message_id"] = message_id
    else:
        serverdata["servers"].append({"guild_id": guild_id, "channel_id": channel_id, "message_id": message_id})
    
    set_cell_entry(3, 7, json.dumps(serverdata))
    update_online_sheet()
    
# Remove a schedule message
def remove_schedule_message(id: int):
    serverdata = get_schedule_messages()
    guild_ids = [server["guild_id"] for server in serverdata["servers"]]
    channel_ids = [server["channel_id"] for server in serverdata["servers"]]
    message_ids = [server["message_id"] for server in serverdata["servers"]]
    
    if (id in guild_ids):
        index = guild_ids.index(id)
    elif (id in channel_ids):
        index = channel_ids.index(id)
    elif (id in message_ids):
        index = message_ids.index(id)
    else:
        return
    
    serverdata["servers"].pop(index)
        
    set_cell_entry(3, 7, json.dumps(serverdata))
    update_online_sheet()
    
# Get modlist messages
def get_modlist_messages():
    if modlist_message_info == "" or modlist_message_info == None: 
        return { "servers": []}
    else:
        return json.loads(modlist_message_info)
    
# Save modlist message
def add_modlist_message(guild_id: int, channel_id: int, message_id: int, file_path: str):
    serverdata = get_modlist_messages()
    serverdata["servers"].append({"guild_id": guild_id, "channel_id": channel_id, "message_id": message_id, "file_path": file_path})
    
    set_cell_entry(4, 7, json.dumps(serverdata))
    update_online_sheet()
    
# Remove a modlist message
def remove_modlist_message(id: int):
    serverdata = get_modlist_messages()
    guild_ids = [server["guild_id"] for server in serverdata["servers"]]
    channel_ids = [server["channel_id"] for server in serverdata["servers"]]
    message_ids = [server["message_id"] for server in serverdata["servers"]]
    
    if (id in guild_ids):
        index = guild_ids.index(id)
    elif (id in channel_ids):
        index = channel_ids.index(id)
    elif (id in message_ids):
        index = message_ids.index(id)
    else:
        return
    
    serverdata["servers"].pop(index)
    
    set_cell_entry(4, 7, json.dumps(serverdata))
    update_online_sheet()

# Get the date of the next sunday
def get_next_sunday():
    today = datetime.date.today()
    next_sunday = today + datetime.timedelta(days= (6 - today.weekday()))
    return next_sunday

# Get a list over the next n amount of Sundays
def get_next_n_sundays(n = 5):
    next_sunday = get_next_sunday()
    next_n_sundays = []
    for i in range(n):
        sunday_after = next_sunday + datetime.timedelta(days=i*7)
        next_n_sundays.append(sunday_after.strftime("%b %d (%y)"))
    return next_n_sundays    

# Return schedule dates
def get_schedule_dates():
    update_local_sheet()
    dates = [row[0] for row in entire_sheet]
    names = [row[1] for row in entire_sheet]
    authors = [row[2] for row in entire_sheet]
    old_ops = [dates, names, authors]
    next_sundays = get_next_n_sundays(date_amount)
    ops = []
    
    # Go through all the ops that have taken place and add them to the archive sheet
    previous_sundays = [date for date in old_ops[0] if date not in next_sundays]
    for old_sunday in previous_sundays:
        if (old_sunday != "Date"):
            index = old_ops[0].index(old_sunday)
            old_name = old_ops[1][index]
            old_author = old_ops[2][index]
            archive_sheet.append_row(values=[old_sunday, old_name, old_author])
    
    # Go through all the ops that are coming up and add them to the schedule (And make sure they're ordered correctly)
    for i in range(1, 11):
        name = ''
        author = ''
        if(next_sundays[i-1] in old_ops[0]):
            index = old_ops[0].index(next_sundays[i-1])
            if index >= 0 and index < len(old_ops[1]):
                name = old_ops[1][index]
            if index >= 0 and index < len(old_ops[2]):
                author = old_ops[2][index]
        ops.append([next_sundays[i-1], name, author])
    
    # Update the online sheet with the new schedule
    for i in range(0,10):
        set_cell_entry(i+2, 1, ops[i][0])
        set_cell_entry(i+2, 2, ops[i][1])
        set_cell_entry(i+2, 3, ops[i][2])
        
    update_online_sheet()
    
    # Return the new schedule in a format that is more easily usable
    dates = []
    names = []
    authors = []
    for i in range(0, len(ops)):
        
        dates.append(ops[i][0])
        names.append(ops[i][1])
        authors.append(ops[i][2])

    return [dates, names, authors]
        
# Updates an op entry in the schedule
# Use
#   update_op_entry("Nov 06 (22)", opname = "OP Name") to update only opname
# or
#   update_op_entry("Nov 06 (22)", opauthor = "OP Author") to update only author
def update_op(datex, opname = None, opauthor = None):
    entries = sheet1.col_values(1)
    for i in range(2, len(entries)):
        if entries[i] == datex:
            if opname != None:
                set_cell_entry(i+1, 2, opname)
            if opauthor != None:
                set_cell_entry(i+1, 3, opauthor)
    update_online_sheet()
    return None

# Get data on specific op
def get_op_data(date = None, op = None, author = None):
    dateinfo = [row[0] for row in zip(*entire_sheet)]
    opinfo = [row[1] for row in zip(*entire_sheet)]
    authorinfo = [row[2] for row in zip(*entire_sheet)]

    if(date != None):
        for i in range(1, len(dateinfo)):
            if dateinfo[i] == date:
                return [dateinfo[i], opinfo[i], authorinfo[i]]
    elif(op != None):
        for i in range(1, len(opinfo)):
            if opinfo[i] == op:
                return [dateinfo[i], opinfo[i], authorinfo[i]]
    elif(author != None):
        for i in range(1, len(authorinfo)):
            if authorinfo[i] == author:
                return [dateinfo[i], opinfo[i], authorinfo[i]]
    else:
        return None

# Returns a list of all op entries in the sheet
def get_full_schedule():
    full_schedule = get_schedule_dates()
    entries = []
    entries = list(zip(*full_schedule))
    # for i in range(0, len(full_schedule)):
    #     entries.append([full_schedule[0][i], full_schedule[1][i], full_schedule[2][i]])
    return entries

# Get the dates without an op
def get_free_dates():
    full_schedule = get_full_schedule()
    free_dates = []
    for entry in full_schedule:
        if entry[1] == "" or entry[1] == None:
            free_dates.append([entry[0], entry[1], entry[2]])
    return free_dates

# Get the dates with an op
def get_booked_dates():
    full_schedule = get_full_schedule()
    booked_dates = []
    for entry in full_schedule:
        if entry[1] != "" and entry[1] != None:
            booked_dates.append([entry[0], entry[1], entry[2]])
    return booked_dates

print("Sheets updated and setup")