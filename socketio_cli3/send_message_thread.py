#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Andrey Derevyagin'
__copyright__ = 'Copyright © 2015'

import threading, Queue
import logging
import time
from sio_message import SIOMessage

class SendMessageThread(threading.Thread):
	def __init__(self, send_messages_queue, socketio_cli, ping_interval=None):
		threading.Thread.__init__(self)
		self.setDaemon(True)
		self.send_messages_queue = send_messages_queue
		self.socketio_cli = socketio_cli
		self.ping_interval = ping_interval

	def run(self):
		ping_tm = time.time()
		ping_msg = SIOMessage(2)
		self._running = True
		while True:
			if not self._running:
				break
			if self.ping_interval:
				tm = time.time()
				if tm - ping_tm > self.ping_interval:
					logging.debug('ping message')
					self.socketio_cli.ws.send(str(ping_msg))
					ping_tm = tm
			try:
				msg = self.send_messages_queue.get(block=True, timeout=1)
			except Queue.Empty, e:
				msg = None
			if msg:
				logging.debug('send message: %s', str(msg))
				self.socketio_cli.ws.send(str(msg))

	def stop(self):
		self._running = False
