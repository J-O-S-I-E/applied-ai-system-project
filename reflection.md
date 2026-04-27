# PawPal+ Project Reflection

---

## 1. System Design

**a. Initial design**

Before writing any code, I identified three core actions a user should be able to perform:

1. **Add a pet** — The user needs to register a pet (name, species, age) so that care
   tasks can be associated with it. Without this, the system has nothing to schedule.

2. **Add a care task** — The user needs to create a task (e.g. "Morning walk", 30 min,
   HIGH priority) and assign it to a pet. Tasks are the central unit of data in PawPal+.

3. **View today's scheduled tasks** — The user needs to see a prioritized, time-ordered
   list of what needs to happen today. This is the app's main output and the reason
   scheduling logic exists.

These three actions map to the four main classes I built:

- **Task** — represents a single care activity. It holds everything needed to describe
  the work: what it is, how long it takes, how urgent it is, and whether it repeats.
  It knows how to mark itself done and generate the next occurrence if it is recurring.

- **Pet** — represents one of the owner's animals. It owns a list of Task objects and
  provides filtered views of them (e.g. pending only, high-priority only). It does not
  know anything about scheduling — that is not its job.

- **Owner** — represents the person using the app. It owns a list of Pets and knows
  the daily time window the owner is available. It can aggregate all pending tasks
  across all pets into one flat list for the Scheduler to use.

- **Scheduler** — the "brain." It takes an Owner, pulls all pending tasks, sorts and
  filters them, assigns time slots, detects conflicts, and returns a ScheduleResult.
  It holds no data of its own beyond a reference to the Owner — all state lives in
  the Owner/Pet/Task layer.

- **ScheduleResult** — a clean return object from the Scheduler. It holds the scheduled
  tasks, any skipped tasks, any conflict warnings, and a utilization percentage. Keeping
  this separate from Scheduler makes the output easy to display in both the CLI and the
  Streamlit UI.

The key design decision was to separate data (Owner → Pet → Task) from logic
(Scheduler). This means the Scheduler can be tested independently and the UI can
display data without knowing how it was scheduled.

**b. Design changes**

After asking Copilot to review my class skeletons, I made the following changes:

1. **Added `task_id` to Task** — Copilot pointed out that without a unique identifier,
   removing a specific task from a pet's list would require matching on title, which
   breaks if two tasks have the same name. I added a `task_id` field using
   `uuid.uuid4()` as the default factory.

2. **Added `ScheduleResult` as a separate dataclass** — Initially I planned to return
   a plain dictionary from `build_schedule()`. Copilot suggested a typed return object
   would make the UI code cleaner and prevent key-error bugs. I agreed and added
   `ScheduleResult` with typed fields.

3. **Kept `available_start` and `available_end` as strings on Owner** — Copilot
   suggested converting them to `datetime.time` objects immediately. I decided against
   this because string inputs are simpler to collect from the Streamlit UI and the
   conversion can happen inside the Scheduler when needed.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

The scheduler considers three constraints:

1. **Time window** — the owner's `available_start` and `available_end` define the hard
   outer boundary of the day. No task can be scheduled before the window opens or after
   it closes. Any task that would overflow the end time is skipped entirely rather than
   partially scheduled.

2. **Priority** — tasks are sorted HIGH → MEDIUM → LOW before any time slots are
   assigned. This means a HIGH priority task is always placed before a MEDIUM one,
   regardless of preferred time. If the window fills up, it is always the lowest
   priority tasks that get skipped first.

3. **Preferred time** — tasks can carry a hint ("morning", "afternoon", "evening") that
   nudges the scheduler toward a specific part of the day. This is a soft constraint —
   the scheduler respects it only if the slot is still available after higher-priority
   tasks have been placed.

Priority was chosen as the dominant constraint because the core promise of the app is
that the most important care tasks always happen. Time preferences are a convenience,
not a guarantee — a pet's medication matters more than whether it happens at a
preferred hour.

**b. Tradeoffs**

The scheduler uses a greedy, first-fit algorithm: it processes tasks in priority order
and assigns each one the next available slot, never backtracking.

The tradeoff is this: a single large HIGH priority task can push several smaller MEDIUM
tasks out of the window entirely, even if those smaller tasks could have collectively
fit in the time the large task consumed. For example, a 90-minute vet appointment
scheduled in the morning might cause three 10-minute feeding tasks to be skipped —
even though 30 minutes of space was available elsewhere in the day.

This tradeoff is reasonable for a daily pet care schedule because simplicity matters.
A greedy algorithm is easy to understand, test, and debug. An owner reading the output
can predict exactly why each task landed where it did. It is better to guarantee that
HIGH priority tasks always run than to squeeze in an extra low-priority task through
complex rescheduling.

The conflict detector uses a nested loop that compares every pair of tasks (O(n²)).
Copilot suggested replacing it with a sort-then-single-pass approach (O(n log n)) which
is faster but only catches overlaps between adjacent tasks after sorting — it would miss
a case where task 1 and task 3 overlap but task 2 sits between them. I kept the nested
loop because correctness matters more than performance for a schedule with 5–15 tasks.
The speed difference at that scale is measured in microseconds.

---

## 3. AI Collaboration

**a. How you used AI**

AI was used in three distinct ways across the project:

- **Design brainstorming (Phase 1)** — Copilot Chat was used to generate the initial
  Mermaid.js UML diagram from a plain-English description of the four classes. This was
  useful for quickly visualizing relationships (Owner → Pet → Task) before writing any
  code. The most effective prompt style was specific and constrained: "Generate a
  Mermaid.js classDiagram for these four classes with these attributes and methods"
  produced a much cleaner result than a vague "design a pet app."

