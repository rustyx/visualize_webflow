# visualize_webflow

### - Spring WebFlow visualization utility

This script processes spring webflow configuration (flow.xml files) and makes a graph of the flow states using graphviz dot utility.

**Note - [graphviz](http://www.graphviz.org/Download.php)** must be available on the system PATH.

```
usage: visualize_webflow.py [-h] [-d] [-s] [--skip-flows SKIPFLOWS]
                            [--skip-states SKIPSTATES]
                            [--split-states SPLITSTATES]
                            [--merge-states-min-inputs MERGEMINTOTAL]
                            [--merge-states-min-common-inputs MERGEMINCOMMON]
                            [--merge-states-max-diff-inputs MERGEMAXDIFF]
                            [--hide-conditions]
                            [--flow-id-path-steps FLOW_ID_PATH_STEPS]
                            [-o OUTPUT] [-v]
                            input

positional arguments:
  input                 the path to <webflow-servlet.xml> or <flow.xml>

optional arguments:
  -h, --help            show this help message and exit
  -d, --dot             invoke DOT to generate a PDF for each flow (requires
                        -o or -s)
  -s, --split           split output by subflow
  --skip-flows SKIPFLOWS
                        comma-separated list of subflows to skip
  --skip-states SKIPSTATES
                        comma-separated list of states to skip
  --split-states SPLITSTATES
                        comma-separated list of states to split (for
                        frequently used states)
  --merge-states-min-inputs MERGEMINTOTAL
                        auto-merge states with at least this many inputs
                        (default 5)
  --merge-states-min-common-inputs MERGEMINCOMMON
                        auto-merge states with at least this many common
                        inputs (default 3)
  --merge-states-max-diff-inputs MERGEMAXDIFF
                        auto-merge states with at most this many different
                        inputs (default 7)
  --hide-conditions     hide decision state conditions
  --flow-id-path-steps FLOW_ID_PATH_STEPS
                        how many steps in the flow.xml path to use as flow ID
                        (default 1)
  -o OUTPUT, --output OUTPUT
                        output DOT file name (ignored if -s is specified)
  -v, --verbose         be verbose
```

### Example output

![example output](https://raw.githubusercontent.com/rustyx/visualize_webflow/samples/booking-portlet-mvc.gif)
