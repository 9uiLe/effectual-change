# Fictional exhibit updater facts
The target kiosk uses flash storage and a catalog viewer that opens its active catalog at startup and on a publication notification. The viewer can resolve all images from an immutable catalog directory. Its handling of a notification while restarting has not been tested.

## Current direction: in-place entries
A development tmpfs probe replaced 2,000 caption records in 1.8 s. Images were not part of that probe. Entries become readable one by one. There is no update journal or rollback. A power interruption can stop between replacing an image and replacing its caption.

## Immutable generation publisher
The supplied interface can stage captions and image files in a new generation directory, check all referenced files, then publish one active-generation pointer. Readers retain the previous immutable generation until the new pointer is opened. Documentation requires flushing staged file contents and the containing directory before flushing publication metadata. Rename by itself is not a documented guarantee of persistence through power loss. Recovery selects the last valid committed generation; this recovery path has only been inspected as source, not executed on the target.

## Evidence and access
Only the tmpfs probe is measured. No complete image-and-caption update timing, restart race, flush ordering or power-loss recovery result exists. Old generation cleanup happens after a successful reopen and is not time-critical. A target kiosk and controlled power interrupter can be booked for a later experiment.
