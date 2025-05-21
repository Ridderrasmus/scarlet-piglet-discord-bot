import requests
import os
import datetime
import json

# Define the URL
API_URL: str = os.getenv('SCARLETPIGS_API') or 'None'


def get_events():
    # Make the request
    response = requests.get(API_URL + '/events', timeout=20)
    list_of_events = json.loads(response.text)
    # Return the JSON response
    return list_of_events


def get_event_at_date(datetime: datetime.datetime):
    response = requests.get(API_URL + '/events', timeout=20)
    list_of_events = json.loads(response.text)
    for event in list_of_events:
        if (datetime.fromisoformat(event['startTime']) <= datetime and datetime.fromisoformat(event['endTime']) >= datetime):
            return event
    return None


def create_event(name: str, description: str, author: str, authorid: int, starttime: datetime.datetime, endtime: datetime.datetime):
    # Shorten description if it's too long
    if len(description) > 150:
        description = description[:147] + "..."
    # Make the request
    event = {
        "name": name,
        "CreatorDiscordUsername": f"{authorid}",
        "author": author,
        "Description": description,
        "startTime": starttime.isoformat(),
        "endTime": endtime.isoformat()
    }
    response = requests.post(API_URL + '/events', json=event, timeout=20)
    print(response.status_code)
    # Return the JSON response
    return response.json()


def get_event(event_id: int):
    # Make the request
    response = requests.get(API_URL + '/events/' + str(event_id), timeout=20)
    # Return the JSON response
    return response.json()


# def edit_event(id: int, name: str | None, description: str | None, starttime: datetime.datetime | None, endtime: datetime.datetime | None):
#     edited_event = {
#         "id": id,
#         "name": name,
#         "description": description,
#         "startTime": starttime.isoformat() if starttime else None,
#         "endTime": endtime.isoformat() if endtime else None
#     }
#     response = requests.put(API_URL + '/Events/', json=edited_event)


def edit_event(edited_event: dict):
    response = requests.put(API_URL + '/events/',
                            json=edited_event, timeout=20)


def delete_event(event_id: int):
    # Make the request
    response = requests.delete(
        API_URL + '/events/' + str(event_id), timeout=20)
    # Return the JSON response
    return response.ok
