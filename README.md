# Trace Analyzer tool for generating quick csvs from model traces

### Usage 
 --first NameForFirstTrace IterationForFirstTrace Trace --second NameForSecondTrace IterationForSecondTrace Trace

### Variations
If the traces were ran with blocking you will need to run the tool with --no-blocking to stop our blocking time simulation.

If you do not have iterations on either format `iteration#` or `ProfilerStep##` set the iteration to trace to "None" note that this might be slow if you have a huge trace

ex:
`python3 trace_analyzer.py -f AMD 289 deepcrossnext_ob.json -s NVIDIA 969 trace_1000.json`

### Contributing
Please format with `black --line-length 90`
