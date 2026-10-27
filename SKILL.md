---
name: arch-mode
description: >
  Architecture rules for writing or changing code, drawn from Clean Architecture (Robert C. Martin),
  Design Patterns (Gamma, Helm, Johnson, Vlissides) and Designing Data-Intensive Applications
  (Martin Kleppmann). Use together with ub-mode every time code is written or changed: ub-mode says
  how to work, arch-mode says where code goes, which way dependencies point and what happens to data
  when something fails. The gate is the archcheck tool.
---

# arch-mode

Every time you write or change code:
* Work inside ub-mode. arch-mode adds no new process; it informs Foundational Thinking and Architecture
  in "First Make it Work", and adds the archcheck gate to "Then Make it Right".
* Decide where the code lives (Structure), how the parts talk (Design), and what happens to the data
  under load and failure (Data).
* When a rule here and ub-mode's Laziness Protocol seem to disagree, the smaller change wins.
  Structure is added when its force is present, not in advance.

# Structure (Clean Architecture)

## The Dependency Rule

* Source code dependencies point inward: frameworks and drivers -> adapters -> use cases -> entities.
* Nothing in an inner circle names anything in an outer one: no class, function, table, URL or framework type.
* Data that crosses a boundary is plain and shaped for the inner side, never an ORM row or an HTTP request.
* Entities are not ORM models or API schemas. Persistence mapping lives in the adapter that owns the table.

## Entities and Use Cases

* Entities hold the business rules that would exist even without this program.
* A use case is one thing the application does: it takes a request model, drives entities, returns a response model.
* Keep use cases pure. I/O reaches them through ports they own.

## Ports and Adapters

* The inner side declares the interface it needs (a port). The outer side implements it (an adapter).
* When the flow of control must go outward, invert the source dependency with an interface.
* Main is the dirtiest component: it reads configuration, builds the concrete adapters and wires them in.

## Humble Object

* Split what is hard to test (screen, database, network, clock, filesystem) into a humble part with no
  logic and a part that holds all the logic.
* Test the logic part. Keep the humble part too simple to break.

## Boundaries Where Change Lives

* Draw a boundary between things that change for different reasons or at different rates.
* Spend on the boundaries that are expensive to add later: business rules versus I/O, a published API,
  a stored data format. Skip the ones that are cheap to add later.
* Do not build for a replacement that will not happen. One implementation needs no interface until a
  second one or a test fake needs it.
* A boundary has a cost. Start with a partial one (an interface beside its user) and make it full when a
  second implementation or a separate deployment actually arrives.
* The database, the web, the UI and the framework are details. Keep them out of the rules so they can be
  chosen late and replaced.
* Layered is not clean: controller -> service -> repository, where the service imports the ORM, still
  points the wrong way.

## Package by Feature

* Group code by feature or component, not by technical layer: no project-wide controllers/, services/,
  repositories/ folders. Top-level packages name the domain, not the framework.
* Inside a feature, the Dependency Rule still holds.
* Not every feature needs every layer. Plain CRUD may go from the adapter to the store; add use cases and
  entities where there are business rules.
* Map between layers only where the shapes differ.
* In existing code, put the boundary at the seam you are changing and leave the rest. Do not re-layer a
  working project as a side effect.

## Components

* No cycles between packages. Break one with an interface owned by one side, or with a new package.
* Depend in the direction of stability: volatile code depends on stable code.
* The more stable a package, the more abstract it should be. Stable and concrete is the zone of pain;
  abstract and unused is the zone of uselessness.
* Put together what changes together. Do not make a user depend on what it does not use.

## SOLID

* SRP: a module answers to one actor.
* OCP: add behavior by adding code behind an interface, not by editing a switch.
* LSP: a subtype keeps the contract of its base, or it is not a subtype.
* ISP: a client sees only what it calls.
* DIP: policy owns the abstraction; details implement it.

## Tests Are the Outermost Circle

* Tests depend on the code; the code never depends on the tests.
* Test a use case through its own interface with fake adapters behind its ports. Do not boot a framework
  to test a rule. ub-mode's Test Behavior still decides what a good test is.

# Design (Design Patterns)

## Principles First

