#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Andrey Derevyagin'
__copyright__ = 'Copyright © 2015'

import websocket
import logging
import urllib, urllib2
import time
import json
import threading, Queue
import six

from sio_message import SIOMessage
from parse_messages_thread import ParseMessagesThread
from send_message_thread import SendMessageThread


class SocketIO_cli(object):
	"""docstring for SocketIO_cli"""
	def __init__(self, url=None, cookiejar=None, callbacks={}, on_connect=None, autoreconnect=True):
		super(SocketIO_cli, self).__init__()
		self._url = url
		self.cj = cookiejar
		self.info = None
		self.callbacks = callbacks
		self.on_connect = on_connect
		self.autoreconnect = autoreconnect
		self.stopping = False
		self.connecting = False
		self.reconnect_interval = 10

		self.opener = urllib2.build_opener(
				urllib2.HTTPRedirectHandler(),
				urllib2.HTTPHandler(debuglevel=0),
				urllib2.HTTPSHandler(debuglevel=0),
				urllib2.HTTPCookieProcessor(self.cj)
			)

		self.raw_messages_queue = Queue.Queue()
		self.parse_messages_thread = ParseMessagesThread(self.raw_messages_queue, self)
		self.parse_messages_thread.start()
		self.socket_thread = None

		self.send_messages_queue = Queue.Queue()
		self.send_message_thread = None

		self._emit_callbacks = {}
		self._emit_callback_id = 0

		if self._url:
			self.connect()

	def connect(self):
		self.connecting = True
		if not self._url:
			#raise
			return 
		sio_url = self._url+'/socket.io/'
		polling_c = 0
		prms = {
			'EIO': '3',
			'transport': 'polling',
		}
		self.info = None
		while True:
			prms['t'] = '%d-%d'%(int(time.time()*1000), polling_c)
			if self.info:
				prms['sid'] = self.info.get('sid')
			data = urllib.urlencode(prms)
			url = '%s?%s'%(sio_url, data)
			logging.debug(url)
			try:
				response = self.opener.open(url)
			except Exception, e:
				return 
			polling_c += 1
			data = response.read()

			packets = self.parse_polling_packet(data)
			for p in packets:
				logging.debug('receive packet: %s %d', p, p.parsed)
			if self.info:
				break
			for p in packets:
				if p.engine_io == 0:
					self.info = p.message
			break
		self.start()

	def run(self):
		sio_url = self._url+'/socket.io/'
		if 'http' == sio_url[:len('http')]:
			sio_url = 'ws' + sio_url[len('http'):]
		prms = {
			'EIO': '3',
			'transport': 'websocket',
			'sid': self.info.get('sid')
		}
		data = urllib.urlencode(prms)
		url = '%s?%s'%(sio_url, data)
		headers = []
		if self.cj:
			cookies = ';'.join(map(lambda c: '%s=%s'%(c.name, c.value), self.cj))
			headers.append('Cookie: %s'%cookies)
		logging.debug(url)
		self.ws = websocket.WebSocketApp(url,
						on_message = lambda ws, msg: self.on_message(ws, msg),
						on_error = lambda ws, err: self.on_error(ws,err),
						on_close = lambda ws: self.on_close(ws),
						header = headers)
		self.ws.on_open = lambda ws: self.on_open(ws)

		self.send_message(SIOMessage(2, message='probe'))
		self.send_message(SIOMessage(5, message=''))

		self.connecting = False

		#self.ws.run_forever(ping_interval=self.info.get('pingInterval', 0)/1000.0, ping_timeout=self.info.get('pingTimeout', 0)/1000.0)
		self.ws.run_forever()
		self.ws = None
		logging.debug('run ends')

		if not self.stopping and self.autoreconnect:
			self.reconnect()

	def start(self):
		self.stopping = False
		def run(*args):
			self.run()
		self.socket_thread = threading.Thread(target=run)
		self.socket_thread.setDaemon(True)
		self.socket_thread.start()

	def stop(self):
		self.stopping = True
		if self.ws is not None:
			self.ws.close()
		if self.socket_thread is not None:
			self.socket_thread.join()
			self.socket_thread = None

	def reconnect(self):
		while True:
			if self.connecting:
				time.sleep(self.reconnect_interval)
			if self.send_message_thread:
				self.send_message_thread.stop()
				self.send_message_thread.join()
				self.send_message_thread = None
			logging.info('reconnecting...')
			self.connect()
			if not self.connecting:
				break

	def on_open(self, ws):
		#self.ws = ws
		logging.info('open socket')
		ping_interval = self.info.get('pingInterval', 30000)/1000 if self.info else 30
		self.send_message_thread = SendMessageThread(self.send_messages_queue, self, ping_interval)
		self.send_message_thread.start()

	def on_message(self, ws, message):
		p = self.socket_io_message(message)
		logging.debug('receive packet: %s', p)

	def on_error(self, ws, error):
		logging.error("ERROR: {0}".format(error))

	def on_close(self, ws):
		logging.info('close socket')
		if self.send_message_thread:
			self.send_message_thread.stop()
			self.send_message_thread.join()
			self.send_message_thread = None

	def parse_polling_packet(self, data):
		rv = []
		if len(data)==0:
			return rv
		i = 0 
		while i < len(data):
			if data[i] == '\x00':
				i += 1
				l = 0
				while data[i] != '\xFF':
					l = l * 10 + ord(data[i])
					i += 1
				i += 1

				rv.append(self.socket_io_message(data[i:i+l], parse_directly=True))
				i += l
			else:
				break
		return rv

	def socket_io_message(self, data, parse_directly=False):
		rv = SIOMessage()
		rv.engine_io = ord(data[0]) - ord('0')
		if rv.engine_io in [0,2,3]:
			#rv.socket_io = 0
			i = 1
		else:
			rv.socket_io = ord(data[1]) - ord('0')
			i = 2
			if rv.engine_io==4 and rv.socket_io==3:
				rv.socket_io_add = 0
				while i < len(data) and data[i] in '1234567890':
					rv.socket_io_add = rv.socket_io_add * 10 + ord(data[i]) - ord('0')
					i+=1
		rv.message = data[i:]
		if parse_directly:
			rv.parse()
		else:
			self.raw_messages_queue.put(rv)
		return rv

	def message_worker(self, msg):
		msg.parse()
		if msg.engine_io == 4:
			if msg.socket_io in [2,3]:
				if msg.socket_io_add is not None and self._emit_callbacks.has_key(msg.socket_io_add):
					self._emit_callbacks[msg.socket_io_add](self, msg.message, msg)
					self._emit_callbacks.pop(msg.socket_io_add, None)
				elif isinstance(msg.message, list) and isinstance(msg.message[0], six.string_types):
					cid = msg.message[0]
					if self.callbacks.has_key(cid):
						if isinstance(self.callbacks[cid], list):
							for c in self.callbacks[cid]:
								if len(msg.message) > 1:
									c(self, msg.message[1], msg)
								else:
									c(self, None, msg)
						else:
							if len(msg.message) > 1:
								self.callbacks[cid](self, msg.message[1], msg)
							else:
								self.callbacks[cid](self, None, msg)
			elif msg.socket_io == 0:
				if self.on_connect:
					self.on_connect(self)

	def send_message(self, msg):
		self.send_messages_queue.put(msg)
		#self.ws.send(str(msg))

	def on(self, callback_id, callback):
		if self.callbacks.has_key(callback_id):
			if isinstance(self.callbacks[callback_id], list):
				self.callbacks[callback_id].append(callback)
			else:
				self.callbacks[callback_id] = [self.callbacks[callback_id], callback]
		else:
			self.callbacks[callback_id] = [callback, ]

	def emit(self, data, callback=None):
		if callback:
			msg = SIOMessage(4, 2, data, parsed=True, socket_io_add=self._emit_callback_id)
			self._emit_callbacks[self._emit_callback_id] = callback
			self._emit_callback_id += 1
		else:
			msg = SIOMessage(4, 2, data, parsed=True)
		self.send_message(msg)



def cb(io, data, *ex_prms):
	if data.get('event') == 'messageReceived':
		txt = urllib.unquote(data.get('text', ''))
		txt = txt[::-1]
		txt = urllib.quote(txt)
		#io.send_message(SIOMessage(4,2,'["message","%s"]'%data.get('text', '')[::-1]))
		io.emit( ('message', txt ) )
	elif data.get('event') == 'userJoined':
		io.emit( ('message', 'Hello %s'%data.get('name') ) )

def connected(io):
	#io.send_message(SIOMessage(4,2,'["message","String"]'))
	io.emit( ('1', ) )


def main():
	logging.basicConfig(level=logging.DEBUG,
					format='%(asctime)s.%(msecs)03d %(levelname)-5s %(threadName)-10s: %(message)s', datefmt="%H:%M:%S")

	io = SocketIO_cli('http://192.168.1.50:8080', on_connect=connected)
	io.on('message', cb)
	#io = SocketIO_cli('https://ws.tradernet.ru')
	
	while True:
		time.sleep(1)
		#time.sleep(6)
		#break
	io.stop()

if __name__=='__main__':
	main()

