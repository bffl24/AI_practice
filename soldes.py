from __future__ import annotations

import json
import os
import re
import unittest
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4


# ============================================================
# AISDLC Solution Design Agent
# ------------------------------------------------------------
# Purpose:
# - Detect solution-design intent
# - Maintain state for 20+ turns
# - Generate structured solution options
# - Refine only one option on follow-up
# - Return export-ready payload for a Word output engine
#
# Why this version exists:
# - The original implementation depended on langchain_core/langgraph,
#   which may not be installed in the runtime.
# - This file now runs with only the Python standard library.
# - A lightweight agent framework is implemented here so the behavior
#   still matches the AISDLC requirement.
#
# Notes:
# - Replace RuleBasedEngine with a real model adapter later if needed.
# - Replace SimpleProjectContextRetriever with your actual AISDLC RAG layer.
# ============================================================


# -----------------------------
# Structured schemas
# -----------------------------
@dataclass
class SolutionOption:
    name: str
    description: str
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SolutionOption":
        return cls(
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            pros=list(data.get("pros", [])),
            cons=list(data.get("cons", [])),
            dependencies=list(data.get("dependencies", [])),
            recommendation=str(data.get("recommendation", "")),
        )


@dataclass
class SolutionOptionsResponse:
    options: List[SolutionOption] = field(default_factory=list)
    overall_recommendation: str = ""
    assumptions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "options": [option.to_dict() for option in self.options],
            "overall_recommendation": self.overall_recommendation,
            "assumptions": list(self.assumptions),
        }


@dataclass
class ExportableWordSection:
    title: str = "Solution Options"
    options: List[SolutionOption] = field(default_factory=list)
    overall_recommendation: str = ""
    assumptions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "options": [option.to_dict() for option in self.options],
            "overall_recommendation": self.overall_recommendation,
            "assumptions": list(self.assumptions),
        }


IntentType = Literal[
    "new_solution_design",
    "refine_existing_option",
    "change_architecture_pattern",
    "compare_options",
    "export_to_word",
    "general_followup",
]


@dataclass
class IntentResponse:
    intent: IntentType
    target_option_name: Optional[str] = None
    user_goal: str = ""


@dataclass
class RetrievedContext:
    summary: str
    references: List[str]


@dataclass
class Message:
    role: Literal["user", "assistant"]
    content: str


@dataclass
class AgentState:
    session_id: str = field(default_factory=lambda: str(uuid4()))
    messages: List[Message] = field(default_factory=list)
    latest_user_input: str = ""
    detected_intent: str = "general_followup"
    target_option_name: Optional[str] = None
    user_goal: str = ""
    project_context: str = ""
    problem_statement: str = ""
    assumptions: List[str] = field(default_factory=list)
    options: List[SolutionOption] = field(default_factory=list)
    overall_recommendation: str = ""
    turn_count: int = 0
    export_payload: Dict[str, Any] = field(default_factory=dict)
    last_response: str = ""


# -----------------------------
# Context retriever
# -----------------------------
class SimpleProjectContextRetriever:
    """
    Replace this with your actual AISDLC retriever.

    Suggested production replacements:
    - vector DB retriever over uploaded project docs
    - hybrid search using title + semantic chunks
    - metadata filters by project = 'aisdlc'
    """

    def __init__(self) -> None:
        self.seed_context = (
            "AISDLC project context:\n"
            "- The assistant must support solution design intent.\n"
            "- It must maintain context across at least 20 turns.\n"
            "- Output must follow a stable structure: Name, Description, Pros, Cons, Dependencies, Recommendation.\n"
            "- A user can refine only one option in the same thread.\n"
            "- Output should be directly exportable into a Word document section.\n"
            "- Preferred architecture direction includes a stateful solution design microservice pattern.\n"
            "- Existing project style favors manager-orchestrator logic, clear delegation, and deterministic output formatting."
        )

    def retrieve(self, query: str) -> RetrievedContext:
        references = [
            "AISDLC requirement: structured solution options",
            "AISDLC requirement: 20-turn state retention",
            "AISDLC requirement: Word-exportable output",
        ]
        return RetrievedContext(summary=self.seed_context, references=references)


