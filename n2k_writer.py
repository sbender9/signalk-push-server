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
autopilot_dst = '204'
everyone_dst = '255'

n2k_output = None

def format_n2k_date():
    return time.strftime('%Y-%m-%dT%H:%M.%SZ', time.gmtime())

def send(msg):
    global n2k_output
    if n2k_output:
        out = n2k_output
    else:
        out = sys.stdout
    out.write(msg + "\r\n")
    out.flush()

def set_autopilot_heading(val):
    send(heading_command % (format_n2k_date(), default_src, autopilot_dst, val & 0xff,
                            ((val >> 8) & 0xff)))

def set_autopilot_wind_angle(val):
    send(wind_direction_command % (format_n2k_date(), default_src, autopilot_dst, val & 0xff,
                                   ((val >> 8) & 0xff)))
    
def set_autopilot_state(value):
    command = state_commands[value]
    send(command % (format_n2k_date(), default_src, autopilot_dst))

def turn_to_waypoint(val):
    send(raymarine_ttw_Mode % (format_n2k_date(), default_src, autopilot_dst))
    send(raymarine_ttw % (format_n2k_date(), default_src, autopilot_dst))

def silence_rayarine_alarm(dict):
    msg = raymarine_silence % (format_n2k_date(), default_src, dict['alarmId'], dict['groupId'])
    send(msg)

function_map = {
    "steering.autopilot.state": set_autopilot_state,
    "steering.autopilot.target.windAngleApparent": set_autopilot_wind_angle,
    "steering.autopilot.target.headingMagnetic": set_autopilot_heading,
    "turn_to_waypoint": turn_to_waypoint,
    "silence_rayarine_alarm": silence_rayarine_alarm
}
    
def send_command(dict):
    if dict.has_key('updates'):
        for update in dict['updates']:
            if update.has_key('values'):
                for value in update['values']:
                    if function_map.has_key(value['path']):
                        function_map[value['path']](value['value'])
                    
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
            s.log_message("send delta: " + json.dumps(dict, sort_keys=True, indent=2))
            s.send_response(200)
        else:
            s.send_response(404)
            
        s.end_headers()
            
        
    def log_message(self, format, *args):
        global n2k_output
        if n2k_output:
            BaseHTTPServer.BaseHTTPRequestHandler.log_message(self, format, *args)
        
class ThreadedHTTPServer(ThreadingMixIn, BaseHTTPServer.HTTPServer):
    """ This class allows to handle requests in separated threads.
    No further content needed, don't touch this. """

def main(output):
    global n2k_output
    if output:
        n2k_output = output
    server_class = ThreadedHTTPServer
    httpd = server_class((HOST_NAME, PORT_NUMBER), MyHandler)
    print time.asctime(), "n2k_writer listening on port %s" % PORT_NUMBER
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()

if __name__ == '__main__':
    main(None)
