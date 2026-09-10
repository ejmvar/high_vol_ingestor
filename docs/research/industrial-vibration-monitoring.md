# Industrial Vibration Monitoring Research

Status: research baseline, not a production acceptance specification

Date: 2026-09-10

## Executive Summary

Industrial vibration monitoring is a measurement and evidence problem, not only
an ingestion problem. A useful system must preserve the relationship between
the asset, sensor installation, acquisition settings, signal-processing result,
alarm decision, and maintenance action.

There is no single industry-wide sampling interval or retention period. The
required rate depends on the highest frequency that carries diagnostic value,
the fault modes of the asset, sensor and mounting response, alarm latency, and
whether the system stores raw waveforms or derived condition indicators.

The recommended baseline is therefore layered:

- Acquire high-rate waveform bursts only when the diagnostic objective requires
  them.
- Compute low-volume indicators at the edge for continuous health visibility.
- Send event context and provenance with every derived result.
- Keep raw data longer for critical assets and shorter for routine assets, with
  the policy tied to maintenance lead time and replay requirements.

## Evidence Boundaries

The following statements are supported by the sources listed in the source
register:

- Vibration sensors are selected according to the measurement objective,
  frequency range, environment, and installation method.
- Mounting is part of the measurement chain. A poor or inconsistent mount can
  change the measured response and invalidate comparisons.
- Condition monitoring commonly uses time-domain and frequency-domain analysis;
  spectrum interpretation is meaningful only when acquisition metadata and
  machine operating state are retained.
- OpenTelemetry Collector is a vendor-neutral component for receiving,
  processing, and exporting telemetry. It is a suitable pipeline building block
  but does not define an industrial vibration schema or a retention policy.
- ISO 13373 and ISO 20816 are relevant standards families for condition
  monitoring and machine vibration evaluation. The exact applicable part,
  machine class, limits, and acceptance method require review of the licensed
  standard text for the target machinery.

The following are engineering proposals for a pilot and must not be described
as universal industry requirements:

- The acquisition tiers in this document.
- The initial waveform burst lengths and upload cadence.
- The storage and retention tiers.
- The first-pass mapping from signal features to maintenance workflow.

## Measurement Chain

```text
Machine -> sensor and mounting -> signal conditioning -> DAQ/edge device
        -> feature extraction and quality checks -> durable queue
        -> raw object storage / time-series store -> dashboard and maintenance action
```

Each sample or derived observation should remain attributable to:

- asset and component identity;
- sensor identity, axis, orientation, and mounting method;
- acquisition rate, anti-aliasing settings, gain, units, and calibration state;
- timestamp source and clock-quality status;
- operating state, speed, load, process context, and maintenance state;
- processing version, window, overlap, filters, and feature definition;
- sequence number, checksum, idempotency key, and lineage reference.

Without this context, a trend can be plotted but cannot be reliably compared,
replayed, or used to support a maintenance decision.

## Sensor and Instrumentation Choices

### Accelerometers

Accelerometers are the default choice for many rotating-equipment vibration
measurements because acceleration preserves high-frequency information useful for
impacting and bearing-related phenomena. The actual sensor must be selected for
the expected frequency band, amplitude, temperature, hazardous-area
requirements, cable length, and mounting arrangement.

Candidate interface families:

- IEPE/ICP sensors: suitable where the DAQ supplies sensor excitation and
  supports the required analog bandwidth.
- Voltage-output sensors: useful when the conditioning and noise budget are
  explicitly controlled.
- 4-20 mA vibration transmitters: useful for simple control-system integration
  and low-rate overall values, but generally insufficient as the only source
  for waveform or advanced fault diagnosis.
- MEMS accelerometers: useful for embedded, lower-cost, multi-axis monitoring;
  validate noise floor, bandwidth, temperature drift, and long-term stability
  against the diagnostic target.

### Installation

Use a repeatable, documented installation. Prefer a rigid stud mount when the
asset and maintenance procedure allow it. Magnetic or adhesive mounting can be
appropriate for surveys or constrained installations, but the method and its
limitations must be recorded because mounting changes the usable frequency
response.

The installation record should include location relative to bearings or other
transmission paths, axis direction, surface preparation, torque where relevant,
mounting adapter, cable routing, and photographs or an equivalent asset
reference.

### Complementary Signals

Vibration should be correlated with signals that disambiguate operating state:

