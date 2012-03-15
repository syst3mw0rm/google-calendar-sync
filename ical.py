#!/usr/bin/env python

import sys, os, re, getopt, string, time, shutil
import vobject, httplib2, ConfigParser, md5

try:
	from xml.etree import ElementTree
except ImportError:
	from elementtree import ElementTree
import gdata.calendar.service
import gdata.service
import atom.service
import gdata.calendar
import atom


class iCalCalendar:
	def __init__(self, url):
		self.url = url
		m = re.match('^http', self.url)
		try:
			if m:
				# Remote calendar.
				h = httplib2.Http()
				resp, content = h.request(self.url, "GET")
				assert(resp['status'] == '200')
			else:
				# Local calendar.
				stream = file(self.url)
				content = stream.read()
				stream.close()
			self.cal = vobject.readOne(content, findBegin='false')
		except:
			# Create an empty calendar object.
			self.cal = vobject.iCalendar()

	# Properly encode unicode characters.
        def encode_element(self, el):
                return unicode(el).encode('ascii', 'replace')

        # Use the Google-compliant datetime format for single events.
        def format_datetime(self, date):
                try:
                        if re.match(r'^\d{4}-\d{2}-\d{2}$', str(date)):
                                return str(date)
                        else:
                                return str(time.strftime("%Y-%m-%dT%H:%M:%S.000Z", date.utctimetuple()))
                except Exception, e:
                        print type(e), e.args, e
                        return str(date)

        # Use the Google-compliant datetime format for recurring events.
        def format_datetime_recurring(self, date):
                try:
                        if re.match(r'^\d{4}-\d{2}-\d{2}$', str(date)):
                                return str(date).replace('-', '')
                        else:
                                return str(time.strftime("%Y%m%dT%H%M%SZ", date.utctimetuple()))
                except Exception, e:
                        print type(e), e.args, e
                        return str(date)

	# Return the calendar Name
	def calName(self):
		# Returning only the first x-wr-calname property
		return self.cal.contents['x-wr-calname'][0].value

	# Return the list of events in the iCal Calendar.
	def elements(self):
		ret = []
		for event in self.cal.components():
			if (event.name == 'VEVENT') and hasattr(event, 'summary') and hasattr(event, 'uid'):
				ret.append(event)
		return ret

	# Retrieve an event from Google Calendar by local UID.
	def get_event_by_uid(self, uid):
		for e in self.elements():
			if e.uid.value == uid:
				return e
		return None

	# Insert a new iCal event.
	def insert(self, event):
		self.cal.add(event)
		print 'New event inserted (%s): %s' % (self.url, event.uid.value)
		return event

	# Update a Google Calendar event.
	def update(self, event):
		e = self.get_event_by_uid(event.uid.value)
		if e is None:
			print >> sys.stderr, 'WARNING: event %s not found in %s!' % (event.uid.value, self.url)
			return
		e.copy(event)
		print 'Updated event (%s): %s' % (self.url, e.uid.value,)
		return event

	# Delete a iCal Calendar event.
	def delete(self, event):
		e = self.get_event_by_uid(event.uid.value)
		self.cal.remove(e)
		print 'Deleted event (%s): %s' % (self.url, e.uid.value,)

	# List all the iCal events.
	def list(self):
		for event in self.elements():
			print event.summary.value, '-->', event.uid.value

	# Commit changes to iCal Calendar.
	def sync(self):
		print 'Synchronized ', self.url
		m = re.match('^http', self.url)
		if m:
			print >> sys.stderr, 'ERROR: couldn\'t sync a remote calendar directly: ', self.url
			sys.exit(1)
		try:
			f = open(self.url, 'w')
			f.write(unicode(self.cal.serialize()).encode('ascii', 'replace'))
			f.close()
		except Exception, e:
			print >> sys.stderr, 'ERROR: couldn\'t write to local calendar: ', self.url
			print type(e), e.args, e
			sys.exit(1)

	def ical2gcal(self, e, dt):
		# Parse iCal event.
		event = {}
		event['uid'] = self.encode_element(dt.uid.value)
		event['subject'] = self.encode_element(dt.summary.value)
		if hasattr(dt, 'description') and (dt.description is not None):
			event['description'] = self.encode_element(dt.description.value)
		else:
			event['description'] = ''
		if hasattr(dt, 'location'):
			event['where'] = self.encode_element(dt.location.value)
		else:
			event['where'] = ''
		if hasattr(dt, 'status'):
			event['status'] = self.encode_element(dt.status.value)
		else:
			event['status'] = 'CONFIRMED'
		if hasattr(dt, 'organizer'):
			event['organizer'] = self.encode_element(dt.organizer.params['CN'][0])
			event['mailto'] = self.encode_element(dt.organizer.value)
			event['mailto'] = re.search('(?<=MAILTO:).+', event['mailto']).group(0)
		if hasattr(dt, 'rrule'):
			event['rrule'] = self.encode_element(dt.rrule.value)
		if hasattr(dt, 'dtstart'):
			event['start'] = dt.dtstart.value
		if hasattr(dt, 'dtend'):
			event['end'] = dt.dtend.value
		if hasattr(dt, 'valarm'):
			event['alarm'] = self.format_alarm(self.encode_element(dt.valarm.trigger.value))

		# Convert into a Google Calendar event.
		try:
			e.title = atom.Title(text=event['subject'])
			e.extended_property.append(gdata.calendar.ExtendedProperty(name='local_uid', value=event['uid']))
			e.content = atom.Content(text=event['description'])
			e.where.append(gdata.calendar.Where(value_string=event['where']))
			e.event_status = gdata.calendar.EventStatus()
			e.event_status.value = event['status']
			if event.has_key('organizer'):
				attendee = gdata.calendar.Who()
				attendee.rel = 'ORGANIZER'
				attendee.name = event['organizer']
				attendee.email = event['mailto']
				attendee.attendee_status = gdata.calendar.AttendeeStatus()
				attendee.attendee_status.value = 'ACCEPTED'
				if len(e.who) > 0:
					e.who[0] = attendee
				else:
					e.who.append(attendee)
			# TODO: handle list of attendees.
			if event.has_key('rrule'):
				# Recurring event.
				recurrence_data = ('DTSTART;VALUE=DATE:%s\r\n'
					+ 'DTEND;VALUE=DATE:%s\r\n'
					+ 'RRULE:%s\r\n') % ( \
					self.format_datetime_recurring(event['start']), \
					self.format_datetime_recurring(event['end']), \
					event['rrule'])
				e.recurrence = gdata.calendar.Recurrence(text=recurrence_data)
			else:
				# Single-occurrence event.
				if len(e.when) > 0:
					e.when[0] = gdata.calendar.When(start_time=self.format_datetime(event['start']), \
									end_time=self.format_datetime(event['end']))
				else:
					e.when.append(gdata.calendar.When(start_time=self.format_datetime(event['start']), \
									  end_time=self.format_datetime(event['end'])))
				if event.has_key('alarm'):
					# Set reminder.
					for a_when in e.when:
						if len(a_when.reminder) > 0:
							a_when.reminder[0].minutes = event['alarm']
						else:
							a_when.reminder.append(gdata.calendar.Reminder(minutes=event['alarm']))
		except Exception, e:
			print >> sys.stderr, 'ERROR: couldn\'t create gdata event object: ', event['subject']
			print type(e), e.args, e
			sys.exit(1)


