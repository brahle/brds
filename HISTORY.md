Changelog
=========


(unreleased)
------------

Fix
~~~
- Enforce resolved reader path boundary (#15) [Bruno Rahle]

Other
~~~~~
- Preserve stable container latest and record registry digests (#19)
  [Bruno Rahle]
- Contain dataset catalog metadata and handle symlink loops (#18) [Bruno
  Rahle]

  * Contain dataset catalog metadata and reject unresolvable paths

  * Parse dataset catalog paths across platforms
- Recheck resolved API reader paths after version selection (#17) [Bruno
  Rahle]
- Publish validated release artifacts with locked container dependencies
  (#16) [Bruno Rahle]
- Fix and smoke-test the brds container release (#14) [Bruno Rahle]

  * fix: build and validate the brds API release image

  * fix: keep container smoke fixtures owned by the runner


0.12.1 (2026-09-03)
-------------------
- Release: version 0.12.1 🚀 [Bruno Rahle]
- Fload refuses an ambiguous version directory instead of guessing (#13)
  [Bruno Rahle]

  * fix: fload refuses an ambiguous version directory instead of guessing

  `FileReader.get(None)` was `_join(self._folder, _listdir(self._folder)[0])`
  -- whichever entry `readdir` handed back first. `readdir` order is not a
  contract: ext4 htree order depends on a hash seed chosen at mkfs, and is
  insertion order only for small linear directories. Every version directory
  brds writes holds exactly one file, so the first entry was the right entry
  for as long as that stayed true, and silently the wrong one the moment it
  did not.

  Silently is the problem. `load()` dispatches on the extension, so a second
  file is not an error, it is a different answer: forcing the adverse order on
  a leaf holding `data.parquet` + `manifest.json` returned

      RESULT TYPE: <class 'dict'>
      VALUE: {'stage': 6}

  with no exception. A caller doing `fload("model/club_form").shape` fails
  several frames from the cause; one doing `len(...)` gets the number of keys
  in a descriptor and no failure at all.

  `get(None)` now ignores debris (dotfiles, `.crc` checksums, `_SUCCESS`
  markers, partial writes and editor backups), returns the single remaining
  file, and raises `AmbiguousDirectoryError` -- naming the directory, listing
  the candidates and pointing at `fload(folder, filename)` -- when two files
  could both be the answer. Deterministic-but-silent would still be silent:
  picking `sorted(...)[0]` of a parquet and a stray second parquet is a stable
  wrong answer rather than an unstable one.

  A known sidecar descriptor (`manifest.json`) is skipped in favour of a
  payload, so a dataset can carry provenance beside its data -- which is what
  this blocks downstream. A directory holding *only* a descriptor still
  returns it: skipping there would turn a readable directory into a
  `FileNotFoundError`.

  Compatibility, measured rather than assumed: over all 7,849
  `<date>/<time>/` leaves in a real 5.3G store, old and new resolution return
  the identical path 7,849 times. All 9,376 leaves on the three live
  `fpl-*-data` PVCs hold exactly one file, none of it debris, so they resolve
  identically by construction.

  The new tests run every case under *every* permutation of `readdir` order
  rather than the one this filesystem happens to produce -- a test that
  exercises only today's ordering is not a test of the ordering. Against the
  unfixed reader 13 of the 18 fail; the headline one prints

      [(('data.parquet', 'manifest.json'), 'ok'),
       (('manifest.json', 'data.parquet'), 'wrong')]

  Refs: nexus a6c112b6

  * test: install the async plugin the suite already depends on

  `tests/core/fs/test_minio_writer.py::test_stream_write` is an `async def`
  marked `@pytest.mark.asyncio`, added with MinioWriter in 874d37f, but
  `pytest-asyncio` was never added to `requirements-test.txt`. CI has therefore
  been red on `main` since 2025-08-05 with

      Failed: async def functions are not natively supported.

  and, because `make test` runs `--maxfail=1` and that file collects first, the
  run stops there and *nothing after it executes*. A suite that stops at item 8
  of 38 is not running the other 30; it only looks like it is failing for one
  reason.

  It passes locally because a developer venv happens to have the plugin. Naming
  it makes the machine's suite the same suite as the laptop's: 38 passed, which
  is the same 38 collected on the runner today.


0.12.0 (2025-08-05)
-------------------
- Release: version 0.12.0 🚀 [Bruno Rahle]
- Feat: add MinioWriter for S3-compatible object storage. [Bruno Rahle,
  Claude]

  Add MinioWriter class that mirrors FileWriter interface but writes to configurable MinIO/S3 buckets. Supports pandas DataFrames, JSON objects, HTTP responses, and async streaming with automatic bucket creation and timestamp columns.

  🤖 Generated with [Claude Code](https://claude.ai/code)
- Minor changes to file listing. [Bruno Rahle]


0.11.0 (2024-08-20)
-------------------
- Release: version 0.11.0 🚀 [Bruno Rahle]
- Refactor: reorganize imports and add RootedReader to brds.core.fs.
  [Bruno Rahle]


0.10.0 (2024-08-18)
-------------------
- Release: version 0.10.0 🚀 [Bruno Rahle]
- Hotfixing - removing print' [Bruno Rahle]


0.9.0 (2024-08-18)
------------------
- Release: version 0.9.0 🚀 [Bruno Rahle]
- Stream Writer (#12) [Bruno Rahle]

  * Stream Writer

  * Fixing the formatting


0.8.0 (2024-08-18)
------------------
- Release: version 0.8.0 🚀 [Bruno Rahle]
- Fixing the logger. [Bruno Rahle]


0.7.0 (2024-08-18)
------------------
- Release: version 0.7.0 🚀 [Bruno Rahle]
- BREAKING CHANGE: New aiohttp HttpClient (#11) [Bruno Rahle]

  * Breaking Changes to the HttpClient, BrowserEmulator, improvements to the Domain Rate Limiter and Logger

  * Fixing tests

  * Fixing Crawler


0.6.0 (2024-08-18)
------------------
- Release: version 0.6.0 🚀 [Bruno Rahle]
- Fixing Crawler. [Bruno Rahle]
- Fixing tests. [Bruno Rahle]
- Breaking Changes to the HttpClient, BrowserEmulator, improvements to
  the Domain Rate Limiter and Logger. [Bruno Rahle]


0.5.0 (2024-05-27)
------------------
- Release: version 0.5.0 🚀 [Bruno Rahle]
- Fixing lint. [Bruno Rahle]
- Adding pipeline crawl. [Bruno Rahle]
- Fixing formatting. [Bruno Rahle]
- Improvements. [Bruno Rahle]


0.4.1 (2023-09-08)
------------------
- Release: version 0.4.1 🚀 [Bruno Rahle]
- Fixing the release script (#10) [Bruno Rahle]

  * Fixing the release script

  * Adding the automatic next version detection


0.4.0 (2023-09-08)
------------------
- Release: version 0.4.0 🚀 [Bruno Rahle]
- Release: version  🚀 [Bruno Rahle]
- Crawler working with loop variables (#9) [Bruno Rahle]
- Release: version  🚀 [Bruno Rahle]
- Release: version  🚀 [Bruno Rahle]
- Crawler implementation (#8) [Bruno Rahle]

  * Crawler implementation

  * Fixing lint

  * Storing variables


0.3.1 (2023-04-17)
------------------
- Release: version 0.3.1 🚀 [brahle]
- Removing unsupported flag. [brahle]
- Fixing the files. [brahle]
- Removing codecov which is deleted. [brahle]
- CORS. [brahle]


0.3.0 (2023-04-11)
------------------
- Release: version 0.3.0 🚀 [brahle]
- Release: version 0..0 🚀 [brahle]
- Preventing exploits. [brahle]


0.2.8 (2023-04-10)
------------------
- Release: version 0.2.8 🚀 [brahle]
- Also tagging the version from the ref. [brahle]


0.2.7 (2023-04-10)
------------------
- Release: version 0.2.7 🚀 [brahle]
- Fixing the publishing. [brahle]


0.2.6 (2023-04-10)
------------------
- Release: version 0.2.6 🚀 [brahle]
- Fixing return types. [brahle]
- Publish to docker. [brahle]


0.2.5 (2023-04-10)
------------------
- Release: version 0.2.5 🚀 [brahle]
- Adding pandas stubs. [brahle]


0.2.4 (2023-04-10)
------------------
- Release: version 0.2.4 🚀 [brahle]
- Fixing packaging. [brahle]


0.2.3 (2023-04-10)
------------------
- Release: version 0.2.3 🚀 [brahle]
- Adding .typed file. [brahle]


0.2.2 (2023-04-10)
------------------
- Release: version 0.2.2 🚀 [brahle]
- Exposing some additional items. [brahle]


0.2.1 (2023-04-10)
------------------
- Release: version 0.2.1 🚀 [brahle]
- Fixing the formatting. [brahle]


0.2.0 (2023-04-10)
------------------
- Release: version 0.2.0 🚀 [brahle]
- Edit (#7) [Bruno Rahle]


0.1.1 (2023-04-10)
------------------
- Release: version 0.1.1 🚀 [brahle]
- Release: version 0.1.0 🚀 [brahle]
- Merge branch 'main' of github.com:brahle/brds into main. [brahle]
- Br/updates (#6) [Bruno Rahle]

  * Adding FastAPI app to show the datasets

  * Updates to the container


0.1.0 (2023-04-10)
------------------
- Release: version 0.1.0 🚀 [brahle]


0.0.5 (2023-02-18)
------------------
- Release: version 0.0.5 🚀 [brahle]
- Feat: Adding gunzip imporer (#5) [Bruno Rahle]


0.0.4 (2023-02-18)
------------------
- Release: version 0.0.4 🚀 [brahle]
- Updating version (#4) [Bruno Rahle]


0.0.3 (2023-02-18)
------------------
- Release: version 0.0.3 🚀 [brahle]
- Fixing the docs (#3) [Bruno Rahle]


0.0.2 (2023-02-18)
------------------

Fix
~~~
- Release (#2) [Bruno Rahle]

Other
~~~~~
- Release: version 0.0.2 🚀 [brahle]


0.0.1 (2023-02-18)
------------------
- Release: version 0.0.1 🚀 [brahle]
- Feat: Initial version (#1) [Bruno Rahle]

  * Initial version of the brds

  * Fixing license

  * Adding fetcher and importer

  * Fixing the code
- ✅ Ready to clone and code. [brahle]
- Initial commit. [Bruno Rahle]


