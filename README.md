# arch-mode

`arch-mode` is an agent skill for the architecture side of writing and changing code. It is a companion to
[unclebob/ub-mode](https://github.com/unclebob/ub-mode): ub-mode says how to work (make it work, make it right,
practice), arch-mode says where code goes, which way dependencies point and what happens to data when something
fails. The rules are a condensed reading of three books:

- **Clean Architecture** — Robert C. Martin: the Dependency Rule, entities and use cases, ports and adapters,
  boundaries, component principles (ADP, SDP, SAP, CCP, CRP), SOLID.
- **Design Patterns: Elements of Reusable Object-Oriented Software** — Gamma, Helm, Johnson, Vlissides:
  program to an interface, favor composition, patterns named by the force they resolve.
- **Designing Data-Intensive Applications** — Martin Kleppmann: system of record and derived data, schema
  evolution, isolation and lost updates, timeouts, idempotence, clocks, batch and stream.

The skill is paired with a deterministic gate, **archcheck**, in the same spirit as ub-mode's
[crapper](https://github.com/unclebob/crapper), [dryer](https://github.com/unclebob/dryer) and
[mutator](https://github.com/unclebob/mutator).

## How it fits ub-mode

arch-mode adds no process of its own. Where both speak, they say the same thing:

| ub-mode | arch-mode |
|---|---|
| Laziness Protocol: smallest edit, one decision in one place | Structure is added when its force is present; partial boundaries first; apply rules to the code you touch; one system of record |
| Foundational Thinking: data shape first; no shared state under concurrent writers | Data section: model from access pattern, schemas that evolve, single writer for invariants |
| Model the Domain, glossary | Entities and use cases; packages named in the domain's words |
| Boundary Discipline: check data where it enters, pure business logic | The Dependency Rule, ports and adapters, pure layers (checked by archcheck) |
| Make Operations Idempotent | Retries only for idempotent operations; at-least-once plus idempotent handlers; replayable derivations |
| Separate Before Serializing Shared State | No Singleton or module-level mutable state; one writer, enforced in structure |
| Fix Root Causes | Do not swallow errors (checked by archcheck) |
| Test Behavior, Not Implementation | Tests are the outermost circle; test use cases through their ports with fake adapters |
| Crapper: consider whether case statements are worth reducing | A type switch repeated in several places moves into the types; one switch in one place is fine |
| Build the Lever | archcheck is the lever for structure |
| Then Make it Right: crapper, dryer, mutator | plus `archcheck --changed` |

When a rule here and the Laziness Protocol seem to pull apart, the smaller change wins.

## Installation

Copy `SKILL.md` into your agent's skills directory as `arch-mode/SKILL.md` (for example
`~/.claude/skills/arch-mode/SKILL.md` or `~/.cursor/skills/arch-mode/SKILL.md`), then invoke `/arch-mode`.
To have it used on every coding task, say so in your project or user instructions (`CLAUDE.md`, `AGENTS.md`).

archcheck needs Python 3.10+ (3.11+ to read configuration) and nothing else:

```bash
git clone https://github.com/Akhmetov-VA/arch-mode.git ~/tools/arch-mode
~/tools/arch-mode/archcheck --help          # or: pip install ~/tools/arch-mode
```

## archcheck

```bash
archcheck                      # whole project, from its root
archcheck --changed            # only files changed or added in git
archcheck src/shop/domain      # only findings under these paths
archcheck --strict             # warnings fail too
archcheck --json               # machine-readable report
```

Exit code 0 is clean, 1 means errors (or warnings with `--strict`), 2 means a configuration or git problem.
Each run writes `.metrics/arch.json` (skip with `--no-write`). Tests (`tests/`, `test_*.py`, `conftest.py`),
virtualenvs and hidden directories are not checked.

### Layers

List the layers from the innermost to the outermost. A module may import from its own layer and from inner
layers. `pure = true` also forbids I/O, drivers and frameworks (`os`, `subprocess`, `requests`, `sqlalchemy`,
`django`, `aiogram`, … and `open()`); `forbid` adds names of your own.

```toml
[tool.archcheck]
roots = ["src"]                 # default: src/ if it exists, else the project root
exclude = ["src/shop/migrations/*"]
disable = []                    # rule names to turn off

[[tool.archcheck.layers]]
name = "domain"
modules = ["shop.domain"]
pure = true

[[tool.archcheck.layers]]
name = "use-cases"
modules = ["shop.app"]
pure = true

[[tool.archcheck.layers]]
name = "adapters"
modules = ["shop.adapters", "shop.web"]

[[tool.archcheck.layers]]
name = "main"
modules = ["shop.main"]
```

Without a `pyproject.toml` the same keys can live at the top level of `.archcheck.toml`.
Modules that belong to no layer are not checked by the layer rules.

### Rules

| Rule | Severity | Source | What it means |
|---|---|---|---|
| `dependency-rule` | error | Clean Architecture | an inner layer imports an outer one |
| `pure-layer` | error | Clean Architecture | a pure layer imports I/O, a driver or a framework, or opens a file |
| `component-cycle` | error | Clean Architecture (ADP) | packages import each other |
| `network-timeout` | error | DDIA, ch. 8 | `requests`, `urlopen`, `socket.create_connection` without a timeout, or `httpx` with `timeout=None` |
| `parse-error` | error | — | the file does not parse |
| `unstable-dependency` | warning | Clean Architecture (SDP) | a package depends on a less stable one |
| `type-switch` | warning | Design Patterns | three or more `isinstance` checks on one value in a function |
| `deep-inheritance` | warning | Design Patterns | a class inherits through three or more project classes |
| `global-state` | warning | Design Patterns, ub-mode | a `global` statement |
| `wall-clock-duration` | warning | DDIA, ch. 8 | a duration computed from `time.time()` |
| `naive-datetime` | warning | DDIA, ch. 8 | `datetime.now()` without tz, `utcnow()`, `today()` |
| `swallowed-error` | warning | DDIA, ub-mode | a bare or broad `except` whose body does nothing |

Silence one line with `# archcheck: ignore[rule] reason` (or `# archcheck: ignore` for every rule on it).

The report ends with package metrics from Clean Architecture: afferent and efferent couplings (Ca, Ce),
instability `I = Ce / (Ca + Ce)`, abstractness `A` (share of ABCs, Protocols and classes with abstract
methods) and the distance from the main sequence `D = |A + I - 1|`.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install pytest coverage
.venv/bin/python -m pytest
```

## License

MIT. The skill paraphrases ideas from the books above; it does not reproduce their text.
