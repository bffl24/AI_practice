🧩 Story: UNIT TEST COVERAGE – HMM_CALL_PREP_AGENT

Story ID: HMM-UT-001
Epic Link: HMM_CALL_PREP_AGENT_DEV
Story Points: 5
Priority: High
Assignee: <Your Name>
Labels: adk, pytest, unit-test, hmm_call_prep

🧠 User Story

As a developer,
I want to build and run comprehensive unit tests for the HMM Call Prep Agent
so that all logic paths — extractor, output formatting, and phone number handling — are validated and regression-safe.

✅ Acceptance Criteria

Tests cover all core behaviors of the hmm_call_prep agent:

Extractor logic (valid / invalid input handling).

Output logic (API failure and summarization stop rules).

Phone number display logic (single, multiple, and “Do Not Call” scenarios).

Tests run in local and ADK web environments (pytest + adk eval).

Coverage ≥ 90 % for agent.py and related prompt code.

All tests are deterministic (no external API calls or LLM variance).

Results integrated in CI pipeline.

📋 Sub-Tasks
🔹 Sub-Task 1: Build Extractor Logic Unit Tests

Mock topic_extractor to simulate valid and invalid extractions.

Verify correct ID propagation to PatientDataAggregator.get_patient_aggregated_data().

Validate short-circuit behavior for invalid topics (status=error, no aggregator call).

Commit file tests/test_hmm_call_prep_extractor.py.

🔹 Sub-Task 2: Build Output Logic Tests (API Failure Rules)

Validate HMM_CALL_PREP_AGENT_PROMPT includes failure lines:

“Data reception failed, please attempt again.”

Stop summarization after API failure.

Test correct response object structure for API failure inputs.

Commit file tests/test_hmm_call_prep_output_logic.py.

🔹 Sub-Task 3: Build Phone Number Logic Tests

Create prompt-level assertions for:

Primary number display.

Alternate numbers (≥3 entries).

“Do Not Call” handling.

Empty fallback.

(Optional) Implement and test format_contact_information() helper.

Commit file tests/test_hmm_call_prep_phone_logic.py.

🔹 Sub-Task 4: ADK Evalset Creation

Launch adk web and run clean interactions for each scenario:

Valid extractor flow.

Invalid extractor.

API failure.

Phone logic cases.

Save each session as an eval in hmm_call_prep_unit.evalset.json.

Configure expected outputs and run evaluation to baseline results.

🔹 Sub-Task 5: CI Integration and Reporting

Add pytest and pytest-asyncio commands to CI job.

Include coverage report and artifacts upload.

Verify ADK evalset re-run after each commit (adk eval <evalset>).

Ensure pass/fail metrics visible in pipeline.

🧾 Definition of Done (DoD)

All subtasks completed and merged to main branch.

Test suite passes in both local and CI environments.

Evalset executes successfully with ≥ 95 % pass rate.

Coverage report attached to the story.

Code review approved and linked to this JIRA story.
