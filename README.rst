=================
SocketIO_cli3
=================

This package implements Socket.IO client protocol for Python.


License
============

 - LGPL


Usage:
============

    from socketio_cli3 import SocketIO_cli

    def message(io, data, *ex_prms):
        print data

    def connected(io):
        io.emit( ['message', 'String'] )

    io = SocketIO_cli('http://localhost:8080', on_connect=connected)
    io.on('message', message)

    while True:
        time.sleep(1)    
