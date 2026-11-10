# JSON output

With `--json`, diffract writes the result to stdout as one JSON object. The Python
method `DiffractResult.to_dict()` gives the same object.

```bash
diffract v1.2.0 HEAD --json
```

```json
{
  "commit_type": "feat!",
  "summary": "Breaking change. Removed public names: sheridan.diffract: OldHelper",
  "base_ref": "v1.2.0",
  "head_ref": "HEAD",
  "diff": {
    "added": [],
    "removed": [
      {
        "module": "sheridan.diffract",
        "name": "OldHelper"
      }
    ]
  }
}
```

## Keys

| Key | Type | Description |
|---|---|---|
| `commit_type` | string | `feat!`, `feat`, `refactor` or `fix`. |
| `summary` | string | A description of the change for people. Do not parse it. |
| `base_ref` | string | The earlier ref, as you gave it. |
| `head_ref` | string | The later ref, as you gave it. For the staging area, the value is `:staged`. |
| `diff.added` | list | The added public names. Each item has the keys `module` and `name`. |
| `diff.removed` | list | The removed public names. Each item has the keys `module` and `name`. |

## Exit code

`--json` does not change the exit code. To get an exit code for the type of change, add
`--exit-code`. Read [CLI and exit codes](cli.md#exit-codes).

## Read the output in a script

```bash
commit_type=$(diffract --json | jq -r .commit_type)
```
