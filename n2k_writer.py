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

state_commands = {
    "auto":    "%s,3,126208,%s,%s,17,01,63,ff,00,f8,04,01,3b,07,03,04,04,40,00,05,ff,ff",
    "wind":    "%s,3,126208,%s,%s,17,01,63,ff,00,f8,04,01,3b,07,03,04,04,00,01,05,ff,ff",
    "route":   "%s,3,126208,%s,%s,17,01,63,ff,00,f8,04,01,3b,07,03,04,04,80,01,05,ff,ff",
    "standby": "%s,3,126208,%s,%s,17,01,63,ff,00,f8,04,01,3b,07,03,04,04,00,00,05,ff,ff"
    }

heading_command =        "%s,3,126208,%s,%s,14,01,50,ff,00,f8,03,01,3b,07,03,04,06,%02x,%02x";
wind_direction_command = "%s,3,126208,%s,%s,14,01,41,ff,00,f8,03,01,3b,07,03,04,04,%02x,%02x";


raymarine_silence =  "%s,7,65361,%s,255,8,3b,9f,%02x,%02x,ff,ff,ff,ff"

raymarine_ttw_Mode = "%s,3,126208,%s,%s,17,01,63,ff,00,f8,04,01,3b,07,03,04,04,81,01,05,ff,ff"

raymarine_ttw =      "%s,3,126208,%s,%s,21,00,00,ef,01,ff,ff,ff,ff,ff,ff,04,01,3b,07,03,04,04,6c,05,1a,50"

default_src = '1'

def format_n2k_date():
    return time.strftime('%Y-%m-%dT%H:%M.%SZ', time.gmtime())

#2016-09-06T23:01:42.759Z

def send(msg):
    sys.stdout.write(msg + "\r\n")
    sys.stdout.flush()

def set_autopilot_heading(dict):
    val = dict['angle']
    send(heading_command % (format_n2k_date(), default_src, dict['dst'], val & 0xff,
                            ((val >> 8) & 0xff)))

def set_autopilot_wind_angle(dict):
    val = dict['angle']
    print val
    send(wind_direction_command % (format_n2k_date(), default_src, dict['dst'], val & 0xff,
                                   ((val >> 8) & 0xff)))
    
def set_autopilot_state(dict):
    command = state_commands[dict['value']]
    send(command % (format_n2k_date(), default_src, dict['dst']))

def turn_to_waypoint(dict):
    send(raymarine_ttw_Mode % (format_n2k_date(), default_src, dict['dst']))
    send(raymarine_ttw % (format_n2k_date(), default_src, dict['dst']))

def silence_rayarine_alarm(dict):
    msg = raymarine_silence % (format_n2k_date(), default_src, dict['alarmId'], dict['groupId'])
    send(msg)
    
def send_command(dict):
    globals()[dict['path']](dict)

class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_HEAD(s):
        s.send_response(200)
        s.send_header("Content-type", "text/html")
        s.end_headers()
        
    def do_POST(s):
        data = s.rfile.read(int(s.headers['Content-Length']))
        dict = json.loads(data)
        
        if s.path == '/send_delta':
            send_command(dict)
        elif s.path == '/send':
            msg = s.rfile.read(int(s.headers['Content-Length']))

            outp  = msg + '\r\n'
            sys.stdout.write(outp)
            sys.stdout.flush()

            s.log_message('sent n2k message: %s', msg)
            
        s.send_response(200)
        s.end_headers()
            
        
    def log_message(self, format, *args):
       pass

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
