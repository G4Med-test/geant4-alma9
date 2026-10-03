#!/usr/bin/env python3
"""Find every new Geant4 tag, resolving annotated tags to source commits."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

UPSTREAM = "https://github.com/Geant4/geant4.git"
TAG = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+(?:[.-][A-Za-z0-9][A-Za-z0-9.-]*)?\Z")


def parse_refs(text):
    refs, peeled = {}, {}
    for line in text.splitlines():
        sha, ref = line.split()
        if not ref.startswith("refs/tags/"):
            continue
        name = ref[len("refs/tags/"):]
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("Invalid Git object ID")
        if name.endswith("^{}"):
            peeled[name[:-3]] = sha
        else:
            refs[name] = sha
    refs.update(peeled)
    if not refs:
        raise ValueError("Upstream returned no tags; refusing an empty snapshot")
    return refs


def plan(upstream, baseline, published, requested=""):
    for tag, sha in upstream.items():
        previous = published.get(tag, baseline.get(tag))
        if previous and previous != sha:
            raise ValueError("Upstream tag moved; manual review required: " + tag)
    if requested and requested not in upstream:
        raise ValueError("Unknown upstream tag: " + requested)
    candidates = [requested] if requested else sorted(set(upstream) - set(baseline))
    jobs = []
    for tag in candidates:
        if tag in published:
            continue
        if not TAG.fullmatch(tag) or len(tag) > 120:
            raise ValueError("Unsupported tag/image name: " + tag)
        jobs.append({"tag": tag, "commit": upstream[tag], "image_tag": tag[1:]})
    # Limit each batch without dropping the rest: successful tags are the only checkpoint.
    return jobs[:16]


def published_tags():
    result = {}
    tags = subprocess.check_output(["git", "tag", "--list", "v*"], text=True).splitlines()
    for tag in tags:
        message = subprocess.check_output(
            ["git", "for-each-ref", "--format=%(contents)", "refs/tags/" + tag], text=True)
        try:
            record = json.loads(message)
            result[tag] = record["geant4_commit"]
        except (ValueError, KeyError) as error:
            raise ValueError("Release tag lacks build provenance: " + tag) from error
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--tag", default="", help="Build a specific upstream tag, including historic versions")
    args = cli.parse_args()
    baseline = json.loads(Path("upstream-baseline.json").read_text())
    if baseline["upstream"] != UPSTREAM:
        raise ValueError("Unexpected upstream repository")
    refs = subprocess.check_output(["git", "ls-remote", "--tags", UPSTREAM], text=True)
    jobs = plan(parse_refs(refs), baseline["tags"], published_tags(), args.tag)
    matrix = json.dumps({"include": jobs}, separators=(",", ":"))
    print(matrix)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
            stream.write("matrix=" + matrix + "\n")
            stream.write("count=" + str(len(jobs)) + "\n")


if __name__ == "__main__":
    main()