# -----------------------------
# Lightweight engine
# -----------------------------
class RuleBasedEngine:
    """
    A dependency-free stand-in for an LLM-based orchestration layer.
    It uses deterministic heuristics so the script runs anywhere.
    """

    def detect_intent(self, latest_user_input: str, history: str) -> IntentResponse:
        text = latest_user_input.strip()
        lowered = text.lower()
        target_option_name = self._extract_target_option_name(text)

        if any(phrase in lowered for phrase in ["export", "word section", "word output", "doc section"]):
            return IntentResponse(
                intent="export_to_word",
                target_option_name=target_option_name,
                user_goal="Export the current solution options in document-ready structure.",
            )

        if target_option_name and any(
            phrase in lowered
            for phrase in ["make", "refine", "expand", "detail", "improve", "update", "modify"]
        ):
            return IntentResponse(
                intent="refine_existing_option",
                target_option_name=target_option_name,
                user_goal="Refine only the requested option while preserving the others.",
            )

        if any(
            phrase in lowered
            for phrase in [
                "microservices",
                "microservice",
                "event-driven",
                "modular monolith",
                "service-oriented",
                "hexagonal",
            ]
        ):
            return IntentResponse(
                intent="change_architecture_pattern",
                target_option_name=target_option_name,
                user_goal="Reframe the design using the requested architecture pattern.",
            )

        if any(phrase in lowered for phrase in ["compare", "versus", "vs", "trade-off between"]):
            return IntentResponse(
                intent="compare_options",
                target_option_name=target_option_name,
                user_goal="Compare the available solution options and trade-offs.",
            )

        if any(
            phrase in lowered
            for phrase in ["solution", "option", "design", "architecture", "approach", "implement"]
        ):
            return IntentResponse(
                intent="new_solution_design",
                target_option_name=target_option_name,
                user_goal="Generate structured solution options grounded in AISDLC project context.",
            )

        return IntentResponse(
            intent="general_followup",
            target_option_name=target_option_name,
            user_goal="Continue the solution design discussion while preserving context.",
        )

    @staticmethod
    def _extract_target_option_name(text: str) -> Optional[str]:
        option_match = re.search(r"\boption\s*(\d+)\b", text, re.IGNORECASE)
        if option_match:
            return f"Option {option_match.group(1)}"

        quoted_match = re.search(r"['\"]([^'\"]+)['\"]", text)
        if quoted_match:
            candidate = quoted_match.group(1).strip()
            if candidate:
                return candidate

        return None

    def generate_options(
        self,
        project_context: str,
        problem_statement: str,
        user_goal: str,
        assumptions: List[str],
        existing_options: Optional[List[SolutionOption]] = None,
    ) -> SolutionOptionsResponse:
        style_hint = ""
        lowered = (user_goal + " " + problem_statement).lower()
        if "microservice" in lowered:
            style_hint = " using a microservices pattern"
        elif "event-driven" in lowered:
            style_hint = " using an event-driven pattern"
        elif "modular monolith" in lowered:
            style_hint = " using a modular monolith pattern"

        base_assumptions = list(assumptions) if assumptions else [
            "Project context is retrieved from AISDLC uploaded artifacts.",
            "The solution must preserve direct exportability into a Word document section.",
            "The assistant should maintain context for at least 20 turns in a single session.",
        ]

        options = [
            SolutionOption(
                name="Prompt-Driven Solution Designer",
                description=(
                    "A lightweight chat-first implementation that detects solution-design intent and generates "
                    f"structured options{style_hint}. It is fastest to deliver and suitable for a proof of concept."
                ),
                pros=[
                    "Fastest implementation path",
                    "Low infrastructure overhead",
                    "Simple integration into an existing chat interface",
                ],
                cons=[
                    "Less robust session control",
                    "Harder to audit refinement history",
                    "Formatting consistency depends heavily on prompt discipline",
                ],
                dependencies=[
                    "Intent detection",
                    "Prompt templates for solution options",
                    "Word output formatter",
                ],
                recommendation="Recommended only for an MVP or rapid validation phase.",
            ),
            SolutionOption(
                name="Manager-Orchestrated Solution Design Service",
                description=(
                    "A manager-style agent coordinates context retrieval, intent handling, selective refinement, and "
                    f"structured response generation{style_hint}. This aligns well with AISDLC's orchestration style."
                ),
                pros=[
                    "Clear separation of orchestration and content generation",
                    "Supports targeted refinement of individual options",
                    "Good balance of speed and maintainability",
                ],
                cons=[
                    "More engineering effort than a prompt-only approach",
                    "Needs explicit session-state handling",
                    "Requires schema validation between stages",
                ],
                dependencies=[
                    "Session manager",
                    "Context retriever",
                    "Option generation engine",
                    "Structured output schema",
                ],
                recommendation="Recommended as the best fit for near-term implementation in AISDLC.",
            ),
            SolutionOption(
                name="Stateful Solution Design Microservice",
                description=(
                    "A dedicated service manages multi-turn solution-design conversations, retains session state, "
                    f"supports selective option refinement, and returns document-ready payloads{style_hint}."
                ),
                pros=[
                    "Strongest multi-turn state management",
                    "Best support for revision history and auditability",
                    "Reliable Word-exportable contract",
                ],
                cons=[
                    "Highest implementation effort",
                    "Requires persistence and operational monitoring",
                    "Longer delivery timeline",
                ],
                dependencies=[
                    "Persistent session store",
                    "Context retrieval layer",
                    "Recommendation engine",
                    "Word export adapter",
                    "Observability stack",
                ],
                recommendation="Recommended when AISDLC needs a durable enterprise-grade capability.",
            ),
        ]

        if existing_options and any("compare" in lowered for _ in [0]):
            options = existing_options

        overall = (
            "Recommended approach: Manager-Orchestrated Solution Design Service for the first production iteration, "
            "with a later upgrade path to a Stateful Solution Design Microservice when scale, reuse, or auditability become priority requirements."
        )
        return SolutionOptionsResponse(options=options, overall_recommendation=overall, assumptions=base_assumptions)

    def refine_option(
        self,
        project_context: str,
        current_option: SolutionOption,
        latest_user_input: str,
    ) -> SolutionOption:
        refined = SolutionOption.from_dict(current_option.to_dict())
        request = latest_user_input.lower()

        refined.description = (
            refined.description
            + " It includes explicit session state handling, option-level revision support, and a predictable export contract for downstream document generation."
        )

        extra_pros = []
        extra_dependencies = []

        if "microservice" in request:
            refined.description += " In this refinement, the option is framed with independently deployable services, API contracts, and separate state management."
            extra_pros.append("Supports independent scaling of orchestration, retrieval, and export components")
            extra_dependencies.extend(["API gateway", "Service-to-service contracts"])

        if "detailed" in request or "detail" in request or "more" in request:
            extra_pros.append("Improved traceability for solution-option revisions")
            extra_dependencies.append("Option version tracking")
            refined.cons.append("Requires more design-time governance to avoid schema drift")

        if "security" in request:
            extra_dependencies.extend(["Authentication", "Authorization", "Audit logging"])
            extra_pros.append("Can enforce role-based access for project design sessions")

        refined.pros.extend(item for item in extra_pros if item not in refined.pros)
        refined.dependencies.extend(item for item in extra_dependencies if item not in refined.dependencies)
        refined.recommendation = (
            refined.recommendation
            + " Use this refined version when the project needs stronger control, clearer evolution paths, or higher-confidence export behavior."
        )
        return refined


