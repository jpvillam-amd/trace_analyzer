# Trace Analyzer tool for generating quick csvs from model traces

This tool currenttly requires two json files. If you are only looking for analysis on just one, submit it for both parameters until I fix this dependancy. 

## Usage 
 --first NameForFirstTrace IterationForFirstTrace Trace --second NameForSecondTrace IterationForSecondTrace Trace

 NOTE: For now this requires the rpd2tracing.py in this directory with the `--format object` parameter 

 
If you do not have iterations on either format `iteration#` or `ProfilerStep##` set the iteration to trace to "None" note that this might be slow if you have a huge trace

ex:
`python3 trace_analyzer.py -f AMD 289 deepcrossnext_ob.json -s NVIDIA 969 trace_1000.json`

## Options
Currently, by default, the tool will gather the time for all kernels and ops and display then as a table while trying to match them between the two runs.

Additionally there are four other supported "analysis" or options

"--blocking"
"--variations"
"--calculate-elementwise-eff"
"--kernel-stats"

### Blocking
This simply aggregations kernel times back up to the operations responsible for them 

### Variations
Creates a map of all operations and their possible "Variations". Variations in this contexts means different subsequent calls for the same operation. 

For instance if the aten.mm operations sometimes calls kernelA and sometimes calls kernelB then that is two variations.

### Calculate Elementwise efficiency 
Calculates the bandwidth efficiency of elementwise kernel assuming they are not compute bond.

NOTE: Not all Elementwise kernels are implemented.

### Kernel Stats
Creates a table with the total amount of time spent in library kernels vs elementwise kernels. 



### Contributing
Please format with `black --line-length 90`
