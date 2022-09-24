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
sheet2 = sheets[1]

# Settings entered on the sheet
date_amount_cell = sheet1.cell(2, 7)
schedule_message_info_cell = sheet1.cell(3, 7)
        

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

def get_schedule_messages():
    if os.path.isfile("schedule_messages.json"):
        with open("schedule_messages.json", "r") as f:
            messages = json.load(f)
            
        return messages
    else:
        return { 'servers': []}
    
# Save schedule message
# TODO: Make local file using JSON to support multiple servers
def set_schedule_message_id(guild_id: int, channel_id: int, message_id: int):
    serverdata = get_schedule_messages()
    guild_ids = [server['guild_id'] for server in serverdata['servers']]
    
    if (guild_id in guild_ids):
        index = guild_ids.index(guild_id)
        serverdata['servers'][index]['channel_id'] = channel_id
        serverdata['servers'][index]['message_id'] = message_id
    else:
        serverdata['servers'].append({'guild_id': guild_id, 'channel_id': channel_id, 'message_id': message_id})
        
    with open("schedule_messages.json", "w") as f:
        json.dump(serverdata, f)

# Return schedule dates
def get_schedule_dates():
    next_sundays = get_next_n_sundays(int(date_amount_cell.value)+4)
    dates = sheet1.col_values(1)
    names = sheet1.col_values(2)
    authors = sheet1.col_values(3)
    old_ops = [dates, names, authors]
    
    next_sundays = get_next_n_sundays(int(date_amount_cell.value))
    ops = []
    
    previous_sundays = [x for x in old_ops[0] if x not in next_sundays]
    for old_sunday in previous_sundays:
        if (old_sunday != "Date"):
            index = old_ops[0].index(old_sunday)
            old_name = old_ops[1][index]
            old_author = old_ops[2][index]
            sheet2.append_row(values=[old_sunday, old_name, old_author])
        
    
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
    
    
    for i in range(0,10):
        sheet_range = 'A' + str(i+2) + ':C' + str(i+2)
        sheet1.batch_update([{'range' : sheet_range, 'values' : [ops[i]]}])
        
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
                sheet1.update_cell(i+1, 2, opname)
            if opauthor != None:
                sheet1.update_cell(i+1, 3, opauthor)
    return None

# Get data on specific op
def get_op_data(date = None, op = None, author = None):
    dateinfo = sheet1.col_values(1)
    opinfo = sheet1.col_values(2)
    authorinfo = sheet1.col_values(3)

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
    dates = []
    for i in range(0, len(full_schedule[0])):
        dates.append([full_schedule[0][i], full_schedule[1][i], full_schedule[2][i]])
    return dates

# Get the dates without an op
def get_free_dates():
    full_schedule = get_full_schedule()
    free_dates = []
    for i in range(0, len(full_schedule)):
        if full_schedule[i][1] == "" or full_schedule[i][1] == None:
            free_dates.append([full_schedule[i][0], full_schedule[i][1], full_schedule[i][2]])
    return free_dates

# Get the dates with an op
def get_booked_dates():
    full_schedule = get_full_schedule()
    booked_dates = []
    for i in range(0, len(full_schedule)):
        if full_schedule[i][1] != "" and full_schedule[i][1] != None:
            booked_dates.append([full_schedule[i][0], full_schedule[i][1], full_schedule[i][2]])
    return booked_dates





get_schedule_dates()
print("Sheets updated and setup")