#!/usr/bin/python

import time
import BaseHTTPServer
from SocketServer import ThreadingMixIn
import socket
import json
import os
import sys
from pprint import pprint
from urlparse import urlparse, parse_qs

HOST_NAME = ''
PORT_NUMBER = 5000

class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_HEAD(s):
        s.send_response(200)
        s.send_header("Content-type", "text/html")
        s.end_headers()

    def do_POST(s):
        if s.path == '/send':
            msg = s.rfile.read(int(s.headers['Content-Length']))

            outp  = msg + '\r\n'
            sys.stdout.write(outp)
            sys.stdout.flush()

            s.send_response(200)
            s.end_headers()
            s.log_message('sent n2k message: %s', msg)
        
#    def log_message(self, format, *args):
#        pass

class ThreadedHTTPServer(ThreadingMixIn, BaseHTTPServer.HTTPServer):
    """ This class allows to handle requests in separated threads.
    No further content needed, don't touch this. """
       
if __name__ == '__main__':
    server_class = ThreadedHTTPServer
    httpd = server_class((HOST_NAME, PORT_NUMBER), MyHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
