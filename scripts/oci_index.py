#!/usr/bin/env python3
"""Combine the per-architecture SIF manifests into one multi-arch OCI index."""
import argparse
import hashlib
import json
from pathlib import Path

INDEX = "application/vnd.oci.image.index.v1+json"
MANIFEST = "application/vnd.oci.image.manifest.v1+json"
SIF_LAYER = "application/vnd.sylabs.sif.layer.v1.sif"
ARCHES = ("amd64", "arm64")


def descriptor(arch, manifest, provenance, tag):
    """Descriptor for a pushed per-arch manifest, checked against its build record."""
    if arch not in ARCHES or provenance.get("arch") != arch:
        raise ValueError("Unexpected architecture: " + arch)
    if provenance.get("geant4_tag") != tag:
        raise ValueError(f"{arch} provenance is for {provenance.get('geant4_tag')}, not {tag}")
    content = json.loads(manifest)
    if content.get("mediaType") != MANIFEST:
        raise ValueError(f"{arch} manifest is not an OCI image manifest")
    layers = content.get("layers", [])
    # The SIF layer digest is the file's SHA-256: the tag must hold this run's SIF.
    if [layer.get("mediaType") for layer in layers] != [SIF_LAYER] \
            or layers[0].get("digest") != "sha256:" + provenance["sif_sha256"]:
        raise ValueError(f"{arch} manifest does not hold the SIF built by this run")
    return {"mediaType": MANIFEST, "digest": "sha256:" + hashlib.sha256(manifest).hexdigest(),
            "size": len(manifest), "platform": {"architecture": arch, "os": "linux"}}


def index(entries, tag, annotations):
    """entries: (arch, manifest bytes, provenance dict) for every published architecture."""
    if sorted(arch for arch, _, _ in entries) != sorted(ARCHES):
        raise ValueError("The index needs exactly one manifest per architecture: " + ", ".join(ARCHES))
    if len({provenance["geant4_commit"] for _, _, provenance in entries}) != 1:
        raise ValueError("Architectures were built from different Geant4 commits")
    manifests = [descriptor(arch, manifest, provenance, tag)
                 for arch, manifest, provenance in sorted(entries)]
    return {"schemaVersion": 2, "mediaType": INDEX, "manifests": manifests,
            "annotations": dict(sorted(annotations.items()))}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--tag", required=True)
    cli.add_argument("--entry", nargs=3, action="append", required=True,
                     metavar=("ARCH", "MANIFEST", "PROVENANCE"))
    cli.add_argument("--annotation", action="append", default=[], metavar="KEY=VALUE")
    cli.add_argument("--output", required=True)
    args = cli.parse_args()
    entries = [(arch, Path(manifest).read_bytes(), json.loads(Path(provenance).read_text()))
               for arch, manifest, provenance in args.entry]
    annotations = dict(item.split("=", 1) for item in args.annotation)
    Path(args.output).write_text(json.dumps(index(entries, args.tag, annotations), indent=2) + "\n")


if __name__ == "__main__":
    main()
