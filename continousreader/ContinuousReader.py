
# TODO: add option for inlet buffer size
# TODO: add option for ContinuousResolver forget_after
# TODO: simplify fetch_all / pull_last. E.g. remove fetch_all=False case? _multi_read with pull_last per stream? Also merge read() and callmeback()?

import pylsl

def fmt2string(format_code):
    """
    Convert LSL channel format index to an actual name
    FIXME: might be updated in the future, to sync with last pylsl / LSL
    """
    FMT_DICT = {
        pylsl.cf_float32: 'float32',
        pylsl.cf_double64: 'double64',
        pylsl.cf_string: 'string',
        pylsl.cf_int32: 'int32',
        pylsl.cf_int16: 'int16',
        pylsl.cf_int8: 'int8',
        pylsl.cf_int64: 'int64',
        pylsl.cf_undefined: 'undefined'
    }
    if format_code not in FMT_DICT:
        return 'unknown'
    return FMT_DICT[format_code]

class ContinuousReader():
    """
    Wrap LSL continuous resolver with some candy. Fetching all streams of one type, getting either values from the first one or from all, using uid to detect change. This class can be used either through read() to retrieve a sample per call, or through callmeback() to process each stream separately with a custom function.
    """
    def __init__(self, pred, fetch_all=False):
        """
        pred: A predicate to use to filter streams. E.g. "type='EEG'", "type='EEG' and name='BioSemi'", "(type='EEG' and name='BioSemi') or type='HR'". Note that that predicat is case-sensitive. If empty, grab all streams (you don't want that here).)
        fetch_all: will pull samples from all streams matching the predicate. If set to False, will pull samples from an arbitrary stream (first from ContinuousResolver result, which is not necessarily the first stream found)
        """
        self._cr = pylsl.ContinuousResolver(pred = pred, forget_after = 5)
        self._fetch_all = fetch_all
        # used for the "simple" use-case, fetching from only one stream
        self._uid = None
        self._inlet = None
        self._name = None
        self._type = None
        self._hostname = None
        self._srate = None
        self._format = None
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
                self._inlet = pylsl.StreamInlet(streams[0])
                self._uid = streams[0].uid()
                self._name = streams[0].name()
                self._type = streams[0].type()
                self._hostname = streams[0].hostname()
                self._srate = streams[0].nominal_srate()
                self._format = fmt2string(streams[0].channel_format())

            # fetch last value from stream
            try:
                sample, _ = self._inlet.pull_sample(timeout=0)
            except pylsl.LostError:
                # stream broke, but wait for resolver to remove it from list
                print("stream broke")
                
            # if option set, fetch all samples since last visit
            if pull_last:
                new_sample = sample
                while new_sample is not None:
                    try:
                        sample = new_sample
                        new_sample, _ = self._inlet.pull_sample(timeout=0)
                    except pylsl.LostError:
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
            print("Lost stream:", self._streams[o]['name'], self._streams[o]['type'], self._streams[o]['hostname'])
            # remove item, explicitely delete corresponding inlet
            s = self._streams.pop(o)
            del(s['inlet'])
   
        # add new streams
        streams_new = set(current_streams) - set(self._streams)
        for n in streams_new:
            print("Got new stream:", current_streams[n].name(), current_streams[n].type(), current_streams[n].hostname())
            # add stream to list, creating inlet
            self._streams[current_streams[n].uid()] = {
                "info": current_streams[n],
                "inlet": pylsl.StreamInlet(current_streams[n]),
                "name": current_streams[n].name(),
                "type": current_streams[n].type(),
                "hostname": current_streams[n].hostname(),
                "srate": current_streams[n].nominal_srate(),
                "format": fmt2string(current_streams[n].channel_format())
                }
    
    def _multi_read(self, pull_last=False):
        """
        Here we fetch data from all streams matching pred
        pull_last: makes less sense than with _simple_read(), discard all samples from all streams except for the last sample of the (arbitrarily) last stream.
        """
        self._updateStreams()

        new_sample = None
        # loop all current streams
        for s in self._streams.values():
            inlet = s['inlet']
            try:
                sample, timestamp = inlet.pull_sample(timeout=0)
            except pylsl.LostError:
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
                except pylsl.LostError:
                    print("stream broke")
                    sample = None
        # if we reach this point, either we did not find any sample, or we discarded all samples from inlets and return the last one
        return new_sample
        
    def read(self, pull_last=False):
        """
        Return a sample (if any) from matching streams.
        WARNING: use either read() or callmeback(), a sample process in one won't appear in the other.
        pull_last: if True, will retrieve last value, skipping everything that occurred since last read
        """
        if self._fetch_all:
            return self._multi_read(pull_last)
        else:
            return self._simple_read(pull_last)

    def _simple_callmeback(self, callback_fun, pull_last=False):
        """
        Here only process the first stream matching predicate
        callback_fun: function to call for each new sample. Well get as argument a tuplet (sample, timestamp, name, type, hostname, uid)
        pull_last: if True, only process last value, skipping everything that occurred since last call
        """
        sample = None
        new_sample = None
        new_timestamp = None
        streams = self._cr.results()
        if len(streams) > 0:
            # stream changed, retrieve new inlet
            if streams[0].uid() != self._uid:
                self._inlet = pylsl.StreamInlet(streams[0])
                self._uid = streams[0].uid()
                self._name = streams[0].name()
                self._type = streams[0].type()
                self._hostname = streams[0].hostname()
                self._srate = streams[0].nominal_srate()
                self._format = fmt2string(streams[0].channel_format())

            # fetch last value from stream
            try:
                sample, timestamp = self._inlet.pull_sample(timeout=0)
            except pylsl.LostError:
                # stream broke, but wait for resolver to remove it from list
                print("stream broke")
            while sample is not None:
                new_sample = sample
                new_timestamp = timestamp
                # depending on option, callback function for each past sample
                if not pull_last: 
                    callback_fun((new_sample, new_timestamp, self._name, self._type, self._hostname, self._uid, self._srate, self._format))

                try:
                    sample, timestamp = self._inlet.pull_sample(timeout=0)
                except pylsl.LostError:
                    pass

            # in case only the last sample of the stream is of interest
            if pull_last and new_sample is not None:
                callback_fun((new_sample, new_timestamp, self._name, self._type, self._hostname, self._uid, self._srate, self._format))

    def _multi_callmeback(self, callback_fun, pull_last=False):
        """
        Here we fetch data from all streams matching pred.
        pull_last: for each stream discard all samples but the last
        """
        self._updateStreams()

        new_sample = None
        new_timestamp = None
        # loop all current streams
        for k in self._streams:
            s = self._streams[k]
            inlet = s['inlet']
            try:
                sample, timestamp = inlet.pull_sample(timeout=0)
            except pylsl.LostError:
                # stream broke, but wait for resolver to remove it from list
                print("stream broke")

            while sample is not None:
                new_sample = sample
                new_timestamp = timestamp
                # depending on option, callback function for each past sample
                if not pull_last: 
                    print(s)
                    callback_fun((new_sample, new_timestamp, s['name'], s['type'], s['hostname'], k, s['srate'], s['format']))

                try:
                    sample, timestamp = inlet.pull_sample(timeout=0)
                except pylsl.LostError:
                    pass

            # in case only the last sample of the stream is of interest
            if pull_last and new_sample is not None:
                callback_fun((new_sample, new_timestamp, s['name'], s['type'], s['hostname'], k, s['srate'], s['format']))
    
    def callmeback(self, callback_fun, pull_last=False):
        """
        Run callback_fun for each sample of each captured stream. Compared to read() no value is returned, and each stream / sample is processed before return.
        WARNING: use either read() or callmeback(), a sample process in one won't appear in the other.
        pull_last: if True, will retrieve and process only the last sample (if any) of each captured stream.
        """
        if self._fetch_all:
            self._multi_callmeback(callback_fun, pull_last)
        else:
            self._simple_callmeback(callback_fun, pull_last)
