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

