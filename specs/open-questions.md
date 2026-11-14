# Open questions

Each item has an ID (`Q-NNN`), a status (`open`), the question, the planned fallback, and what it blocks. Agents MUST NOT close an item on assumption. Only a verified sandbox result or a user answer closes it. When closed, the row is **deleted** and its consequence is recorded in the affected spec or ADR (`specs/README.md` section 4).

## Verify early (non-blocking, but affect design)

| ID | Status | Question | Fallback | Blocks |
|---|---|---|---|---|
| Q-006 | open | Is the 9-instance limit real, and does `max_size = 4` fit? The Service Quotas API is denied for the lab role. | Lower `asg_max_size` to 3 | `INF-ASG-01` |

Creating a test resource to answer a question needs the user's approval for each test, unless the user has authorized sandbox tests in general. Evidence for closed questions is in `answered-questions.md`.

## Process and scheduling

| ID | Status | Question | Fallback | Blocks |
|---|---|---|---|---|
| Q-011 | open | The teammate uses another AI tool. Does it read `AGENTS.md` and `specs/` the same way? | Not blocking. Both tools must follow `AGENTS.md`. | First shared session |

## Notes

- Verification evidence (date and a CLI output summary) goes into the ADR or spec that the answer changes. Do not paste account IDs or credentials here.
