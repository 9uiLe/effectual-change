# Fictional Fieldkit summary command

The shared CLI is `python3 fieldkit.py`. Add `summarize INPUT` alongside the existing `status` command. Use Python 3.11 or later and the standard library only. The user has approved this small common operation. Reading this design does not authorize running recorders, adding formats or transmitting data.

`INPUT` is the one CSV file explicitly selected by the caller. Its header is exactly `metric,unit,value`, in that order. There must be at least one data row. Each row must have exactly three fields, nonempty metric and unit, and a value parseable as a finite number. Negative values are allowed. Empty or malformed rows, duplicate or extra columns, missing files, invalid text and non-finite values fail the whole operation. Do not skip invalid rows or print a successful partial summary.

Group rows by `(metric, unit)` and print one JSON array, ordered lexicographically by metric then unit. Each element has exactly `metric`, `unit`, `count` and `mean`; count is an integer and mean is a finite JSON number. No particular indentation is required. A sum or mean that cannot be represented as a finite number is an input error. Summary success exits 0. Input errors exit 2, print a concise diagnostic to stderr, print nothing to stdout and expose no traceback. The input file is never changed.

The supplied file produces the following numeric result (insignificant number formatting may differ):

```json
[
  {"metric":"latency","unit":"ms","count":3,"mean":20.0},
  {"metric":"payload","unit":"bytes","count":2,"mean":150.0}
]
```

`python3 fieldkit.py status` continues to print the JSON object `{"ready": true}` and exit 0. The program writes no files. This is arithmetic over explicit values, with no claim that the numbers came from a real measurement or establish a performance regression.
