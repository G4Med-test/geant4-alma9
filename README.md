# Geant4 AlmaLinux 9 — Apptainer base for G4Med

One SIF base image for LowEFrag, CCCStest and Attenuation-ilantest, published on
GHCR with the **exact upstream Geant4 tag**, including `v`:

```bash
apptainer pull geant4-alma9.sif oras://ghcr.io/g4med-test/geant4-alma9:v11.3.2
apptainer exec geant4-alma9.sif geant4-config --version
```

The published architecture is `linux/amd64`, for the Padova runners. Geant4
`v11.3.2` is the initial version, matching the existing tests.

## Contents

AlmaLinux 9, GCC/G++, Make, CMake, Geant4 multithread in `/opt/geant4`, and Python
3.12 with NumPy/uproot in `/opt/venv`. Development tools remain because the derived
Apptainer images compile their own test programs. Geant4's built-in ROOT writer
and uproot do not require ROOT/PyROOT, which is absent. Qt/OpenGL, GDML/Xerces,
examples, source/build trees and physics datasets are omitted. Datasets are
mounted at `/g4data`; `GEANT4_DATA_DIR` and `G4DATA_DIR` point there.

The complete build uses **Apptainer**, starting with `Apptainer.def` and
`Bootstrap: dnf`. AlmaLinux 9 is installed directly from its RPM repositories;
Geant4 and Python dependencies are installed in `%post`, and source trees and
caches are removed before SIF compression. No Dockerfile, Docker daemon, Buildx,
OCI base image or intermediate Docker image is used. Publication uses Apptainer
ORAS. The legacy OCI artifact `:11.3.2` remains available; SIF tags retain the
upstream spelling `:v11.3.2`, etc.

## One version source: the Git tag

There is no separately maintained Geant4 version in the build configuration.
For `v11.4.4` the workflow:

1. Resolves `Geant4/geant4`'s `v11.4.4` to its source commit, including annotated
   tag dereferencing.
2. Creates a same-name `v11.4.4` tag in this repository, recording the Geant4 source
   commit and recipe commit. Existing Git tags are never moved.
3. Uses the recipe at the workflow's exact Git revision and builds the SIF
   directly with Apptainer. The source tag is also passed to the image labels.
4. Checks Python and weighted ROOT I/O without PyROOT and compiles all three tests
   inside the SIF at the source revisions pinned in the workflow.
5. Pushes `oras://ghcr.io/g4med-test/geant4-alma9:v11.4.4`, pulls it back, and compares
   the SIF bytes. An Actions artifact records source/recipe/workflow commits and
   the SIF SHA-256.

The initial `v11.3.2` Git tag predates the native Apptainer recipe and retains its
original commit. An explicit rebuild can use the current recipe without moving
the Git tag or changing the Geant4 source commit. The provenance artifact records
the actual recipe revision used for each build, including retries and rebuilds.

A Git tag alone is **not** a successful build marker: the scheduled job checks
GHCR for the exact tag. A tagged version without a published SIF is retried,
including historic versions selected manually. Authentication/network errors are
reported; only a package-not-found response is treated as a first publication.
Moved upstream tags fail for manual review. Automatic runs skip published SIF
tags. Replacement requires a manual dispatch with both `geant4_tag` and
`rebuild=true`; this is also how the initial SIF is migrated to the native
Apptainer recipe. Publication uses a concurrency lock.

## Triggers

The workflow polls **all** tags in `https://github.com/Geant4/geant4.git` hourly
at minute 17 UTC, including maintenance releases and beta tags. GitHub does not
send another repository's tag events directly to this workflow; schedules may
be delayed. New local `v*` tag pushes, manual dispatch and `repository_dispatch`
(`geant4-tag-created`, payload `{"tag":"v11.4.4"}`) are also supported.

`upstream-baseline.json` lists historic tags present at setup; these do not cause
mass rebuilds. `v11.3.2` was excluded to bootstrap the current test version. New
upstream tags and unpublished local version tags are always candidates. Batches
are limited to 16; further tags remain pending.

