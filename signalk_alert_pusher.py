#!/usr/bin/python

import time
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

#SignalK Server
HOST='localhost'
PORT=3000

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

def load_json(host, port):
    conn = httplib.HTTPConnection(host, port)
    conn.request("GET", "/signalk/v1/api/")
    res = conn.getresponse()
    if res.status != 200:
        print "Error connecting to %s:%d: %d %s" % (host, port, res.status, res.reason)
        return None
    else:
        return res.read()

def get_from_path(element, json):
    return reduce(lambda d, key: d[key], element.split('.'), json)

def make_alarm(title, body, type=None, category=None):
    alarm = {}
    alarm['title'] = title
    alarm['body'] = body
    if not type:
        type = title
    alarm['type'] = type
    if category:
        alarm['category'] = category

    return alarm

def check_anchor(vessel, alarm_config):
    conf = alarm_config.get('anchor', None)

    if conf != None and conf['enabled'] == 1:
        position = push_server.read_anchor_position()
       
        radius = conf['value']
        lat1 = get_from_path('navigation.position.latitude', vessel)
        long1 = get_from_path('navigation.position.longitude', vessel)

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
                               % feet)]
    return []

def check_depth(vessel, alarm_config):
    conf = alarm_config.get('shallow_depth',None)
    if conf != None and conf['enabled'] == 1:
        shallow_depth_alarm = conf['value']
        mdepth = get_from_path(depth_path, vessel)
        offset = get_from_path(offset_path, vessel)

        mdepth = mdepth + offset
        fdepth = meters_to_feet(mdepth)

        #print 'depth', fdepth

        if fdepth < shallow_depth_alarm:
            return [make_alarm('Shallow Depth', 'Depth is %0.2f ft' 
                               % fdepth)]
    return []

def check_wind(vessel, alarm_config):
    global last_wind
    speed = get_from_path(wind_path, vessel)
    kspeed = ms_to_knots(speed)
    #print 'wind', kspeed
    last_wind = kspeed

    excessive_wind = alarm_config.get('excessive_wind',None)
    high_wind = alarm_config.get('high_wind',None)
    
    if excessive_wind != None and excessive_wind['enabled'] == 1 and kspeed > excessive_wind['value']:
        return [make_alarm('Excessive Wind', 'Wind Speed is %0.2f kts' 
                           % kspeed, 'excessive_wind')]
    elif high_wind != None and high_wind['enabled'] == 1 and kspeed > high_wind['value']:
        return [make_alarm('High Wind', 'Wind Speed is %0.2f kts' 
                           % kspeed, 'high_wind')]
    return []

def check_attitude(vessel, alarm_config):
    global last_pitch, last_roll
    roll = get_from_path(roll_path, vessel)
    pitch = get_from_path(pitch_path, vessel)

    roll = math.degrees(roll)
    pitch = math.degrees(pitch)
    
    last_pitch = pitch
    last_roll = roll
    #print 'attitude', pitch, roll
    alarms = []

    conf = alarm_config.get('excessive_attitute',None)

    if conf != None and conf['enabled'] == 1:
        if roll > conf['value']:
            alarms.append(make_alarm('Excessive Attitude', 'Roll is %0.2f' % roll,
                                     'Roll'))

        if pitch > conf['value']:
            alarms.append(make_alarm('Excessive Attitude', 'Pitch is %0.2f' 
                                     % pitch, 'Pitch'))

    return alarms

def check_for_notifications(vessel):
    alarms = []
    if vessel.has_key('notifications'):
        notifications = vessel['notifications']

        if notifications and len(notifications):
            #print notifications
            for key in notifications.keys():
                #pprint(notifications[key])

                notif = notifications[key]
                if notif['state'] != 'normal':
                    msg = notif['message']

                    #if notif.has_key('pgn') and notif['pgn'] == 65288:
                      #cat = 'alarm_with_ack'
                    if key == 'autopilotPilotWayPointAdvance':
                        cat = 'advance_waypoint'
                    else:
                        cat = 'alarm'
                        
                    alarm = make_alarm(None, msg, key, cat)
                    if notification_data.has_key(key):
                        nd = notification_data[key]
                        paths = nd['paths']
                        vals = ()
                        for path in paths:
                            #print get_from_path(path, vessel)
                            vals = vals + (get_from_path(path, vessel),)

                        alarm['body'] = nd['msg'] % vals

                    alarm['timestamp'] = notif['timestamp']
                    alarm['path'] = 'notifications.%s' % key
                    alarms.append(alarm)
                else:
                    last_notifications.pop(key,None)

    return alarms

def check_for_alarms(vessel):
    alarms = []

    alarm_config = push_server.read_alarm_config()

    alarms.extend(check_for_notifications(vessel))

    alarms.extend(check_depth(vessel, alarm_config))

    alarms.extend(check_anchor(vessel, alarm_config))

    alarms.extend(check_wind(vessel, alarm_config))

    alarms.extend(check_attitude(vessel, alarm_config))

    print "%s - Wind: %0.2f Pitch: %0.2f Roll: %0.2f" % (time.asctime(time.localtime(time.time())), last_wind, last_pitch, last_roll)

    #alarms = []

    history = push_server.read_history()

    devices = push_server.read_devices()
    
    for alarm in alarms:
        type = alarm['type']
        if alarm.has_key('category'):
            #print last_notification_time
            #print alarm
            if last_notifications.has_key(type):
                continue
        elif last_alarm_times.has_key(type):
            last_time = last_alarm_times[type]
            hour_from = last_time + timedelta(minutes=15)
            if datetime.now() < hour_from:
                continue

        alarm['date'] = time.strftime('%m/%d %H:%M', time.localtime(time.time()))
        history.append(alarm)

        if alarm.has_key('category'):
            category = alarm['category']
        else:
            category = None

        if alarm.has_key('path'):
            path = alarm['path']
        else:
            path = None

        for device in devices.values():
            uuid = None
            if device.has_key('uuid'):
                uuid = device['uuid']

            push_to_amazon_sns(alarm['title'], alarm['body'],
                               device['targetArn'], 'us-east-1',
                               device['accessKey'],
                               device['secretAccessKey'],
                               path,
                               uuid,
                               category)

        if alarm.has_key('category'):
            last_notifications[type] = alarm
        else:
            last_alarm_times[type] = datetime.now()
        
        print "%s - Alert: %s: %s" % (time.asctime(time.localtime(time.time())), alarm['title'], alarm['body'])

    if len(history) > 100:
        history = history[len(history)-100:]

    push_server.save_history(history)
    
if __name__ == '__main__':
    while 1:
        try:
            messages = load_json(HOST, PORT)

            if messages:
                dict = json.loads(messages)

                vessels = dict['vessels']
                if vessels and len(vessels):
                    vessel = vessels[vessels.keys()[0]];
                    if vessel:
                        check_for_alarms(vessel)
        except:
            print("Unexpected error:", sys.exc_info())
            traceback.print_exc()

        sys.stdout.flush()
        time.sleep(2)
