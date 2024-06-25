import requests
import os
import datetime

# Define the URL
API_URL = os.getenv('SCARLETPIGS_API')


def get_events():
    # Make the request
    response = requests.get(API_URL + '/events')
    # Return the JSON response
    return response.json()


def create_event(name: str, description: str, author: int, starttime: datetime.datetime, endtime: datetime.datetime):
    # Make the request
    event = {
        'name': name,
        'description': description,
        'createdByUserId': -1,
        'eventTypeId': -1,
        'startTime': starttime.isoformat(),
        'endTime': endtime.isoformat()
    }
    response = requests.post(API_URL + '/events', json=event)
    print(response.text)
    # Return the JSON response
    return response.json()
