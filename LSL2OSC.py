
# Fetching data from LSL, pipe to OSC.

# pointing to local copies of libs
import sys, os
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.realpath(__file__)), './continousreader'))
from ContinuousReader import ContinuousReader

import argparse, time
from pythonosc import udp_client

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipe data from LSL to OSC.")
    parser.add_argument("--pred", type = str, default = "", help = """A predicate to use to filter streams. E.g. "type='EEG'", "type='EEG' and name='BioSemi'", "(type='EEG' and name='BioSemi') or type='HR'". Note that that predicat is case-sensitive. Default: empty, record all streams. CAUTION: if the predicate is malformed (e.g. messing up parentheses, or invalid characters) it can crash the outlet!""")
    parser.add_argument("--ip", default = "127.0.0.1",
      help="The IP or address of the OSC server (default: 127.0.0.1).")
    parser.add_argument("--port", type = int, default = 5005,
      help="The port the OSC server is listening on (default: 5005).")
    parser.add_argument("-v", "--verbose", action='store_true', help="Print more verbose information.")
    args = parser.parse_args()

    print("Starting OSC client to address %s and port %d" % (args.ip, args.port))
    osc_client = udp_client.SimpleUDPClient(args.ip, args.port)

    print("Now watching for streams...")
    cr = ContinuousReader(pred=args.pred, fetch_all=True)

    def show_data(data):
        """
        Callback function for LSL samples, will get data tuples with (sample, timestamp, name, type, hostname, uid, sampling rate, data format).
        Forward to OSC server.
        """
        sample = data[0]
        stream_name = data[2]
        stream_type = data[3]
        osc_url = "/%s/%s" % (stream_type, stream_name)
        if args.verbose:
            print(osc_url, sample)
        osc_client.send_message(osc_url, sample)

    try:
        while True:
            cr.callmeback(show_data, pull_last=True)
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("Catching Ctrl-C or SIGTERM, bye!")
    print("The end.")
