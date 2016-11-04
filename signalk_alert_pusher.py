#!/usr/bin/python

import time
import exceptions
import math
import socket
import json
import sys
from subprocess import call
from pprint import pprint
from datetime import datetime, timedelta
import httplib
import traceback
import math
from  aws_push import push_to_amazon_sns
import push_server
import BaseHTTPServer
from SocketServer import ThreadingMixIn
import threading
import signalk_ws_server

#SignalK Server
HOST='localhost'
PORT=3000

local_alarms = {}

last_alarm_times = {}
last_notifications = {}
last_wind = None
last_pitch = None
last_roll = None

depth_path = 'environment.depth.belowTransducer.value'
offset_path = 'environment.depth.surfaceToTransducer.value'
battery_status_path = 'electrical.batteries.%d.voltage.value'
wind_path = 'environment.wind.speedApparent.value'
roll_path = 'navigation.attitude.roll'
pitch_path = 'navigation.attitude.pitch'

notification_data = {
    'engineOverTemperature': {
        'paths': ['propulsion.port.temperature.value'],
        'msg': 'The engine temperature is %s'
        },
    'engineLowOilPressure': {
        'paths': [ 'propulsion.port.oilPressure.value' ],
        'msg': 'The engine oil pressure is %s'
        },
    'lowSystemVoltage': {
        'paths': [ 'electrical.batteries.0.voltage.value',
                   'electrical.batteries.1.voltage.value' ],
        'msg': 'A battery voltage is low. Starter bank is %0.2f. House bank is %0.2f'
        }
}

def deg2rad(deg):
    return deg * (math.pi/180)

