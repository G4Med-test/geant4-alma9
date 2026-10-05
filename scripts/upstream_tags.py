#!/usr/bin/env python3
"""Find every new Geant4 tag, resolving annotated tags to source commits."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.error
import urllib.request

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


def plan(upstream, baseline, published, requested="", tagged=None, rebuild=False):
    tagged = tagged or {}
    if rebuild and not requested:
        raise ValueError("Rebuilding requires an explicit upstream tag")
    for tag, sha in upstream.items():
        previous = tagged.get(tag, published.get(tag, baseline.get(tag)))
        if previous and previous != sha:
            raise ValueError("Upstream tag moved; manual review required: " + tag)
    if requested and requested not in upstream:
        raise ValueError("Unknown upstream tag: " + requested)
    candidates = [requested] if requested else sorted((set(upstream) - set(baseline)) | set(tagged))
    jobs = []
    for tag in candidates:
        if tag in published and not rebuild:
            continue
        if not TAG.fullmatch(tag) or len(tag) > 120:
            raise ValueError("Unsupported tag/image name: " + tag)
        jobs.append({"tag": tag, "commit": upstream[tag], "image_tag": tag})
    # Limit each batch without dropping the rest: only published images are the completion checkpoint.
    return jobs[:16]


def repository_tags(upstream):
    result = {}
    names = subprocess.check_output(["git", "tag", "--list", "v*"], text=True).splitlines()
    for tag in names:
        if tag not in upstream or not TAG.fullmatch(tag):
            raise ValueError("Repository tag has no matching Geant4 source tag: " + tag)
        message = subprocess.check_output(
            ["git", "for-each-ref", "--format=%(contents)", "refs/tags/" + tag], text=True)
        try:
            record = json.loads(message)
        except ValueError:
            record = {}  # Manually created lightweight/annotated version tag.
        result[tag] = record.get("geant4_commit", upstream[tag])
    return result


def registry_tags():
    """Query GHCR using this repository's GITHUB_TOKEN with packages:read."""
    owner, package = os.environ["GITHUB_REPOSITORY"].lower().split("/")
    token = os.environ["GH_TOKEN"]
    result = set()
    page = 1
    while True:
        url = (f"https://api.github.com/orgs/{owner}/packages/container/{package}"
               f"/versions?per_page=100&page={page}")
        request = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                versions = json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return set()  # First publication: the package does not exist yet.
            raise RuntimeError(f"Cannot read GHCR package versions (HTTP {error.code})") from None
        for version in versions:
            result.update(version.get("metadata", {}).get("container", {}).get("tags", []))
        if len(versions) < 100:
            return result
        page += 1


def create_tags(jobs, existing):
    for job in jobs:
        tag = job["tag"]
        if tag in existing:
            continue  # Tags are immutable, including the initial OCI release tag.
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        record = {"geant4_tag": tag, "geant4_commit": job["commit"], "recipe_commit": commit}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as message:
            json.dump(record, message, indent=2)
            message.flush()
            subprocess.run(["git", "tag", "-a", tag, commit, "-F", message.name], check=True)
        subprocess.run(["git", "push", "origin", "refs/tags/" + tag], check=True)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--tag", default="", help="Build a specific upstream tag, including historic versions")
    cli.add_argument("--rebuild", action="store_true", help="Explicitly replace the selected image using this recipe revision")
    args = cli.parse_args()
    baseline = json.loads(Path("upstream-baseline.json").read_text())
    if baseline["upstream"] != UPSTREAM:
        raise ValueError("Unexpected upstream repository")
    refs = subprocess.check_output(["git", "ls-remote", "--tags", UPSTREAM], text=True)
    upstream = parse_refs(refs)
    tagged = repository_tags(upstream)
    images = registry_tags()
    published = {tag: sha for tag, sha in tagged.items() if tag in images}
    jobs = plan(upstream, baseline["tags"], published, args.tag, tagged, args.rebuild)
    create_tags(jobs, tagged)
    matrix = json.dumps({"include": jobs}, separators=(",", ":"))
    print(matrix)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
            stream.write("matrix=" + matrix + "\n")
            stream.write("count=" + str(len(jobs)) + "\n")


if __name__ == "__main__":
    main()
