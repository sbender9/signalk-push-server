# signalk-push-server
A server that pushes notifications to [WilhelmSK](https://itunes.apple.com/us/app/wilhelmsk/id1150499484?mt=8) based on SignalK data via Amazon SNS

Hopefully, this is all temporary. Work is being done to get this integrated into the SignalK standard and into signalk-server-node. I'm also working with the iKommunicate folks to see if anything can be done there.

It currently has anchor, excessive pitch, roll, wind and shallow depth alarms and also sends any SignalK notifications out.

Install tornada and Amazon's [Boto 3](https://aws.amazon.com/sdk-for-python/) python API's:

```
pip install boto3
pip install tornado
```

Copy all of the files to a direcrtory on your server. 
Copy alarm_config.json-sample to alarm_config.json

You can just run the push server.
```
/path/signalk_alert_pusher.py
```

Or, instead, if you also want autopilot control, edit your signalk-node-server/bin/actisense-serial-n2kd to look something like:

```
/usr/local/src/signalk-push-server/wilhelm_server.py --log /tmp/wilhelm_server.log | actisense-serial /dev/ttyUSB0 | analyzer -json -si
```


In WilhelmSK, connect to your boat and go to the Notificaion settings. Check the "Enable Notifications" box. (You must be currently connected to your boat for this to work).
This currently requires the WilhelmSK Beta (1.1.0 build 9+)




***Please note that this allows anyone with access to port 5000 on your server to send NMEA 2000 messages on your network***

***Autopilot control is still experimental, do not rely on WilhelmSK alone to control your autopilot and please be safe!***
