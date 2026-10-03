#!/usr/bin/env python3
"""Check Python, weighted ROOT I/O and strict JSON without PyROOT or datasets."""
import importlib.util
import json
from pathlib import Path
import tempfile

import numpy as np
import uproot
from uproot.writing.identify import to_TAxis, to_TH1x

assert importlib.util.find_spec("ROOT") is None, "PyROOT must not be installed"
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp)
    with uproot.recreate(path / "test.root") as output:
        output["hist"] = to_TH1x(
            fName="hist", fTitle="hist", data=np.array([0., 9., 0.]),
            fEntries=4., fTsumw=9., fTsumw2=25., fTsumwx=0., fTsumwx2=0.,
            fSumw2=np.array([0., 25., 0.]), fXaxis=to_TAxis("xaxis", "", 1, 0., 1.))
    with uproot.open(path / "test.root") as source:
        hist = source["hist"]
        assert hist.values().tolist() == [9.]
        assert hist.errors().tolist() == [5.]
        json.dumps({"values": hist.values().tolist(), "errors": hist.errors().tolist()}, allow_nan=False)
print("Python, uproot and weighted ROOT I/O passed; PyROOT absent")
