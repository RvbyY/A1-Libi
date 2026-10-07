# Feature: Scheduled AI Tasks

## General Information

**Feature ID:** T1  
**Category:** Tools / UX  
**Owner:** Noé  
**Status:** Done

---

## Catalogue Reference

**Official feature name:**  
Scheduled AI Tasks

**Catalogue description:**  
The assistant can register tasks that should be executed later or repeatedly, persist them, and run them at the appropriate time.

**How our implementation matches it:**  
SensAI supports scheduled AI tasks through the `/schedule` CLI command. Tasks are persisted in the database as `ScheduledTask` records and executed by a background `TaskRunner`. Scheduled prompts reuse the existing SensAI chat/Ollama execution flow.

---

## Why This Feature?

This feature allows users to ask SensAI to execute prompts later instead of only responding immediately during a live conversation.

It is useful for learning workflows, reminders, recurring summaries, and repeated AI-generated exercises.

### Real-World Use Case

A user learning Japanese can ask SensAI to generate a short quiz every day at 18:00 or remind them in 30 minutes to revise kanji.

---

## User Story 1

**As a** SensAI user,  
**I want to** schedule a one-time AI task from the terminal,  
**so that** SensAI can execute a prompt later without me manually asking again.

### Acceptance Criteria

- [x] `/schedule at HH:MM <prompt>` creates a one-time task.
- [x] `/schedule in <duration> <prompt>` creates a one-time relative task.
- [x] The task is persisted in the database.
- [x] The scheduler executes the task when it becomes due.
- [x] The task status is updated after execution.

---

## User Story 2

**As a** SensAI user,  
**I want to** create recurring scheduled AI tasks,  
**so that** SensAI can automatically repeat useful prompts over time.

### Acceptance Criteria

- [x] `/schedule every <duration> <prompt>` creates a recurring interval task.
- [x] `/schedule daily HH:MM <prompt>` creates a daily recurring task.
- [x] `/schedule weekly <day> HH:MM <prompt>` creates a weekly recurring task.
- [x] Recurring tasks are re-scheduled after execution.
- [x] Recurring tasks remain active with status `pending`.

---

## Technical Approach

### How will we implement it?

The scheduling feature is split into four parts:

1. A SQLAlchemy model, `ScheduledTask`, persists scheduled prompts.
2. `TaskManager` provides task creation, due-task lookup, cancellation, status updates, and recurring re-scheduling.
3. `TaskRunner` runs independently from the REPL loop and periodically executes due tasks.
4. `ScheduleCommand` exposes the feature through the CLI command framework.

The scheduler reuses the existing SensAI chat flow by executing scheduled prompts through the same agent/Ollama path as normal user prompts.

### Main files / components

- `src/galerelm/models/scheduled_task.py` — SQLAlchemy model for persisted scheduled tasks.
- `src/scheduler/task_manager.py` — scheduling domain logic and database operations.
- `src/scheduler/runner.py` — background runner that detects and executes due tasks.
- `src/commands/schedule.py` — `/schedule` CLI command parser and task creation logic.
- `src/commands/__init__.py` — registration of `ScheduleCommand`.
- `src/main.py` — starts the scheduler runner in a background thread.
- `src/galerelm/unit_tests/test_scheduled_task.py` — unit tests for scheduling persistence and status behavior.

### Dependencies

- SQLAlchemy
- SQLite
- Existing SensAI chat/Ollama execution flow
- Existing CLI command framework

---

## Technical Decisions

**Chosen approach:**  
Use a persisted `ScheduledTask` model with a background runner and a CLI command wrapper.

**Why we chose it:**  
This keeps scheduling logic separated from the chatbot loop while still allowing scheduled prompts to reuse the existing AI agent flow. Persistence also allows tasks to be tracked reliably in the database.

**Alternative considered:**  
Implement scheduling directly inside the REPL loop.

**Why we did not choose it:**  
Putting scheduling directly in the REPL would mix terminal input logic with background task execution. It would also make recurrence, task status, and future extensions harder to maintain.

---

## Testing

- [x] Normal case works
- [x] Edge case works
- [x] Failure case is handled
- [x] User Story 1 passes
- [x] User Story 2 passes

### Important test cases

1. Creating a scheduled task stores it with status `pending`.
2. Due tasks are returned by `TaskManager.get_due_tasks()`.
3. Future tasks are not returned as due.
4. Completed tasks are marked as `completed`.
5. Cancelled tasks are marked as `cancelled`.
6. Relative schedules such as `in 10s` execute successfully in the CLI.
7. Recurring schedules such as `every 10s` are re-scheduled after execution.

---

## Limitations

- There is no dedicated CLI command yet to list scheduled tasks.
- There is no dedicated CLI command yet to cancel scheduled tasks.
- Recurring tasks can currently be cancelled manually by updating their status to `cancelled` in the database.
- Terminal output can be visually interrupted when a scheduled task prints while the user is typing.

---

## Demo / Keynote

**Scenario:**  
A user schedules SensAI to execute a prompt automatically from the CLI.

**What we will demonstrate:**  

- `/schedule in 10s dis bonjour`
- SensAI persists the task.
- The background runner detects the due task.
- The scheduled prompt is executed through the existing chat/Ollama flow.
- A recurring task such as `/schedule every 10s dis bonjour` is re-scheduled after execution.

**Technical point to explain:**  
The scheduling system is independent from the REPL loop and uses `TaskManager` plus `TaskRunner` to keep scheduling logic separated from command parsing and chat execution.

**Backup:**  

- [ ] Screenshot
- [ ] Recording

---

## Definition of Done

- [x] Catalogue requirements are satisfied
- [x] Two user stories are complete
- [x] Acceptance criteria pass
- [x] Feature is integrated
- [x] Tests pass
- [x] README is updated
- [x] Demo is ready