* Program to an interface, not an implementation.
* Favor composition over inheritance. Inherit for a true is-a with a stable contract, and keep project
  inheritance shallow: two levels at most.
* Find what varies and put it behind one interface.

## A Pattern Only for Its Problem

* Name the force before the pattern. If the force is absent, write the plain code.
* Wait for the second concrete case before abstracting; the first one is just code.
* If the pattern makes the code feel forced, the problem is a different one. Look again, or drop the pattern.
* Name the pattern where you use it; the name is documentation.
* In a dynamic language most patterns shrink to a language feature (Norvig counted 16 of 23). Use the
  small form and keep the name in a comment, so the intent survives.

## Forces and Their Patterns

| Force | Pattern | In Python |
|---|---|---|
| Families of related objects vary together with configuration | Abstract Factory | a module or dict of constructors chosen in Main |
| Construction has many optional parts or ordered steps | Builder | keyword arguments or a dataclass; a builder only when steps validate each other |
| Which class to create varies | Factory Method | a class or function is already a factory; pass it in |
| Make a new object by copying a configured one | Prototype | `copy.copy`, `dataclasses.replace` |
| One shared instance | Singleton | do not: create it once in Main and pass it in; a module-level constant if it is immutable |
| A third-party interface does not match the one you need | Adapter | a small class at the boundary; this is the port's adapter |
| Two independent dimensions of variation | Bridge | compose two interfaces instead of a class per combination |
| Part-whole trees treated uniformly | Composite | a node type with children and the same method as the leaf |
| Behavior around calls: retry, cache, metrics, logging | Decorator | a wrapper object, or a function decorator for functions |
| A complex subsystem used from many places | Facade | a module with a few functions |
| Many small, identical, immutable objects | Flyweight | interning, `functools.lru_cache` on the constructor |
| Same interface, with lazy loading, access control, remote call or caching | Proxy | a wrapper class; `__getattr__` to forward the rest |
| The handler of a request is not known in advance | Chain of Responsibility | a list of handlers or middleware, each passes or handles |
| Requests to queue, log, retry or undo | Command | a callable, `functools.partial`, or a small dataclass |
| A small rule language | Interpreter | a tree of small node classes, or a table of rules |
| Walk a collection without exposing its structure | Iterator | a generator |
| Many objects coordinating many-to-many | Mediator | one coordinator object; the others know only it |
| Save and restore state for undo, without exposing internals | Memento | an immutable snapshot (frozen dataclass) |
| One-to-many notification of change | Observer | a list of callbacks or events; handlers idempotent |
| Behavior changes with the object's mode | State | one object per state behind one interface |
| An algorithm varies | Strategy | pass a function |
| Fixed skeleton with varying steps | Template Method | prefer passing the steps in (Strategy) over subclassing |
| Operations over a fixed type hierarchy you own | Visitor | `functools.singledispatch` |

* A type switch on your own classes that repeats in more than one place moves into the types (polymorphism,
  Strategy, State, Visitor). One switch in one place, such as a factory in Main, is fine. A switch over
  library or builtin types is parsing at a boundary and is fine.

# Data (Designing Data-Intensive Applications)

## Reliability, Scalability, Maintainability

* Faults are normal. Design so that a fault does not become a failure.
* Before optimizing, write down the load parameters and the percentile you aim at (p95, p99), not the average.
* A request that fans out to many calls is as slow as the slowest one. Give each call a deadline from the
  request's time budget, and measure the percentile where the user waits.
* Keep it operable: visible state, a safe restart and a simple path for the next change.

## System of Record and Derived Data

* Every fact has exactly one system of record. Caches, indexes, search, views, ML features, embeddings and
  vector indexes are derived and can be rebuilt from it.
* Write derivation as a function of the record that can be replayed, not as a second writer. Version derived
  data with the code or model that produced it.
* Never dual-write. Writing to the database and separately to a broker, cache or search index leaves them
  inconsistent when one write fails. Write once (a database with an outbox table, or a log) and derive the
  rest (change data capture).

## Data Models, Encoding and Schemas

* Choose the model from the access pattern: relational for joins and many-to-many, documents for
  self-contained trees, graphs for dense relationships.