```bash
gh workflow run build.yml -R G4Med-test/geant4-alma9 -f geant4_tag=v11.4.3
```

To rebuild an existing image from the recipe on `main`:

```bash
gh workflow run build.yml -R G4Med-test/geant4-alma9 --ref main \
  -f geant4_tag=v11.3.2 -f rebuild=true
```

Git tag creation and the build run in the same workflow, avoiding the restriction
that tags pushed with `GITHUB_TOKEN` do not trigger another workflow. Only the
built-in token is required (`contents: write`, `packages: read/write`), not a PAT.
GitHub can disable schedules on public repositories after 60 days without activity;
check the workflow remains enabled if the repository is idle.

## Derived test images

The test definitions use the documented
[`oras` bootstrap agent](https://apptainer.org/docs/user/1.3/appendix.html#oras-bootstrap-agent):

```text
Bootstrap: oras
From: ghcr.io/g4med-test/geant4-alma9:{{ TAG }}

%arguments
    TAG=v11.3.2
```

```bash
apptainer build --build-arg TAG=v11.3.2 LowEFrag.sif Apptainer.def
apptainer run -B /cvmfs/geant4.cern.ch/share/data:/g4data:ro LowEFrag.sif macro/bic.mac
```

This package supports anonymous pulls (verified for `v11.3.2`). If deploying a
private copy, grant the test repositories read access under its Actions access
settings and authenticate before building. Retain the base's `/opt/geant4` and
`/opt/venv` PATH/library settings in derived images.

The parsers remain in each test repository, and the common exporter remains in
`ci-workflows`. The SIF supplies dependencies and executes the exporter inside
Apptainer, producing `results.json` and `plots/*.json` without runtime pip installs.
With repositories checked out side by side:

```bash
apptainer exec --bind "$PWD:/work" --pwd /work geant4-alma9.sif \
  python3 ci-workflows/validation/export.py export \
    --repo LowEFrag --macro bic.mac --input raw-output \
    --version 11.3.2 --output json-output
```

The JSON `mctool.version` is the actual value of `geant4-config --version`, e.g.
`11.3.2`; the Git/registry tag retains `v11.3.2`. The integrated pipeline reads
that runtime version from the image automatically.

## Verification and origin

Run `python3 -m unittest discover -s tests -v` for tag planning/retry tests. The
workflow checks the actual SIF and builds the three applications before pushing.
It does not replace full simulations or experimental validation on Padova.

Build locally on Linux with Apptainer, DNF and RPM installed. The GitHub runner
installs these directly on Ubuntu, without a job container. On Ubuntu/Debian,
configure root's RPM database path before the bootstrap, as required by Apptainer:

```bash
printf '%s\n' '%_var /var' '%_dbpath %{_var}/lib/rpm' | sudo tee /root/.rpmmacros
```

Pass the desired tag and the corresponding **peeled source commit** (not an
annotated tag object) as build arguments. Neither has a hardcoded default:

```bash
sudo apptainer build \
  --build-arg GEANT4_TAG=v11.3.2 \
  --build-arg GEANT4_COMMIT=62f62ecae238a7c304c52af4affbe70795475590 \
  --build-arg SOURCE_REVISION="$(git rev-parse HEAD)" \
  --build-arg BUILD_JOBS=4 \
  geant4-alma9.sif Apptainer.def
```

The workflow resolves the source commit automatically from the tag.
See Apptainer's [`dnf` bootstrap documentation](https://apptainer.org/docs/user/latest/appendix.html#yum-or-dnf-bootstrap-agent).

Inspired by [carlomt/docker-geant4/almalinux9](https://github.com/carlomt/docker-geant4/tree/0f7a2b00e70b6f647596d686b9d509e31392d71d/almalinux9).
Geant4 remains subject to its [license](https://github.com/Geant4/geant4/blob/master/LICENSE).
