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

## Entities and Use Cases

* Entities hold the business rules that would exist even without this program.
* A use case is one thing the application does: it takes a request model, drives entities, returns a response model.
* Keep use cases pure. I/O reaches them through ports they own.

## Ports and Adapters

* The inner side declares the interface it needs (a port). The outer side implements it (an adapter).
* When the flow of control must go outward, invert the source dependency with an interface.
* Main is the dirtiest component: it reads configuration, builds the concrete adapters and wires them in.

## Boundaries Where Change Lives

* Draw a boundary between things that change for different reasons or at different rates.
* A boundary has a cost. Start with a partial one (an interface beside its user) and make it full when a
  second implementation or a separate deployment actually arrives.
* The database, the web, the UI and the framework are details. Keep them out of the rules so they can be
  chosen late and replaced.
* Top-level packages name the domain, not the framework.
* In existing code, apply the rules to what you touch. Do not re-layer a working project as a side effect.

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
* Name the pattern where you use it; the name is documentation.
* In Python a function is often the whole pattern: a Strategy is a callable, a Factory is a function,
  a Command is a closure.

## Forces and Their Patterns

* The same type switch in more than one place: move the behavior into the types (polymorphism, Strategy,
  State, Visitor). One switch in one place, such as a factory in Main, is fine.
* Creation that varies with configuration: Factory or Abstract Factory, called from Main.
* A third-party API you do not control: Adapter at the boundary. This is the port's adapter.
* Behavior around calls (retry, cache, metrics, logging): Decorator, not edits inside the call.
* A complex subsystem used from many places: Facade.
* Part-whole trees: Composite.
* One-to-many notification of change: Observer or events, with idempotent handlers.
* Requests to queue, log, retry or undo: Command.
* Global access: not a Singleton. Main passes the dependency in. Module-level mutable state is a hidden global.

# Data (Designing Data-Intensive Applications)

## Reliability, Scalability, Maintainability

* Faults are normal. Design so that a fault does not become a failure.
* Before optimizing, write down the load parameters and the percentile you aim at (p95, p99), not the average.
* Keep it operable: visible state, a safe restart and a simple path for the next change.

## System of Record and Derived Data

* Every fact has exactly one system of record. Caches, indexes, search, views and ML features are derived
  and can be rebuilt from it.
* Write derivation as a function of the record that can be replayed, not as a second writer.
* When several systems need the same changes, feed them from one ordered log (change data capture or events).

## Data Models and Schemas

* Choose the model from the access pattern: relational for joins and many-to-many, documents for
  self-contained trees, graphs for dense relationships.
* Schemas evolve. New code reads old data and old code reads new data: add optional fields with defaults,
  never give a field or tag a new meaning, never remove a required field in one step.
* Parse and validate where data enters, into the inner model (ub-mode Boundary Discipline).

## Storage and Indexes

* Know the read and write paths of your store. Add an index for a query you run, not for a guess:
  every index slows writes.
* Transactions and analytics are different workloads. Do not scan the transactional store for analytics;
  derive a separate one.

## Replication and Partitioning

* Know what replication lag does to your reads: read-your-writes, monotonic reads, consistent prefix.
  Choose explicitly where they matter.
* Choose the partition key from the access pattern, and watch for hot keys.

## Transactions and Consistency

* Name the isolation level you rely on. Read committed does not prevent lost updates or write skew.
* Prevent lost updates with an atomic operation, compare-and-set or an explicit lock, not with
  read-modify-write in application code.
* An invariant across rows needs serializable isolation, a constraint in the store or a single writer.
* Do not span services with distributed transactions by default. Use a log and idempotent consumers.

## Faults in Distributed Systems

* Every network call has a timeout. An unbounded wait is a hang.
* Retry only what is idempotent, or make it idempotent with a request id and deduplication
  (ub-mode Make Operations Idempotent).
* Default to at-least-once delivery with idempotent handlers. Exactly-once is idempotence plus deduplication.
* Clocks lie. Measure durations with a monotonic clock. Store timestamps in UTC with a time zone. Order
  events across machines by a sequence, version or log offset, never by wall-clock time.
* A process can pause at any moment. A lease or lock needs a fencing token.
* Do not swallow errors. A hidden fault is a postponed failure (ub-mode Fix Root Causes).

## Batch and Stream

* A batch job reads immutable input and writes new output. Running it again gives the same result.
* A stream consumer commits its offset atomically with its output, or is idempotent.

# Gate: archcheck

* Run `archcheck --changed` from the project root after the change, next to crapper, dryer and mutator.
* Errors fail the gate: a Dependency Rule violation, I/O or a framework in a pure layer, a package cycle,
  a network call without a timeout, a file that does not parse.
* Warnings ask for a decision, not obedience: a dependency toward a less stable package, a type switch,
  deep inheritance, global state, a wall-clock duration, a naive datetime, a swallowed broad exception.
  Fix it, or mark the line `# archcheck: ignore[rule] reason` and say why.
* Configure layers in `pyproject.toml` under `[tool.archcheck]` once the project has more than one layer.
  Without layers the other checks still run.
* Report the archcheck result together with the other gates.

# Practice

* Record a decision when you choose a boundary, a store, a consistency guarantee or a pattern: one paragraph
  in the commit message, or `docs/adr/NNNN-title.md` when the project keeps ADRs.
* Name packages, use cases and ports in the words of the domain glossary (ub-mode Model the Domain).
