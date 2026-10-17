# Fictional receipt system facts
All timings below are observations under the stated conditions, not forecasts for another environment.

## RapidParse
Median 6 ms per receipt on 25 cached, clean samples. Its output can use the existing single-item uploader. That uploader serially takes about 0.8 s per item in the review-service staging environment, excluding parsing and retries. The current RapidParse output does not match the group-session uploader contract. A translator could be written; correctness, duplicate handling and performance have not been tested.

## CarefulParse
Median 14 ms per receipt on the same 25 cached samples. Native output matches the group-session uploader. The uploader publishes groups of at most 100 results and supports a caller-provided stable receipt key for deduplication. In a ten-item staging probe, one group became visible in 3 s. Correct original-file linkage was manually checked for those ten only.

## Shared constraints
Both parsers omit a quality flag on some blurred images; the downstream policy for those results is unresolved. The target batch includes clean and blurred images. The acceptance timer ends only when every result and link is visible in the review service. Folder detection, parsing, transformation, upload, retries and downstream visibility are all inside that timer. Target staging access and a mixed 500-receipt fixture are available for a later experiment. No production claims follow from this packet.