- rotational speed or tachometer phase;
- motor current and power;
- temperature;
- pressure, flow, and valve state;
- load, recipe, batch, or production mode;
- maintenance and lubrication events.

These signals are not interchangeable with vibration. They provide the context
needed to separate a real mechanical change from a normal process change.

## Sampling and Time Windows

### What Must Be Sampled

The sampling frequency must be chosen from the highest frequency of interest,
not from the desired dashboard update rate. The Nyquist condition is a minimum
mathematical constraint; practical acquisition also requires an anti-aliasing
filter, transition-band margin, sensor bandwidth, and enough frequency
resolution to separate the features being compared.

The diagnostic design should specify, for each asset class:

- fault modes to detect;
- frequency bands and harmonics of interest;
- sensor and mounting response in those bands;
- sampling rate and anti-aliasing cutoff;
- waveform duration and window function;
- overlap and averaging policy;
- speed/load conditions required for comparison.

### Proposed Pilot Tiers

These values are starting points for a pilot, not universal requirements:

| Tier | Payload | Initial proposal | Purpose |
| --- | --- | --- | --- |
| Continuous health | RMS, peak, crest factor, temperature, quality flags | 1-10 Hz feature updates | Low-bandwidth trend and alarm visibility |
| Scheduled waveform | Time waveform plus metadata | 1-10 second burst every 1-10 minutes for critical assets | Spectrum, trend confirmation, and replay |
| Event waveform | High-rate pre/post-trigger burst | Triggered by threshold, process event, or feature change | Capture transient evidence without continuous raw upload |
| Survey/reference | Full measurement set | Technician or commissioning schedule | Baseline creation and sensor/installation validation |

The high-rate tier must be set per asset after the frequency bands are known.
For example, a slow pump and a gearbox with bearing-impact diagnostics should
not inherit the same rate merely because they use the same gateway.

### Windowing and Resolution

Frequency resolution is approximately the inverse of the waveform duration
before accounting for window effects. Longer windows improve resolution but
reduce responsiveness and increase payload size. The system should preserve the
window type, duration, overlap, and averaging count so that a later analysis can
reproduce the result.

For variable-speed machinery, order tracking or speed-conditioned analysis may
be more appropriate than comparing fixed-frequency bins. This is a design
requirement to validate during the pilot, not an assumption to hide in a generic
FFT service.

## Failure Modes and Features

The following mapping is a diagnostic hypothesis to validate with asset history
and expert review:

| Failure hypothesis | Useful evidence | Required context |
| --- | --- | --- |
| Imbalance | Dominant running-speed component and rising overall vibration | Speed, operating load, phase if available |
| Misalignment | Running-speed harmonics, axial/radial relationship, coupling context | Sensor axes and coupling/shaft arrangement |
| Mechanical looseness | Harmonics, impacting, changing waveform shape | Mounting condition, load, maintenance history |
| Bearing degradation | High-frequency energy, envelope-related features, impulsive waveform changes | Bearing geometry, shaft speed, sensor path, lubrication events |
| Gear damage | Gear-mesh-related components and sidebands | Tooth count, speed, gearbox ratio, load |
| Resonance or structural response | Narrow-band amplification and strong operating-state dependence | Speed sweep, structure, sensor mounting, process state |

No single feature should automatically create a work order. A robust decision
combines feature trend, confidence/quality flags, operating context, persistence,
and maintenance history. The initial system should support a human-reviewed
classification loop and preserve the evidence used for that decision.

## Data Pipeline and Storage

### Edge Processing

The edge device should perform only deterministic, versioned operations that
reduce bandwidth without destroying evidence:

- validate sensor health and signal range;
- apply documented filtering and anti-aliasing;
- calculate agreed features;
- trigger and retain waveform evidence around events;
- assign sequence numbers and checksums;
- buffer during network outages;
- publish health and processing metrics.

### Durable Ingestion

The durable queue is the acceptance boundary for telemetry. A producer
acknowledgement should mean that the configured queue acceptance condition has
been met, not merely that an in-memory process received the message. Consumers
must be idempotent and replayable.

Recommended payload separation:

- raw waveforms and immutable evidence in object storage;
- feature observations and alarms in a time-series or analytical store;
- asset, sensor, calibration, and maintenance metadata in a relational store;
- lineage linking every feature and alarm back to its source waveform or an
  explicit reason that no waveform exists.

