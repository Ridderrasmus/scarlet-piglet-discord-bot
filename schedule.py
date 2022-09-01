import gspread
import datetime
from oauth2client.service_account import ServiceAccountCredentials

scope = ['https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scope)

client = gspread.authorize(creds)

sheets = client.open("Scarlet Pigs OP Schedule").worksheets()

sheet1 = sheets[0]
sheet2 = sheets[1]

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

def set_schedule_message_id(message_id):
    if message_id != None:
        sheet1.update_cell(schedule_message_info_cell.row, schedule_message_info_cell.col, str(message_id))
    else:
        sheet1.update(schedule_message_info_cell.row, schedule_message_info_cell.col, [])
    return None

def get_schedule_message_id():
    msg_id = schedule_message_info_cell.value
    if (msg_id != None and msg_id != "[]" and msg_id != ""):
        msg_id = msg_id.strip("[]")
        msg_id = msg_id.split(",")
        msg_id = [msg_id[0], msg_id[1]]
        return msg_id
    else:
        return []

def check_schedule_dates():
    next_sundays = get_next_n_sundays(int(date_amount_cell.value)+4)
    dates = sheet1.col_values(1)
    ops = sheet1.col_values(2)
    authors = sheet1.col_values(3)
    for i in range(0, int(date_amount_cell.value)+1):
        if len(dates) < (int(date_amount_cell.value)+1):
            dates.append("")
        if len(ops) < (int(date_amount_cell.value)+1):
            ops.append("")
        if len(authors) < (int(date_amount_cell.value)+1):
            authors.append("")
            
    
    
    if next_sundays[0] in [dates[2], dates[3], dates[4], dates[5], dates[6], dates[7], dates[8], dates[9]]:
        sheet2.insert_row([dates[1], ops[1], authors[1]], 2)
        
        
        for i in range(1, int(date_amount_cell.value)+1):
            if i == int(date_amount_cell.value) or dates[i] == None or dates[i] == "":
                sheet1.update_cell(i+1, 1, next_sundays[i-1])
                print("INFO: Date just updated.")
            else:
                sheet1.update_cell(i+1, 1, dates[i+1])
                sheet1.update_cell(i+1, 2, ops[i+1])
                sheet1.update_cell(i+1, 3, authors[i+1])
                print("INFO: Date just got moved.")
    
    elif len(dates) != int(date_amount_cell.value)+1:
        for i in range(1, int(date_amount_cell.value)+1):
            if dates[i] == None or dates[i] == "":
                sheet1.update_cell(i+1, 1, next_sundays[i-1])
                print("INFO: Date just updated.")
    
    else:
        for i in range(1, int(date_amount_cell.value)+1):
            if dates[i] == None or dates[i] == "":
                sheet1.update_cell(i+1, 1, next_sundays[i-1])
                print("INFO: Date just updated.")
    

    return [dates, ops, authors]
        
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
    full_schedule = check_schedule_dates()
    dates = []
    for i in range(1, len(full_schedule[0])):
        dates.append([full_schedule[0][i], full_schedule[1][i], full_schedule[2][i]])
    return dates

# Get the dates without an op
def get_free_dates():
    full_schedule = get_full_schedule()
    print(full_schedule)
    free_dates = []
    for i in range(0, len(full_schedule)):
        if full_schedule[i][1] == "" or full_schedule[i][1] == None:
            free_dates.append([full_schedule[i][0], full_schedule[i][1], full_schedule[i][2]])
    print(free_dates)
    return free_dates

# Get the dates with an op
def get_booked_dates():
    full_schedule = get_full_schedule()
    booked_dates = []
    for i in range(0, len(full_schedule)):
        if full_schedule[i][1] != "" and full_schedule[i][1] != None:
            booked_dates.append([full_schedule[i][0], full_schedule[i][1], full_schedule[i][2]])
    return booked_dates




check_schedule_dates()
print("Sheets updated and setup")