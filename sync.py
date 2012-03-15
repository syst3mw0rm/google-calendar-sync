#!/usr/bin/python

from gcal import GoogleCalendar
from ical import iCalCalendar
import ConfigParser,  sys
import gdata.calendar

config_file = 'config.json'

if __name__ == '__main__':
### Parse configuration file  ###
    config = ConfigParser.ConfigParser()
    # Get mandatory parameters
    try:
        config.read(config_file)
        g_username = config.get('google',  'username')
        g_password = config.get('google',  'password')
        ical_path = config.get('ical',  'path')
    except Exception,  e:
        print 'ERROR: not a valid configuration file, check',  config_file
        print type(e),  e.args,  e
        sys.exit(1)

### Initialization ###
    gcalendar = GoogleCalendar()
    icalendar = iCalCalendar(ical_path)
    
    # Login into Google Calendar
    gcalendar._ClientLogin(g_username,  g_password)

    # Gcal name which has to be synchronized with the ical
    ical_name = icalendar.calName()
    gcal_name = ical_name + '-sync'
 
    all_calendars = gcalendar.cal_client.GetAllCalendarsFeed()

    # Google calendar object that has to be synced with icalendar
    gcal_sync = None

    for a_calendar in all_calendars.entry:
	if a_calendar.title.text == gcal_name:
		print 'Found the calendar'	
		gcal_sync = a_calendar
		break

    if gcal_sync is None:
	gcal_sync = gcalendar._InsertCalendar(gcal_name,'This calendar contains practice and game times', 'America/Los_Angeles', hidden=False, location='Oakland', color='#2952A3')

#    gcal_href = gcal_sync.GetEditLink()
    gcal_href = gcal_sync.content.src

    # insert all elements of icalendar into the gcal_sync
    for event in icalendar.elements():
        e = gdata.calendar.data.CalendarEventEntry()
        icalendar.ical2gcal(e, event)
	new_event = gcalendar.cal_client.InsertEvent(e, insert_uri=gcal_href)