OpenTelemetry Collector can be used for platform telemetry such as ingestion
health, queue lag, processing latency, dropped records, and exporter failures.
It should not be treated as the canonical store for raw vibration waveforms.

### Dashboard Requirements

The operator view should show more than a single red/green status:

- asset hierarchy and current operating state;
- latest feature values with quality and staleness indicators;
- trends with maintenance annotations;
- spectrum and waveform drill-down for the same observation;
- alarm threshold, persistence, and evidence links;
- sensor installation and calibration details;
- queue freshness and pipeline health;
- acknowledgement, review, and work-order state.

The dashboard must make stale data visible. A healthy-looking last value with a
failed gateway is a dangerous false positive.

## Retention Proposal

Retention should be policy-driven by asset criticality, diagnostic replay needs,
regulatory or contractual requirements, and storage cost. It should not be
chosen as one global number.

Initial proposal for review:

| Data class | Suggested starting retention | Rationale |
| --- | --- | --- |
| Continuous scalar features | 13-25 months | Compare seasonal operation and at least one maintenance cycle |
| Alarm and decision records | Life of the asset or policy-defined longer period | Preserve decision and action lineage |
| Event waveform bursts | 3-13 months online, archive critical events | Support investigation and model review |
| Commissioning and baseline waveforms | Life of the asset while the installation remains comparable | Reference for drift and sensor replacement |
| Raw non-event waveforms | Short rolling window, such as 7-30 days | Bound cost while retaining recent replay capability |
| Pipeline and quality telemetry | 3-13 months | Investigate missingness, latency, and false health states |

These durations are proposals, not sourced industry mandates. Before adoption,
the owner should define the maximum expected failure-development lead time,
maintenance interval, legal hold requirements, and replay scope. Retention,
versioning, checksums, and access control must be tested in the chosen storage
service; local object storage should not be called legally immutable without
validated object-lock, versioning, retention, and policy behavior.

## Pilot Acceptance Questions

The pilot should answer these questions with measured evidence:

1. Can the installation reproduce a baseline under the same speed and load?
2. Does the chosen sensor and mount cover the intended diagnostic bands?
3. Can an outage recover without duplicate or silently missing observations?
4. Can a feature or alarm be replayed from retained evidence?
5. Can operators distinguish stale telemetry from a healthy asset?
6. Do maintenance events explain observed feature changes?
7. Which waveform classes actually change a maintenance decision?
8. Are the proposed retention tiers sufficient for the longest review cycle?

## Source Register

Accessed 2026-09-10. URLs are recorded for verification; standards require
review of the applicable official text rather than relying on summaries.

| Source | Relevance | Evidence use |
| --- | --- | --- |
| NI, Condition Monitoring overview: https://www.ni.com/docs/en-US/bundle/ni-condition-monitoring/page/overview.html | Condition-monitoring concepts and measurement workflow | Supports the distinction between acquisition, analysis, and condition decisions |
| NI, Vibration sensors: https://www.ni.com/docs/en-US/bundle/ni-condition-monitoring/page/vibration-sensors.html | Sensor selection and vibration measurement context | Supports sensor choice being dependent on application and bandwidth |
| PCB Piezotronics, Sensor mounting technical information: https://www.pcb.com/resources/technical-information/sensor-mounting | Mounting methods and measurement response | Supports treating mounting as part of the measurement chain |
| OpenTelemetry, Collector documentation: https://opentelemetry.io/docs/collector/ | Receive, process, and export telemetry | Supports using the Collector for platform telemetry, not as waveform retention |
| ISO catalogue search for ISO 13373: https://www.iso.org/search.html?q=ISO%2013373 | Vibration condition-monitoring standards family | Identifies the standards family requiring machine-specific review |
| ISO catalogue search for ISO 20816: https://www.iso.org/search.html?q=ISO%2020816 | Machine vibration evaluation standards family | Identifies the standards family requiring machine-class review |

## Open Gaps

- Obtain and review the exact applicable ISO parts for each target machine class.
- Validate the pilot rates against sensor bandwidth, DAQ anti-aliasing, and
  bearing/gear diagnostic objectives.
- Obtain real failure and maintenance history before training or automating
  failure classification.
- Define the authoritative asset and sensor identity model.
- Define queue acceptance, outage buffering, replay, and duplicate-handling
  tests in the repository's verification scripts.
