import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("oci_index", Path(__file__).parents[1] / "scripts/oci_index.py")
oci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oci)
A, B = "a" * 64, "b" * 64


def manifest(sif_sha256):
    return json.dumps({"schemaVersion": 2, "mediaType": oci.MANIFEST, "layers": [
        {"mediaType": oci.SIF_LAYER, "digest": "sha256:" + sif_sha256, "size": 1}]}).encode()


def provenance(arch, sif_sha256, tag="v11.3.2", commit="c" * 40):
    return {"arch": arch, "geant4_tag": tag, "geant4_commit": commit, "sif_sha256": sif_sha256}


class IndexTests(unittest.TestCase):
    def test_index_has_one_platform_per_architecture(self):
        entries = [("arm64", manifest(B), provenance("arm64", B)),
                   ("amd64", manifest(A), provenance("amd64", A))]
        result = oci.index(entries, "v11.3.2", {"org.opencontainers.image.version": "v11.3.2"})
        self.assertEqual(result["mediaType"], oci.INDEX)
        self.assertEqual([m["platform"] for m in result["manifests"]],
                         [{"architecture": "amd64", "os": "linux"}, {"architecture": "arm64", "os": "linux"}])
        self.assertEqual(result["manifests"][0]["digest"], "sha256:" + hashlib.sha256(manifest(A)).hexdigest())
        self.assertEqual(result["manifests"][0]["size"], len(manifest(A)))

    def test_missing_or_duplicate_architecture_fails(self):
        with self.assertRaises(ValueError):
            oci.index([("amd64", manifest(A), provenance("amd64", A))], "v11.3.2", {})
        with self.assertRaises(ValueError):
            oci.index([("amd64", manifest(A), provenance("amd64", A))] * 2, "v11.3.2", {})

    def test_stale_or_foreign_manifest_fails(self):
        with self.assertRaises(ValueError):  # Tag still holds an older SIF.
            oci.index([("amd64", manifest(B), provenance("amd64", A)),
                       ("arm64", manifest(B), provenance("arm64", B))], "v11.3.2", {})
        with self.assertRaises(ValueError):  # Provenance belongs to another version.
            oci.index([("amd64", manifest(A), provenance("amd64", A, "v11.4.0")),
                       ("arm64", manifest(B), provenance("arm64", B))], "v11.3.2", {})

    def test_different_source_commits_fail(self):
        with self.assertRaises(ValueError):
            oci.index([("amd64", manifest(A), provenance("amd64", A)),
                       ("arm64", manifest(B), provenance("arm64", B, commit="d" * 40))], "v11.3.2", {})


if __name__ == "__main__": unittest.main()
