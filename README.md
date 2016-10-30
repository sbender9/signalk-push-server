# signalk-push-server
A server that pushes notifications to [WilhelmSK](https://itunes.apple.com/us/app/wilhelmsk/id1150499484?mt=8) based on SignalK data via Amazon SNS

Hopefully, this is all temporary. Work is being done to get this integrated into the SignalK standard and into signalk-server-node. I'm also working with the iKommunicate folks to see if anything can be done there.

It currently has excessive pitch, roll, wind and shallow depth alarms. Also sends any SignalK notifications out.

Modify signalk_alert_pusher.py to change configuration:

```python
#SignalK Server
HOST='localhost'
PORT=3000

#Alarm Thresholds
excesive_attitute_alarm = 5.0
excesive_wind_alarm = 20.0
high_wind_alarm = 10.0
shallow_depth_alarm = 8.0
```

Install Amazon's [Boto 3](https://aws.amazon.com/sdk-for-python/) python API's:

```
pip install boto3
```

Copy all of the .py files to your server.
Make sure that n2k_writer.py is executable and in your path.
Run the two servers in the background. 
```
/path/push_server.py > /dev/null 2>&1 &
/path/signalk_alert_pusher.py > /dev/null 2>&1 &
```

In WilhelmSK, connect to your boat and go to the Notificaion settings. Check the "Enable Notifications" box. (You must be currently connected to your boat for this to work).
This currently requires the WilhelmSK Beta (1.1.0 build 9)

You can also get NMEA 2000 Raymarine autopilot control and Raymarine/Seatalk Alarms with signalk-node-server by copying the code in ./canboat and ./signalk-server-node into those projects. Make sure you have their latest code from git hub.

Your signalk-node-server/bin/actisense-serial-n2kd should look something like:

```
n2k_writer.py 2>/dev/null | actisense-serial /dev/ttyUSB0 | analyzer -json -si
```

***Please note that this allows anyone with access to port 5000 on your server to send NMEA 2000 messages on your network***

***Autopilot control is still experimental, do not rely on WilhelmSK alone to control your autopilot and please be safe!***
