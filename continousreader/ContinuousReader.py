
from pylsl import ContinuousResolver, StreamInlet, LostError

class ContinuousReader():
    """
    Wrap LSL continuous resolver with some candy. Fetching all streams of one type, getting either values from the first one or from all, using uid to detect change.
    """
    def __init__(self, pred, fetch_all=False):
        """
        pred: A predicate to use to filter streams. E.g. "type='EEG'", "type='EEG' and name='BioSemi'", "(type='EEG' and name='BioSemi') or type='HR'". Note that that predicat is case-sensitive. If empty, grab all streams (you don't want that here).)
        fetch_all: will pull samples from all streams matching the predicate. If set to False, will pull samples from an arbitrary stream (first from ContinuousResolver result, which is not necessarily the first stream found)
        """
        self._cr = ContinuousResolver(pred = pred, forget_after = 5)
        self._fetch_all = fetch_all
        # used for the "simple" use-case, fetching from only one stream
        self._uid = None
        self._inlet = None
        # used for the more consuming "fetch_all" case, will hold info about known streams, because it is resource consuming to create inlets
        self._streams = {}

    def _simple_read(self, pull_last=False):
        """
        Here only fetch value from the first stream matching predicate
        pull_last: if True, will retrieve last value, skipping everything that occurred since last read
        """
        sample = None
        streams = self._cr.results()
        if len(streams) > 0:
            # stream changed, retrieve new inlet
            if streams[0].uid() != self._uid:
                self._inlet = StreamInlet(streams[0])
                self._uid = streams[0].uid()
            
            # fetch last value from stream
            try:
                sample, timestamp = self._inlet.pull_sample(timeout=0)
            except LostError:
                # stream broke, but wait for resolver to remove it from list
                print("stream broke")
                
            # if option set, fetch all samples since last visit
            if pull_last:
                new_sample = sample
                while new_sample is not None:
                    try:
                        sample = new_sample
                        new_sample, timestamp = self._inlet.pull_sample(timeout=0)
                    except LostError:
                        pass
        return sample


    def _updateStreams(self):
        """
        update internal stream list, for _multi_read()
        FIXME: takes time, especially when there is a new inlet to create, should be ran in background
        """
        # fetch current streams
        current_streams = {}
        for i in self._cr.results():
            current_streams[i.uid()] = i
       
        # prune streams that do not exist anymore
        streams_outdated = set(self._streams) - set(current_streams)
        for o in streams_outdated:
            print("Lost stream:", self._streams[o]['info'].name(), self._streams[o]['info'].type(), self._streams[o]['info'].hostname())
            # remove item, explicitely delete corresponding inlet
            s = self._streams.pop(o)
            del(s['inlet'])
   
        # add new streams
        streams_new = set(current_streams) - set(self._streams)
        for n in streams_new:
            print("Got new stream:", current_streams[n].name(), current_streams[n].type(), current_streams[n].hostname())
            # add stream to list, creating inlet
            self._streams[current_streams[n].uid()] = {"info": current_streams[n], "inlet": StreamInlet(current_streams[n])}
    
    def _multi_read(self, pull_last=False):
        """
        Here we fetch data from all streams matching pred. pull_last
        pull_last: makes less sense than with _simple_read(), discard all samples from all streams except for the last sample of the (arbitrarily) last stream.
        """
        self._updateStreams()

        new_sample = None
        # loop all current streams
        for s in self._streams.values():
            inlet = s['inlet']
            try:
                sample, timestamp = inlet.pull_sample(timeout=0)
            except LostError:
                # stream broke, but wait for resolver to remove it from list
                print("stream broke")

            # return as soon as we find a sample, unless pull_last is set
            if sample is not None and not pull_last:
                return sample

            # fetch all samples since last visit
            while sample is not None:
                new_sample = sample
                try:
                    sample, timestamp = inlet.pull_sample(timeout=0)
                except LostError:
                    print("stream broke")
                    sample = None
        # if we reach this point, either we did not find any sample, or we discarded all samples from inlets and return the last one
        return new_sample
        
    def read(self, pull_last=False):
        """
        pull_last: if True, will retrieve last value, skipping everything that occurred since last read
        """
        if self._fetch_all:
            return self._multi_read(pull_last)
        else:
            return self._simple_read(pull_last)