# -----------------------------
# Utilities
# -----------------------------
def summarize_history(messages: List[Message], limit: int = 12) -> str:
    trimmed = messages[-limit:]
    return "\n".join(f"{msg.role}: {msg.content}" for msg in trimmed)


def normalize_option_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    return re.sub(r"\s+", " ", name.strip().lower())


def find_option(options: List[SolutionOption], target_option_name: Optional[str]) -> Optional[int]:
    if not options or not target_option_name:
        return None

    target = normalize_option_name(target_option_name)
    if not target:
        return None

    for idx, option in enumerate(options):
        if normalize_option_name(option.name) == target:
            return idx

    match = re.search(r"option\s*(\d+)", target)
    if match:
        pos = int(match.group(1)) - 1
        if 0 <= pos < len(options):
            return pos

    return None


def render_user_response(state: AgentState) -> str:
    chunks: List[str] = ["# Solution Options"]

    if state.assumptions:
        chunks.append("## Assumptions")
        for item in state.assumptions:
            chunks.append(f"- {item}")

    for idx, option in enumerate(state.options, start=1):
        chunks.append(f"## Option {idx}: {option.name}")
        chunks.append(f"**Description**\n{option.description}")

        chunks.append("**Pros**")
        chunks.extend(f"- {item}" for item in option.pros)

        chunks.append("**Cons**")
        chunks.extend(f"- {item}" for item in option.cons)

        chunks.append("**Dependencies**")
        chunks.extend(f"- {item}" for item in option.dependencies)

        chunks.append(f"**Recommendation**\n{option.recommendation}")

    if state.overall_recommendation:
        chunks.append("## Overall Recommendation")
        chunks.append(state.overall_recommendation)

    return "\n\n".join(chunks)


