#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Andrey Derevyagin'
__copyright__ = 'Copyright © 2015'

import time
import json
import six

class SIOMessage(object):
	def __init__(self, engine_io=None, socket_io=None, message=None, parsed=False, socket_io_add=None):
		super(SIOMessage, self).__init__()
		self.socket_io = socket_io
		self.socket_io_add = socket_io_add
		self.engine_io = engine_io
		self.message = message
		self.parsed = parsed
		self.tm = time.time()

	def __str__(self):
		rv = str(self.engine_io)
		if self.socket_io is not None:
			rv += str(self.socket_io)
		if self.socket_io_add is not None:
			rv += str(self.socket_io_add)
		if self.message is not None:
			if self.parsed:
				if isinstance(self.message, six.string_types) or isinstance(self.message, (int, long, float, complex)):
					rv += json.dumps( (self.message, ) )
				else:
					rv += json.dumps(self.message)
			else:
				rv += self.message
		return rv

	def parse(self):
		if self.parsed is False:
			try:
				self.message = json.loads(self.message)
			except ValueError, e:
				pass
			self.parsed = True
