
Retrieve data *from* Labstreaminglayer and forward it *to* an (UDP) OSC server.

If you wish to do the opposite (get data from OSC and pipe it through LSL), have a look at https://github.com/gisogrimm/osc2lsl

As is, once connected to server, LSL data will be forwarded to addresses with format "/lsl_type/lsl_name".

Because it would not make sense anyway with OSC when controlling sound or visuals to get many samples in a row, here for each loop (roughly 100hz) we always get last sample from each stream. Hack that or prefer another approach if you need all values, as OSC in sot suited for that.

At the moment the resolver is set to a fixed 5 `forget_after`. The size of inlet's buffer is also yet to be configured.

Tested with python 3.8.10, on Ubuntu x64 20.04

# Troubleshooting

I experienced some issues with LSL ContinuousResolver with an empty predicate (probably because I've been playing with various versions of liblsl and pylsl). Workaround with `--pred "type=*"`.

# Dev

This repository uses git subrepo (https://github.com/ingydotnet/git-subrepo) to sync code (e.g. with the ContinuousReader wrapper).
