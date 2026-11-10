# JSON output

With `--json`, diffract writes the result to stdout as one JSON object. The Python
method `DiffractResult.to_dict()` gives the same object.

```bash
diffract v1.2.0 HEAD --json
```

```json
{
  "group": "feat!",
  "possible_types": [
    "feat!"
  ],
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
| `group` | string | The group of possible types: `feat!`, `feat`, `code`, `test` or `other`. Read [Getting started](getting-started.md#how-diffract-gives-the-commit-types). |
| `possible_types` | list | The Conventional Commit types in the group, for example `["fix", "refactor", "perf", "style"]` for `code`. |
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
group=$(diffract --json | jq -r .group)
```
