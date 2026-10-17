# Fictional lab components
These are complete supplied facts, not descriptions of real libraries.

## ArrivalTap
Watches the lab account notification stream, records item id and requested setting, and emits a local event. It does not click controls or change saved settings.

## PanelSight
Captures panel screenshots, identifies displayed controls and reads the saved-state summary. It never synthesizes input. A demonstration connected ArrivalTap to PanelSight and correctly described ten requested settings; no setting was changed.

## PanelHands
Can focus the panel, set a control and press Save from a local event. It provides an input-delivery log, not saved-state verification. Requires the dedicated account's accessibility permission and an unlocked desktop. Permission has not yet been granted in the target account.

## Lab rules
The saved-state summary is the authoritative observable result. A delivered click or a plausible screenshot description alone does not prove that Save persisted. A repeat event must not double-apply a change. A deliberately disabled Save button is available as a negative control. No run artifacts from the target workstation are supplied.
