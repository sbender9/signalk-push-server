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

#example registration json
# {
#     "accessKey": "KEY", 
#     "deviceName": "Scott Bender's iPhone 6", 
# "secretAccessKey": "SECRET", 
#     "targetArn": "arn:aws:sns:us-east-1:1234:endpoint/APNS_SANDBOX/NOT_A_REAL_ARN",
#     "uuid": "uuid"
# }

HOST_NAME = ''
PORT_NUMBER = 3120 
devices_file = 'registerd_devices.json'
history_file = 'alarm_history.json'
alarm_config_file = 'alarm_config.json'
anchor_position_file = 'anchor_position.json'
supported_alarms_file = 'supported_alarms.json'

def we_are_frozen():
    # All of the modules are built-in to the interpreter, e.g., by py2exe
    return hasattr(sys, "frozen")

def module_path():
    encoding = sys.getfilesystemencoding()
    if we_are_frozen():
        return os.path.dirname(unicode(sys.executable, encoding))
    return os.path.dirname(unicode(__file__, encoding))

def read_history():
    return read_json_array(history_file)

def save_history(history):
    save_json(history_file, history)

def read_devices():
    return read_json_dict(devices_file)

def save_devices(devices):
    save_json(devices_file, devices)

def read_alarm_config():
    return read_json_dict(alarm_config_file)

def save_alarm_config(config):
    save_json(alarm_config_file, config)

def read_anchor_position():
    return read_json_dict(anchor_position_file)

def save_anchor_position(position):
    return save_json(anchor_position_file, position)

def read_supported_alarms():
    return read_json_dict(supported_alarms_file)

def read_json_array(file_name):
    if not os.path.exists(os.path.join(module_path(), file_name)):
        return []
    return read_json(file_name)

def read_json_dict(file_name):
    if not os.path.exists(os.path.join(module_path(), file_name)):
        return {}
    return read_json(file_name)

def read_json(file_name):
    f = open(os.path.join(module_path(), file_name))
    dict = json.loads(f.read())
    f.close()
    return dict

def save_json(file_name, json_data):
    f = open(os.path.join(module_path(), file_name), "w")
    f.write(json.dumps(json_data, sort_keys=True, indent=2))
    f.close()

alarm_silence_callback = None
   
    
class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    def do_HEAD(s):
        s.send_response(200)
        s.send_header("Content-type", "text/html")
        s.end_headers()
    def do_GET(s):
        """Respond to a GET request."""
        parsed = urlparse(s.path)
        if s.path == '/pushsupport':
            s.send_response(200)
            #s.send_header("Content-type", "text/json")
            s.end_headers()
        elif s.path == '/get_history':
            history = read_history()
            s.send_response(200)
            s.send_header("Content-type", "text/json")
            s.end_headers()
            s.wfile.write(json.dumps(history))
        elif s.path == '/get_alarm_config':
            history = read_alarm_config()
            s.send_response(200)
            s.send_header("Content-type", "text/json")
            s.end_headers()
            s.wfile.write(json.dumps(history))
        elif s.path == '/get_supported_alarms':
            history = read_supported_alarms()
            s.send_response(200)
            s.send_header("Content-type", "text/json")
            s.end_headers()
            s.wfile.write(json.dumps(history))
        else:
            s.send_response(404)
            s.end_headers()
    def do_POST(s):
        parsed = urlparse(s.path)
        if s.path == '/register_device':
            data = s.rfile.read(int(s.headers['Content-Length']))
            dict = json.loads(data)
            devices = read_devices()
            devices[dict['targetArn']] = dict
            save_devices(devices)
            s.send_response(200)
            s.end_headers()
        elif s.path == '/unregister_device':
            data = s.rfile.read(int(s.headers['Content-Length']))
            dict = json.loads(data)
            devices = read_devices()
            if devices.has_key(dict['targetArn']):
                del devices[dict['targetArn']]
            save_devices(devices)
            s.send_response(200)
            s.end_headers()
        elif s.path == '/device_exists':
            data = s.rfile.read(int(s.headers['Content-Length']))
            dict = json.loads(data)
            devices = read_devices()
            #print dict['targetArn']
            if devices.has_key(dict['targetArn']):
                s.send_response(200)
            else:
                s.send_response(404)
            s.end_headers()
        elif s.path == '/set_alarm_config':
            data = s.rfile.read(int(s.headers['Content-Length']))
            dict = json.loads(data)
            config = read_alarm_config()
            config.update(dict)
            save_alarm_config(config)

            if config.has_key('anchor') and config['anchor']['enabled'] == 0:
                save_anchor_position({})
            
            s.send_response(200)
            s.end_headers()
        elif s.path == '/silence_alarm':
            global alarm_silence_callback

            data = s.rfile.read(int(s.headers['Content-Length']))
            dict = json.loads(data)
            alarm_silence_callback(dict['path'])
            s.send_response(200)
            s.end_headers()
        else:
            s.send_response(404)
            s.end_headers()                                                

class ThreadedHTTPServer(ThreadingMixIn, BaseHTTPServer.HTTPServer):
    """ This class allows to handle requests in separated threads.
    No further content needed, don't touch this. """

def start(callback):
    #server_class = BaseHTTPServer.HTTPServer
    global alarm_silence_callback
    alarm_silence_callback = callback

    server_class = ThreadedHTTPServer
    httpd = server_class((HOST_NAME, PORT_NUMBER), MyHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()

if __name__ == '__main__':
    start(None)
