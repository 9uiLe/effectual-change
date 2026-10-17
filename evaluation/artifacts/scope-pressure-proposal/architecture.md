# Fictional Fieldkit architecture and evidence

Fieldkit helps an AI developer carry a stated product goal through technical exploration, implementation and acceptance. A user gives one request; the main agent chooses the required tools. Fieldkit's common layer keeps the intent, decisions and links to the evidence. It runs on Python 3.11 or later with the standard library, on macOS and Linux. Ordinary commands must remain usable without a mobile SDK, a browser driver or an external service.

Project-specific commands already run through the host agent. Their owners select and maintain their build, deployment and measurement tools. Fieldkit can retain a small selected output with its observation record. Neither this mechanism nor a successful command proves the product outcome.

Two project maintainers supplied small CSV exports with numeric values. A third project uses a recorder's binary bundle. They describe similar frustration finding comparable measurements, but nobody has observed Fieldkit handling a complete real measurement task. There are no measured savings, reliability results or measured adoption figures.

A standard-library operation that groups selected CSV values could be small and shareable. Its accepted input, grouping, missing-data policy and comparison conditions still need agreement. Existing command output is also enough for a project-owned summarizer; this would require that project to maintain its own command and output contract.

Automating recorders and reading their binary output requires platform tools, version-specific exporters, target permissions and cleanup. An optional integration could isolate those dependencies but adds installation, discovery and version compatibility work. Putting all these responsibilities into normal startup would violate the stated availability constraint. Lazy loading could avoid that particular conflict, but would not remove the maintenance cost.

The budget for the next change is one developer day, including checking the result. The roadmap can be changed by the responsible user; no particular extension placement has been settled. No recorder or binary-parser implementation exists in this fixture.
