# Public release audit

PACKAGE_FILE_COUNT=47
PACKAGE_SIZE_MB=0.101613

ABSOLUTE_PATH_MATCH_COUNT=0
INTERNAL_TERM_MATCH_COUNT=0
SECRET_MATCH_COUNT=0

PYTEST_RESULT=PASS (10 passed)
QUICK_REPRODUCTION=PASS
FULL_REPRODUCTION=PASS
EXPECTED_RESULT_MISMATCH_COUNT=0

THIRD_PARTY_FILE_COUNT=1
THIRD_PARTY_LICENSE_RISK=PASS

GITHUB_READY=true
ZENODO_READY=true

## Clean-room validation

DEPENDENCY_INSTALLATION=PASS
PYTHON_VERSION=3.11.9
RDFLIB_VERSION=7.6.0
PYTEST_RUNTIME_SECONDS=9.221
QUICK_RUNTIME_SECONDS=8.127
FULL_RUNTIME_SECONDS=100.005
PEAK_GENERATED_ARTIFACT_SIZE_MB=11.738358

The clean-room directory was created from this package alone. A new virtual
environment used the host's exact pinned packages through Python's
system-site-packages mechanism, after which `pip install -r requirements.txt`
confirmed every required version. Tests, quick reproduction, and full
reproduction all completed successfully.

The single third-party-related file is the secondary numeric transcription in
`data/external/zhang_fig13_transcription.csv`. It contains no source image or
copyrighted artwork and is accompanied by a source citation and provenance
note. No manuscript, submission document, credentials, local history, cache,
or generated output is included in the package.
