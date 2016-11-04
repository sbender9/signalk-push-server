#!/usr/bin/python

import sys
import n2k_writer
import signalk_alert_pusher
import threading
import argparse

class MyParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help(sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
  stdout = sys.stdout
  stderr = sys.stderr

  parser = argparse.ArgumentParser(description='WilhelmSK Server')
  parser.add_argument('--log', action='store', dest='log_file',
                      help='log file',required=True,type=argparse.FileType('w'))
  parser.add_argument('--signalk-listen-port', action='store', dest='signalk_listen_port',
                      help='Port for incoming websockets connections',default=3001,type=int)  

  args = parser.parse_args()
  
  sys.stdout = args.log_file
  sys.stderr = args.log_file
  
  thread = threading.Thread(target = signalk_alert_pusher.main, args=(args.signalk_listen_port,))
  thread.daemon = True
  thread.start()

  n2k_writer.main(stdout)