* Schemas evolve. New code reads old data and old code reads new data: add optional fields with defaults,
  never give a field or tag a new meaning, never remove a required field in one step.
* Do not store or exchange data in a language-specific format (pickle, joblib, marshal): it ties the data to
  one code version and runs code on load. Use a schema format (JSON with a schema, Avro, Protobuf, Parquet).
  Model weights are the usual exception; record the producing code version beside them.
* Parse and validate where data enters, into the inner model (ub-mode Boundary Discipline).

## Storage

* Know the read and write paths of your store. Add an index for a query you run, not for a guess:
  every index slows writes.
* Transactions and analytics are different workloads. Do not scan the transactional store for analytics;
  derive a separate one.
* Object storage is the durable base; compute and local disks are disposable. Keep state you cannot lose
  out of the container.

## Replication and Partitioning

* Know what replication lag does to your reads: read-your-writes, monotonic reads, consistent prefix.
  Choose explicitly where they matter.
* Last-write-wins by timestamp silently drops concurrent writes. When writes can conflict, use versions,
  a merge rule or a single leader. Leaderless quorums are not linearizable by themselves.
* Choose the partition key from the access pattern, and watch for hot keys.

## Transactions and Consistency

* Name the isolation level you rely on. Read committed does not prevent lost updates or write skew.
* Prevent lost updates with an atomic operation, compare-and-set or an explicit lock, not with
  read-modify-write in application code.
* Check-then-insert (two bookings of one slot) is write skew through a phantom: guard it with a unique
  constraint, serializable isolation or a lock on a row that exists.
* When something must be linearizable (a unique name, a leader, a lock), take it from a store or a consensus
  service that provides it. Do not build your own.
* Do not span services with distributed transactions by default. Use a log and idempotent consumers.

## Faults in Distributed Systems

* Every network call has a timeout. An unbounded wait is a hang.
* Retry only what is idempotent, or make it idempotent (ub-mode Make Operations Idempotent).
* End to end: TCP, a broker or a database transaction alone do not remove duplicates. Create a request id
  where the request starts and carry it to the place that writes; deduplicate there.
* Default to at-least-once delivery with idempotent handlers. Exactly-once is idempotence plus deduplication.
* Clocks lie. Measure durations with a monotonic clock. Store timestamps in UTC with a time zone. Order
  events across machines by a sequence, version or log offset, never by wall-clock time.
* A process can pause at any moment. A lease or lock needs a fencing token.
* Do not swallow errors. A hidden fault is a postponed failure (ub-mode Fix Root Causes).

## Batch and Stream

* A batch job reads immutable input and writes new output. Running it again gives the same result.
* A stream consumer commits its offset atomically with its output, or is idempotent.
* Queues are bounded. When consumers fall behind, choose explicitly: block the producer (backpressure),
  drop, or spill to disk.

## Responsibility for Data

* Collect only what the purpose needs. Personal data is a liability that outlives the reason it was collected.
* Set a retention period and delete. Deletion must reach derived data, logs and backups; in an immutable
  log, encrypt per person and destroy the key.
* An automated decision about a person needs an explanation and a way to appeal.
* Follow the project's data policy: what may leave the machine, which external models may see it.

# Gate: archcheck

* Run `archcheck --changed` from the project root after the change, next to crapper, dryer and mutator.
* Errors fail the gate: a Dependency Rule violation, I/O or a framework in a pure layer, a package cycle,
  a network call without a timeout, a file that does not parse.
* Warnings ask for a decision, not obedience: a dependency toward a less stable package, a type switch over
  project classes, deep inheritance, a Singleton, global state, a wall-clock duration, a naive datetime,
  a swallowed broad exception, language-specific serialization, an unbounded queue.
  Fix it, or mark the line `# archcheck: ignore[rule] reason` and say why.
* Configure layers in `pyproject.toml` under `[tool.archcheck]` once the project has more than one layer.
  Without layers the other checks still run.
* Report the archcheck result together with the other gates.

# Practice

* Record a decision when you choose a boundary, a store, a consistency guarantee or a pattern: one paragraph
  in the commit message, or `docs/adr/NNNN-title.md` when the project keeps ADRs.
* Name packages, use cases and ports in the words of the domain glossary (ub-mode Model the Domain).