# -----------------------------
# Agent implementation
# -----------------------------
class AISDLCSolutionDesignAgent:
    def __init__(
        self,
        context_retriever: Optional[SimpleProjectContextRetriever] = None,
        engine: Optional[RuleBasedEngine] = None,
    ) -> None:
        self.context_retriever = context_retriever or SimpleProjectContextRetriever()
        self.engine = engine or RuleBasedEngine()
        self.sessions: Dict[str, AgentState] = {}

    def create_session(self) -> str:
        session_id = str(uuid4())
        self.sessions[session_id] = AgentState(session_id=session_id)
        return session_id

    def get_state(self, session_id: str) -> AgentState:
        if session_id not in self.sessions:
            self.sessions[session_id] = AgentState(session_id=session_id)
        return self.sessions[session_id]

    def run_turn(self, user_input: str, session_id: Optional[str] = None) -> AgentState:
        state = self.get_state(session_id or self.create_session())
        state.turn_count += 1
        state.latest_user_input = user_input

        retrieved = self.context_retriever.retrieve(user_input)
        state.project_context = retrieved.summary

        intent = self.engine.detect_intent(
            latest_user_input=user_input,
            history=summarize_history(state.messages),
        )
        state.detected_intent = intent.intent
        state.target_option_name = intent.target_option_name
        state.user_goal = intent.user_goal

        if intent.intent == "new_solution_design":
            if not state.problem_statement:
                state.problem_statement = user_input
            response = self.engine.generate_options(
                project_context=state.project_context,
                problem_statement=state.problem_statement,
                user_goal=state.user_goal,
                assumptions=state.assumptions,
                existing_options=state.options,
            )
            state.options = response.options
            state.assumptions = response.assumptions
            state.overall_recommendation = response.overall_recommendation
            state.last_response = render_user_response(state)

        elif intent.intent == "change_architecture_pattern":
            problem_statement = state.problem_statement or user_input
            response = self.engine.generate_options(
                project_context=state.project_context,
                problem_statement=problem_statement,
                user_goal=user_input,
                assumptions=state.assumptions,
                existing_options=state.options,
            )
            state.options = response.options
            state.assumptions = response.assumptions
            state.overall_recommendation = response.overall_recommendation
            state.last_response = render_user_response(state)

        elif intent.intent == "compare_options":
            if not state.options:
                response = self.engine.generate_options(
                    project_context=state.project_context,
                    problem_statement=state.problem_statement or user_input,
                    user_goal=state.user_goal,
                    assumptions=state.assumptions,
                    existing_options=state.options,
                )
                state.options = response.options
                state.assumptions = response.assumptions
                state.overall_recommendation = response.overall_recommendation
            comparison_lines = ["# Option Comparison"]
            for idx, option in enumerate(state.options, start=1):
                comparison_lines.append(
                    f"- Option {idx}: {option.name} | Pros: {len(option.pros)} | Cons: {len(option.cons)} | Dependencies: {len(option.dependencies)}"
                )
            comparison_lines.append("")
            comparison_lines.append(f"Recommendation: {state.overall_recommendation}")
            state.last_response = "\n".join(comparison_lines)

        elif intent.intent == "refine_existing_option":
            target_index = find_option(state.options, state.target_option_name)
            if target_index is None:
                state.last_response = (
                    "I could not identify which option to refine. "
                    "Please refer to it by exact name or say something like 'make Option 2 more detailed'."
                )
            else:
                state.options[target_index] = self.engine.refine_option(
                    project_context=state.project_context,
                    current_option=state.options[target_index],
                    latest_user_input=user_input,
                )
                state.last_response = render_user_response(state)

        elif intent.intent == "export_to_word":
            export = ExportableWordSection(
                options=state.options,
                overall_recommendation=state.overall_recommendation,
                assumptions=state.assumptions,
            )
            state.export_payload = export.to_dict()
            state.last_response = json.dumps(state.export_payload, indent=2)

        else:
            if not state.options:
                response = self.engine.generate_options(
                    project_context=state.project_context,
                    problem_statement=state.problem_statement or user_input,
                    user_goal=state.user_goal or user_input,
                    assumptions=state.assumptions,
                    existing_options=state.options,
                )
                state.options = response.options
                state.assumptions = response.assumptions
                state.overall_recommendation = response.overall_recommendation
            state.last_response = render_user_response(state)

        state.messages.append(Message(role="user", content=user_input))
        state.messages.append(Message(role="assistant", content=state.last_response))
        return state


