#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Andrey Derevyagin'
__copyright__ = 'Copyright © 2015'

import threading, Queue
from sio_message import SIOMessage

class ParseMessagesThread(threading.Thread):
	def __init__(self, raw_messages_queue, socketio_cli):
		threading.Thread.__init__(self)
		self.setDaemon(True)
		self.raw_messages_queue = raw_messages_queue
		self.socketio_cli = socketio_cli

	def run(self):
		while True:
			msg = self.raw_messages_queue.get(block=True)
			self.socketio_cli.message_worker(msg)
			#self.parsed_messages_queue.put(msg)