def calc_distance(lat1, long1, lat2, long2):
    dlon = deg2rad(long2 - long1)
    dlat = deg2rad(lat2 - lat1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(deg2rad(lat1)) * math.cos(deg2rad(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2( math.sqrt(a), math.sqrt(1-a) )
    R = 6371.0
    d = R * c
    return d

def meters_to_feet(val):
    return val * 3.28084

def ms_to_knots(val):
    return val * 1.94384;

def load_json(host, port, path=""):
    conn = httplib.HTTPConnection(host, port)
    conn.request("GET", "/signalk/v1/api/vessels/self" + path)
    res = conn.getresponse()
    if res.status != 200:
        print "Error connecting to %s:%d: %d %s" % (host, port, res.status, res.reason)
        return None
    else:
        return res.read()

def get_from_path(element, json):
    try:
        return reduce(lambda d, key: d[key], element.split('.'), json)
    except exceptions.KeyError:
        return None

def make_alarm(title, body, state, category=None, path=None, isGenerated=False):
    alarm = {}
    alarm['title'] = title
    alarm['body'] = body
    alarm['state'] = state
    if category:
        alarm['category'] = category
    if path:
        alarm['path'] = path
    alarm['isGenerated'] = isGenerated
    return alarm

def check_anchor(vessel, alarm_config):
    conf = alarm_config.get('anchor', None)

    if conf != None and conf['enabled'] == 1:
        position = push_server.read_anchor_position()
       
        radius = conf['value']
        lat1 = get_from_path('navigation.position.latitude', vessel)
        long1 = get_from_path('navigation.position.longitude', vessel)

        if not lat1 or not long1:
            return None

        if len(position) != 2:
            position['latitude'] = lat1
            position['longitude'] = long1
            if last_alarm_times.has_key('Anchor Alarm'):
                del last_alarm_times['Anchor Alarm']
            push_server.save_anchor_position(position)
            return []

        lat2 = position['latitude']
        long2 = position['longitude']
#        lat2 = get_from_path('navigation.courseGreatCircle.nextPoint.position.latitude', vessel)
#        long2 = get_from_path('navigation.courseGreatCircle.nextPoint.position.longitude', vessel)

        feet = calc_distance(lat1, long1, lat2, long2) * 3280.84
        
        if feet > radius:
            return [make_alarm('Anchor Alarm', 'The anchor is %0.2f ft away' 
                               % feet, 'alarm', path='notifications.anchorDrift',
                               isGenerated=True)]
    return None

def check_depth(vessel, alarm_config):
    conf = alarm_config.get('shallow_depth',None)
    if conf != None and conf['enabled'] == 1:
        shallow_depth_alarm = conf['value']
        mdepth = get_from_path(depth_path, vessel)
        offset = get_from_path(offset_path, vessel)

        if not mdepth or not offset:
            return None

        mdepth = mdepth + offset
        fdepth = meters_to_feet(mdepth)

        #print 'depth', fdepth

        if fdepth < shallow_depth_alarm:
            return [make_alarm('Shallow Depth', 'Depth is %0.2f ft' 
                               % fdepth, 'alarm', path='notifications.shallowDepth',
                               isGenerated=True)]
    return None

def check_high_wind(vessel, alarm_config):
    global last_wind
    speed = get_from_path(wind_path, vessel)

    if not speed:
        return None
    
    kspeed = ms_to_knots(speed)
    #print 'wind', kspeed
    last_wind = kspeed

    high_wind = alarm_config.get('high_wind',None)
    
    if high_wind != None and high_wind['enabled'] == 1 and kspeed > high_wind['value']:
      return [make_alarm('High Wind', 'Wind Speed is %0.0f kts' 
                         % kspeed, 'alert', path='notifications.highWind',
                         isGenerated=True)]
    return None

def check_excessive_wind(vessel, alarm_config):
    speed = get_from_path(wind_path, vessel)

    if not speed:
        return None
    
    kspeed = ms_to_knots(speed)

    excessive_wind = alarm_config.get('excessive_wind',None)
    
    if excessive_wind != None and excessive_wind['enabled'] == 1 and kspeed > excessive_wind['value']:
        return [make_alarm('Excessive Wind', 'Wind Speed is %0.2f kts' 
                           % kspeed, 'alarm', path='notifications.excessiveWind',
                           isGenerated=True)]
    return None

def check_roll(vessel, alarm_config):
    global last_roll
    roll = get_from_path(roll_path, vessel)

    if not roll:
        return None
    
    roll = math.degrees(roll)
    
    last_roll = roll

    conf = alarm_config.get('excessive_attitute',None)

    if conf != None and conf['enabled'] == 1:
        if roll > conf['value']:
            return [ make_alarm('Excessive Attitude', 'Roll is %0.2f' % roll,
                                'alert', path='notifications.excessiveRoll',
                                isGenerated=True) ]

    return None

def check_pitch(vessel, alarm_config):
    global last_pitch
    pitch = get_from_path(pitch_path, vessel)

    if not pitch:
        return None
    
    pitch = math.degrees(pitch)
    
    last_pitch = pitch

    conf = alarm_config.get('excessive_attitute',None)

    if conf != None and conf['enabled'] == 1:
        if pitch > conf['value']:
            return [make_alarm('Excessive Attitude', 'Pitch is %0.2f' 
                               % pitch, 'alert', path='notifications.excessivePitch',
                               isGenerated=True)]

    return None

def check_for_notifications(vessel):
    alarms = []
    if vessel.has_key('notifications'):
        notifications = vessel['notifications']

        if notifications and len(notifications):
            #print notifications
            for key in notifications.keys():
                #pprint(notifications[key])

                notif = notifications[key]

                if notif.has_key('$source') and notif['$source'] == 'alerts_pusher.XX':
                    continue
                
                path = 'notifications.%s' % key                        

                if notif['state'] != 'normal':
                    msg = notif['message']

                    #if notif.has_key('pgn') and notif['pgn'] == 65288:
                      #cat = 'alarm_with_ack'
                    if key == 'autopilotPilotWayPointAdvance':
                        cat = 'advance_waypoint'
                    else:
                        cat = 'alarm'
                    alarm = make_alarm(None, msg, 'alarm', path=path, category=cat)
                    if notification_data.has_key(key):
                        nd = notification_data[key]
                        paths = nd['paths']
                        vals = ()
                        for path in paths:
                            #print get_from_path(path, vessel)
                            vals = vals + (get_from_path(path, vessel),)

                        alarm['body'] = nd['msg'] % vals

                    alarm['timestamp'] = notif['timestamp']
                    alarms.append(alarm)
                else:
                    last_notifications.pop(path,None)

    return alarms

def format_n2k_date():
    return time.strftime('%Y-%m-%dT%H:%M.%SZ', time.gmtime())

def publish_alarm(alarm, state=None, methods=['visual', 'sound' ]):
    global uuid
    timestamp = format_n2k_date()
    if not state:
        state = alarm['state']
    value = {
	    'state': state,
	    'timestamp': timestamp
    }

    if alarm.has_key('body'):
    	value['message'] = alarm['body']

    if state != 'normal':
    	value['method'] = methods

    update = {
        "updates":[
            {
                "source":{"label":"alert_pusher"},
                "timestamp": timestamp,
                "values":[
                    {
                        "path": alarm['path'],
                        "value": value
                    }
                ]
            }
        ],
        "context":"vessels." + uuid
    }
    local_alarms[alarm['path']] = alarm
    print 'publish: ', update
    signalk_ws_server.SignalKSocketHandler.send_updates(update)

def clear_alarm(vessel, path):
    existing = get_from_path(path, vessel)
    if existing and existing['state'] != 'normal':
        publish_alarm({ "path": path }, 'normal')
        del local_alarms[path]

def silence_alarm(path):
    try:
        notification = json.loads(load_json(HOST, PORT, "/" + path.replace('.', '/')))
        alarm = {
            "path": path,
            "body": notification['message']
        }
        publish_alarm(alarm, notification["state"], methods=["visual"])
        
    except socket.error:
        pass
    
def check_alarm(vessel, alarm_config, function, path):
    alarms = function(vessel, alarm_config)
    if not alarms or len(alarms) == 0:
        clear_alarm(vessel, path)
        
    return alarms

def vessel_has_matching_alarm(vessel, alarm):
    match = get_from_path(alarm['path'], vessel)
    #print match, alarm
    if match and match['state'] == alarm['state'] and alarm['body'] == match['message']:
        return True
    return False

def check_for_alarms(vessel):
    alarms = []
    alarm_checkers = ((check_depth, 'notifications.shallowDepth'),
                      (check_anchor, 'notifications.anchorDrift'),
                      (check_high_wind, 'notifications.highWind'),
                      (check_excessive_wind,'notifications.excessiveWind'),
                      (check_roll, 'notifications.excessiveRoll'),
                      (check_pitch, 'notifications.excessivePitch'))

    alarm_config = push_server.read_alarm_config()

    alarms.extend(check_for_notifications(vessel))

    for func in alarm_checkers:
        res = check_alarm(vessel, alarm_config, func[0], func[1])
        if res:
            alarms.extend(res)

    if last_wind != None and last_pitch != None and last_roll != None:
        print "%s - Wind: %0.2f Pitch: %0.2f Roll: %0.2f" % (time.asctime(time.localtime(time.time())), last_wind, last_pitch, last_roll)

    history = push_server.read_history()

    devices = push_server.read_devices()

    for alarm in alarms:
#        type = alarm['type']
        path = alarm['path']

        if len(signalk_ws_server.SignalKSocketHandler.waiters) > 0:
            if vessel_has_matching_alarm(vessel, alarm):
                continue
        else:
            if alarm.has_key('category'):
                if last_notifications.has_key(path):
                    continue
        
            
            elif last_alarm_times.has_key(path):
                last_time = last_alarm_times[path]
                hour_from = last_time + timedelta(minutes=15)
                if datetime.now() < hour_from:
                    continue

        alarm['date'] = time.strftime('%m/%d %H:%M', time.localtime(time.time()))
        history.append(alarm)

        if alarm.has_key('category'):
            category = alarm['category']
        else:
            category = None

        for device in devices.values():
            uuid = None
            if device.has_key('uuid'):
                uuid = device['uuid']

            try:
                push_to_amazon_sns(alarm['title'], alarm['body'],
                                   device['targetArn'], 'us-east-1',
                                   device['accessKey'],
                                   device['secretAccessKey'],
                                   path,
                                   uuid,
                                   category)
            except:
                print("Error sending to Amazon SNS:", sys.exc_info())
                traceback.print_exc()

        if alarm.has_key('category'):
            last_notifications[path] = alarm
        else:
            last_alarm_times[path] = datetime.now()

        if path and alarm['isGenerated']:
            publish_alarm(alarm)
        
        print "%s - Alert: %s: %s" % (time.asctime(time.localtime(time.time())), alarm['title'], alarm['body'])

    if len(history) > 100:
        history = history[len(history)-100:]

    push_server.save_history(history)

def alarm_check_loop():
    global uuid
    while 1:
        try:
            try:
                messages = load_json(HOST, PORT)
            except socket.error:
                messages = None

                
            if messages:
                dict = json.loads(messages)
                uuid = dict['uuid']
                
                check_for_alarms(dict)
        except:
            print("Unexpected error:", sys.exc_info())
            traceback.print_exc()

        sys.stdout.flush()
        time.sleep(2)
        
def start_push_server():
    push_server.start(silence_alarm)
    
if __name__ == '__main__':
    thread = threading.Thread(target = signalk_ws_server.main)
    thread.daemon = True
    thread.start()

    thread = threading.Thread(target = start_push_server)
    thread.daemon = True
    thread.start()
    
    alarm_check_loop()