# -----------------------------
# Backward-compatible helper
# -----------------------------
def build_solution_design_agent() -> AISDLCSolutionDesignAgent:
    return AISDLCSolutionDesignAgent()


# -----------------------------
# Tests
# -----------------------------
class TestAISDLCSolutionDesignAgent(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = build_solution_design_agent()
        self.session_id = self.agent.create_session()

    def test_new_solution_design_generates_three_options(self) -> None:
        state = self.agent.run_turn(
            "We need a chat interface for solution architects to co-design technical and business solutions.",
            session_id=self.session_id,
        )
        self.assertEqual(state.detected_intent, "new_solution_design")
        self.assertEqual(len(state.options), 3)
        self.assertTrue(state.last_response.startswith("# Solution Options"))

    def test_refine_option_updates_only_target(self) -> None:
        initial = self.agent.run_turn(
            "Design solution options for AISDLC.",
            session_id=self.session_id,
        )
        before_names = [opt.name for opt in initial.options]
        before_descriptions = [opt.description for opt in initial.options]

        updated = self.agent.run_turn(
            "Make Option 2 more detailed and include security.",
            session_id=self.session_id,
        )

        self.assertEqual(updated.detected_intent, "refine_existing_option")
        self.assertEqual([opt.name for opt in updated.options], before_names)
        self.assertEqual(updated.options[0].description, before_descriptions[0])
        self.assertNotEqual(updated.options[1].description, before_descriptions[1])
        self.assertEqual(updated.options[2].description, before_descriptions[2])
        self.assertIn("Authentication", updated.options[1].dependencies)

    def test_export_to_word_returns_json_payload(self) -> None:
        self.agent.run_turn("Design solution options for AISDLC.", session_id=self.session_id)
        state = self.agent.run_turn("Export this to the Word section format.", session_id=self.session_id)
        payload = json.loads(state.last_response)
        self.assertEqual(payload["title"], "Solution Options")
        self.assertEqual(len(payload["options"]), 3)

    def test_change_architecture_pattern_mentions_microservices(self) -> None:
        self.agent.run_turn("Design solution options for AISDLC.", session_id=self.session_id)
        state = self.agent.run_turn(
            "What would this look like using a microservices pattern?",
            session_id=self.session_id,
        )
        self.assertEqual(state.detected_intent, "change_architecture_pattern")
        self.assertTrue(any("microservices pattern" in option.description.lower() for option in state.options))

    def test_turn_count_persists_beyond_multiple_turns(self) -> None:
        for index in range(21):
            self.agent.run_turn(f"Turn {index}: continue the design discussion.", session_id=self.session_id)
        state = self.agent.get_state(self.session_id)
        self.assertEqual(state.turn_count, 21)
        self.assertGreaterEqual(len(state.messages), 42)

    def test_find_option_supports_option_number(self) -> None:
        options = [
            SolutionOption(name="First", description="a"),
            SolutionOption(name="Second", description="b"),
        ]
        self.assertEqual(find_option(options, "Option 2"), 1)
        self.assertIsNone(find_option(options, "Option 3"))

    def test_unknown_refinement_returns_helpful_message(self) -> None:
        self.agent.run_turn("Design solution options for AISDLC.", session_id=self.session_id)
        state = self.agent.run_turn("Refine Option 9.", session_id=self.session_id)
        self.assertIn("could not identify", state.last_response.lower())


if __name__ == "__main__":
    if os.getenv("RUN_TESTS", "1") == "1":
        unittest.main(argv=["ignored", "-v"], exit=False)

    agent = build_solution_design_agent()
    session_id = agent.create_session()

    prompts = [
        "We need a chat interface for solution architects to co-design business and technical solutions from uploaded project context.",
        "Make Option 2 more detailed.",
        "What would this look like using a microservices pattern?",
        "Export this to the Word section format.",
    ]

    for prompt in prompts:
        print("\nUSER:")
        print(prompt)
        state = agent.run_turn(prompt, session_id=session_id)
        print("\nASSISTANT:")
        print(state.last_response)
