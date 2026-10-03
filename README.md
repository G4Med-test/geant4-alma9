# Geant4 AlmaLinux 9 for G4Med

One base image for the LowEFrag, CCCStest and Attenuation-ilantest Apptainer
containers: `ghcr.io/g4med-test/geant4-alma9:<Geant4 version>`.
The first automated build is `11.3.2`, matching the current validation pipeline.
The published architecture is `linux/amd64`, for the Padova runners.

## Contents and size choices

- AlmaLinux 9, GCC/G++, Make and CMake, retained because Apptainer `%post` builds
  each validation executable.
- Geant4 installed in `/opt/geant4`, with multithreading and its built-in ROOT
  file writer. ROOT/PyROOT is **not** installed or needed to write ROOT histograms.
- Python 3.12, NumPy and uproot in `/opt/venv`, available as `python3` on PATH.
  `requirements.txt` pins the direct analysis dependencies.
- No Qt, OpenGL/X11, GDML/Xerces, Geant4 examples or physics datasets: the three
  batch tests do not need those build options. Build sources and objects stay in
  a separate Docker stage and installed Geant4 binaries are stripped.

Mount the Geant4 datasets at `/g4data` (for example from CVMFS). Both
`GEANT4_DATA_DIR` and the existing `G4DATA_DIR` convention point there. The common
image intentionally includes development tools, so it can also build the derived
test containers. It is not a runtime-only image.

## Automatic upstream tags

The action checks **all** tags of `https://github.com/Geant4/geant4.git` hourly
at minute 17 UTC. It handles lightweight/annotated tags, maintenance releases and
beta tags; it does not just compare the numerically newest release.

For every new tag (e.g. `v11.4.4`), it resolves the source commit, builds and tests
the image, publishes `ghcr.io/g4med-test/geant4-alma9:11.4.4`, and then creates an
annotated Git tag `v11.4.4` in this repository. The annotation records the upstream
commit, this repository's recipe commit and the published image digest. Failed
builds do not create a tag and are retried on the next scheduled run. Previously
published versions are not silently overwritten. Moved upstream tags fail for
manual review.

`upstream-baseline.json` records historic tags already present when this repository
was created. Those are not automatically rebuilt; `v11.3.2` is deliberately absent
to bootstrap the version used by the current tests. All subsequently added tags
are detected. A batch processes at most 16 pending tags; further tags remain
pending for subsequent runs.

GitHub does not send another repository's tag events directly to this workflow.
Polling is the self-contained mechanism; schedules can be delayed by GitHub.
For an immediate build, run the workflow manually with `geant4_tag`, or have an
external/upstream integration send a `repository_dispatch` event of type
`geant4-tag-created` with `client_payload: {"tag": "v11.4.4"}`. A webhook bridge
is not configured by this repository. GitHub may disable schedules on inactive
public repositories; check the workflow is enabled if it has been idle for 60 days.

Build, push and tag creation run in the same workflow with `GITHUB_TOKEN` and
`contents: write` / `packages: write`. No Docker Hub credentials or trigger PAT
are required. A tag created with `GITHUB_TOKEN` does not need to trigger a second
workflow. The concurrency lock prevents overlapping publication runs.

To build an older version explicitly:

```bash
gh workflow run build.yml -R G4Med-test/geant4-alma9 -f geant4_tag=v11.4.3
```

## GHCR access and Apptainer

GHCR packages initially default to private. After the first publication, make the
`geant4-alma9` package public in its settings for anonymous pulls by the three
test repositories, or grant those repositories read access under the package's
Actions access settings and authenticate their pulls.

The derived definition uses the **Docker/OCI** bootstrap (the base is not a SIF
artifact stored via ORAS):

```text
Bootstrap: docker
From: ghcr.io/g4med-test/geant4-alma9:{{ TAG }}

%arguments
    TAG=11.3.2
```

The base image exports `PATH`, `CMAKE_PREFIX_PATH` and library paths for
`/opt/geant4`; preserve those settings in the derived image. Build and run:

```bash
apptainer build --build-arg TAG=11.3.2 LowEFrag.sif Apptainer.def
apptainer run -B /cvmfs/geant4.cern.ch/share/data:/g4data:ro LowEFrag.sif macro/bic.mac
```

Production parsing uses uproot in the container. `ci-workflows/validation/export.py`
and each caller's `validation/parser.py` remain versioned in their own repositories;
the base supplies their dependencies without duplicating the scripts. Example
with the repositories checked out side by side and a raw output directory:

```bash
docker run --rm -v "$PWD:/work" -w /work \
  ghcr.io/g4med-test/geant4-alma9:11.3.2 \
  python3 ci-workflows/validation/export.py export \
    --repo LowEFrag --macro bic.mac --input raw-output \
    --version 11.3.2 --output json-output
```

This produces `json-output/results.json` and `json-output/plots/*.json`. The
`--version` must match the image and raw simulation; the integrated workflow reads
it using `geant4-config --version` inside the test image.

## Validation and local builds

Before publication the workflow tests Python/weighted ROOT I/O without PyROOT,
checks the tools and empty dataset directory, and compiles all three applications
at the explicit revisions in `build.yml`. This checks build compatibility, not
experimental agreement. Simulation runs and JSON regressions belong to the caller
pipeline.

```bash
python3 -m unittest discover -s tests -v
docker build -t geant4-alma9:local --build-arg BUILD_JOBS=4 .
docker run --rm -v "$PWD:/checks:ro" geant4-alma9:local python3 /checks/scripts/smoke_test.py
```

When building a different version locally, set **both** `GEANT4_TAG` and
`GEANT4_COMMIT` to the matching upstream tag and peeled commit. The workflow resolves
these automatically. It downloads the exact source commit, not a mutable branch.
For repeatable deployments consume the published digest recorded in the Git tag;
OS package updates can change the bytes of a later rebuild of the same recipe.

## Origin

Inspired by [carlomt/docker-geant4/almalinux9](https://github.com/carlomt/docker-geant4/tree/0f7a2b00e70b6f647596d686b9d509e31392d71d/almalinux9).
The multi-stage structure and external dataset layout are retained; the image is
specialized for the three G4Med tests and publishes only to GHCR. Geant4 remains
subject to its [software license](https://github.com/Geant4/geant4/blob/master/LICENSE).