- **Scaffolding (Phase 2)** — Inline Chat was used to flesh out method bodies from stub
  signatures. Prompts that referenced the file directly (`#file:pawpal_system.py`) gave
  better results than prompts written in isolation, because Copilot could see the
  surrounding class context and match the existing code style.

- **Docstrings (Phase 2, Step 4)** — Inline Chat generated first-draft docstrings for
  each method. This was the fastest use of AI in the project — clicking through each
  method and accepting or editing a one-liner took far less time than writing them all
  from scratch.

The most consistently helpful prompt pattern was: give context, state the constraint,
ask for one specific thing. For example: "In #file:pawpal_system.py, the Scheduler.
_assign_times method needs to respect preferred_time hints without crashing if the hint
is None. Suggest an implementation." Vague prompts like "make the scheduler smarter"
produced unfocused suggestions that required significant editing.

**b. Judgment and verification**

During Phase 1, after asking Copilot to review the class skeletons, it suggested adding
a `validate_time_format()` method to the `Owner` class that would raise a `ValueError`
if `available_start` or `available_end` were not in "HH:MM" format.

This was not accepted for two reasons:

1. **Scope** — input validation belongs at the UI boundary (Streamlit), not inside the
   domain model. The `Owner` class should represent a valid owner, not police how data
   enters the system. Mixing those responsibilities would make `Owner` harder to test
   and reuse.

2. **Timing** — adding validation in Phase 1 before the UI existed meant validating
   against a format that might change. The Streamlit `st.text_input` widget was always
   going to enforce the format visually; a backend exception would be redundant.

The suggestion was evaluated by asking: where does bad data actually enter the system?
The answer was the UI form, not the `Owner` constructor. That reasoning justified
keeping `Owner` simple and deferring any format checking to the Streamlit layer.

During Phase 4, Copilot suggested replacing the nested-loop conflict detector with a
sort-then-single-pass version. I tested both approaches mentally against the edge case
of non-adjacent overlapping tasks and found the single-pass version would miss them.
I kept the original and documented the reasoning in Section 2b.

---

## 4. Testing and Verification

**a. What you tested**

I identified five core behaviors to verify:

1. **Task completion** — `mark_done()` correctly flips `completed` to `True` and returns
   `None` for non-recurring tasks. A completed task no longer appears in
   `pending_tasks()`.

2. **Task addition** — `add_task()` increases the pet's task count and the task appears
   in both `pet.tasks` and `pet.pending_tasks()`.

3. **Sorting correctness** — `sort_by_priority()` returns tasks in HIGH → MEDIUM → LOW
   order with ties broken by shortest duration. `sort_by_time()` returns tasks in
   chronological order by `scheduled_start`.

4. **Recurrence logic** — completing a recurring task with a `scheduled_start` creates
   a next-day clone and appends it to the pet. Completing a recurring task without a
   `scheduled_start` safely returns `None` without crashing.

5. **Conflict detection** — overlapping tasks produce a warning string containing both
   task names. Back-to-back tasks (one ends exactly when the next begins) produce zero
   warnings.

These tests matter because they cover the three places where a bug would cause the most
visible damage to a user: wrong task order in the schedule, missing recurring tasks, and
false conflict warnings.

Edge cases tested: empty pet with no tasks, availability window too short for any task,
two tasks starting at the exact same time, and a recurring task with no scheduled time.

**b. Confidence**

I am confident the core scheduling behaviors work correctly — the five test categories
above cover the main happy paths and the most likely failure modes. The test suite
gives me high confidence that priority sorting, task addition, and conflict detection
are correct.

The areas I am less certain about are interactions between features: for example,
what happens if a recurring task is completed and the cloned task conflicts with an
existing task on the next day. If I had more time, I would test the following edge
cases next:

- Two recurring tasks that generate clones landing in the same time slot
- An owner with zero pets calling `build_schedule()`
- Tasks whose `preferred_time` hint falls outside the owner's availability window
- A pet whose all tasks are already completed before scheduling runs

---

## 5. Reflection

**a. What went well**

The separation between the logic layer (`pawpal_system.py`) and the UI layer (`app.py`)
worked well from the start. Because the Scheduler held no data of its own and all state
lived in Owner → Pet → Task, it was straightforward to test the backend independently
via `demo.py` before touching Streamlit. When UI bugs appeared, I could always rule out
the backend by running the CLI demo first.

**b. What you would improve**

If I had another iteration, I would add JSON persistence so that pets and tasks survive
a browser refresh. Currently, refreshing the Streamlit page wipes all session state.
I would also split the single `app.py` file into separate pages using Streamlit's
multipage feature — one page for setup, one for scheduling, one for managing completed
tasks — to reduce scrolling and make the app feel more polished.

I would also make the conflict detection smarter: instead of just warning about
overlaps, the UI could suggest the next available slot and offer a one-click reschedule.

**c. Key takeaway**

The most important thing I learned is that AI is most useful when you already have a
clear design in mind. When I gave Copilot a specific method signature and a concrete
constraint ("don't crash if preferred_time is None"), it produced usable code
immediately. When I asked open-ended questions without context, the suggestions needed
significant editing. Being the lead architect meant knowing what to ask for — not just
accepting whatever was generated. The AI accelerated the writing; the design decisions
were still mine to make.