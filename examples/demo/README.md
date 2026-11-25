# Demo data: FAKE, not real model output

Every JSON file in this folder is **hand-written fake data**. None of it is real model output. Each file is marked with `"fake": true` and the label `FAKE: hand-written demo data, not real model output`. The loader (`reqpilot.llm.load_fake`) refuses any file that lacks the marker, and the app shows these sets as "demo data, not real model output".

These files are used for two things:
- the bundled examples in the app, which run without an API key or any AI call;
- tests of the writer, reviewer and test-case code, which receive these answers through `FakeTransport` and never reach the network.

The faults in the writer files were put there on purpose, to show what the reviewer and the Python checks find. Each file's `purpose` field lists them, for example a generic role "As a user", an invented number, a wrong source sentence, a vague word, or a goal joining two actions.

| Set | Files |
| --- | --- |
| `01_maintenance/`, `02_procurement/`, `03_lab_results/` | `writer.json`, `reviewer.json`, `test_cases.json` |

The notes they belong to are in `data/notes/`. Once live calls are allowed, real recordings will replace these files as the bundled examples (plan M8), and they will be labelled as recorded model output.
