# Trace Analyzer tool for generating quick csvs from model traces

### Usage 
 --first NameForFirstTrace IterationForFirstTrace Trace --second NameForSecondTrace IterationForSecondTrace Trace

ex:
`python3 trace_analyzer.py -f AMD 289 deepcrossnext_ob.json -s NVIDIA 969 trace_1000.json`

### Contributing
Please format with `black --line-length 90`