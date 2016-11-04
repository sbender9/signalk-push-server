#!/usr/bin/python

import sys
import n2k_writer
import signalk_alert_pusher
import threading

log_file = '/tmp/wilhelm_server.log'

if __name__ == '__main__':
  stdout = sys.stdout
  stderr = sys.stderr

  new_output = open('/tmp/wilhelm_server.log', "w")
  sys.stdout = new_output
  sys.stderr = new_output
  
  thread = threading.Thread(target = signalk_alert_pusher.main)
  thread.daemon = True
  thread.start()

  n2k_writer.main(stdout)
