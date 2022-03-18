
# Fetching data from LSL, pipe to OSC.

# pointing to local copies of libs
import sys, os
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.realpath(__file__)), './continousreader'))
from ContinuousReader import ContinuousReader

import argparse, time

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipe data from LSL to OSC.")
    parser.add_argument("--pred", type = str, default = "", help = """A predicate to use to filter streams. E.g. "type='EEG'", "type='EEG' and name='BioSemi'", "(type='EEG' and name='BioSemi') or type='HR'". Note that that predicat is case-sensitive. Default: empty, record all streams. CAUTION: if the predicate is malformed (e.g. messing up parentheses, or invalid characters) it can crash the outlet!""")
    args = parser.parse_args()

    cr = ContinuousReader(pred=args.pred, fetch_all=True)

    def show_data(data):
        print(data)

    print("Now watching for streams...")
    try:
        while True:
            cr.callmeback(show_data, pull_last=True)
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("Catching Ctrl-C or SIGTERM, bye!")
    print("The end.")
