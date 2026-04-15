from __future__ import annotations

import json
import os
import re
import unittest
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional
from urllib import error, request
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
# This version supports two modes:
# 1. Rule-based fallback engine that runs with only the Python stdlib
# 2. Portkey-backed LLM engine for real model inference
#
# Portkey env vars:
# - PORTKEY_API_KEY        (required for LLM mode)
# - PORTKEY_VIRTUAL_KEY    (required for LLM mode)
# - PORTKEY_BASE_URL       (optional, default: https://api.portkey.ai/v1)
# - PORTKEY_MODEL          (optional, default: gpt-4.1-mini)
# - PORTKEY_PROVIDER       (optional)
# - PORTKEY_METADATA_JSON  (optional JSON string)
# - PORTKEY_TRACE_ID       (optional)
# - PORTKEY_TIMEOUT_SECONDS(optional, default: 60)
# - USE_PORTKEY            (set to 1 to use Portkey in __main__)
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
# Engine interfaces and implementations
# -----------------------------
class BaseEngine:
    def detect_intent(self, latest_user_input: str, history: str) -> IntentResponse:
        raise NotImplementedError

    def generate_options(
        self,
        project_context: str,
        problem_statement: str,
        user_goal: str,
        assumptions: List[str],
        existing_options: Optional[List[SolutionOption]] = None,
    ) -> SolutionOptionsResponse:
        raise NotImplementedError

    def refine_option(
        self,
        project_context: str,
        current_option: SolutionOption,
        latest_user_input: str,
    ) -> SolutionOption:
        raise NotImplementedError


class RuleBasedEngine(BaseEngine):
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

        if existing_options and "compare" in lowered:
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
        request_text = latest_user_input.lower()

        refined.description = (
            refined.description
            + " It includes explicit session state handling, option-level revision support, and a predictable export contract for downstream document generation."
        )

        extra_pros: List[str] = []
        extra_dependencies: List[str] = []

        if "microservice" in request_text:
            refined.description += " In this refinement, the option is framed with independently deployable services, API contracts, and separate state management."
            extra_pros.append("Supports independent scaling of orchestration, retrieval, and export components")
            extra_dependencies.extend(["API gateway", "Service-to-service contracts"])

        if "detailed" in request_text or "detail" in request_text or "more" in request_text:
            extra_pros.append("Improved traceability for solution-option revisions")
            extra_dependencies.append("Option version tracking")
            refined.cons.append("Requires more design-time governance to avoid schema drift")

        if "security" in request_text:
            extra_dependencies.extend(["Authentication", "Authorization", "Audit logging"])
            extra_pros.append("Can enforce role-based access for project design sessions")

        refined.pros.extend(item for item in extra_pros if item not in refined.pros)
        refined.dependencies.extend(item for item in extra_dependencies if item not in refined.dependencies)
        refined.recommendation = (
            refined.recommendation
            + " Use this refined version when the project needs stronger control, clearer evolution paths, or higher-confidence export behavior."
        )
        return refined


class PortkeyLLMEngine(BaseEngine):
    """
    Portkey adapter using the OpenAI-compatible chat completions endpoint.
    Falls back to RuleBasedEngine when Portkey is not configured or the call fails.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        virtual_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        metadata_json: Optional[str] = None,
        trace_id: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("PORTKEY_API_KEY", "")
        self.virtual_key = virtual_key or os.getenv("PORTKEY_VIRTUAL_KEY", "")
        self.base_url = (base_url or os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")).rstrip("/")
        self.model = model or os.getenv("PORTKEY_MODEL", "gpt-4.1-mini")
        self.provider = provider or os.getenv("PORTKEY_PROVIDER", "")
        self.metadata_json = metadata_json or os.getenv("PORTKEY_METADATA_JSON", "")
        self.trace_id = trace_id or os.getenv("PORTKEY_TRACE_ID", "")
        self.timeout_seconds = timeout_seconds or int(os.getenv("PORTKEY_TIMEOUT_SECONDS", "60"))
        self.fallback_engine = RuleBasedEngine()

    def is_configured(self) -> bool:
        return bool(self.api_key and self.virtual_key)

    def detect_intent(self, latest_user_input: str, history: str) -> IntentResponse:
        fallback = self.fallback_engine.detect_intent(latest_user_input, history)
        system_prompt = (
            "You are an intent classifier for the AISDLC solution-design assistant. "
            "Return only compact JSON with keys: intent, target_option_name, user_goal. "
            "Valid intents: new_solution_design, refine_existing_option, change_architecture_pattern, compare_options, export_to_word, general_followup. "
            "Pick exactly one and preserve Option N references when present."
        )
        user_prompt = f"History:\n{history}\n\nLatest user input:\n{latest_user_input}"
        payload = self._chat_json(system_prompt, user_prompt, fallback=fallback.__dict__)

        intent_value = str(payload.get("intent", fallback.intent))
        valid_intents = {
            "new_solution_design",
            "refine_existing_option",
            "change_architecture_pattern",
            "compare_options",
            "export_to_word",
            "general_followup",
        }
        if intent_value not in valid_intents:
            intent_value = fallback.intent

        return IntentResponse(
            intent=intent_value,
            target_option_name=payload.get("target_option_name", fallback.target_option_name),
            user_goal=str(payload.get("user_goal", fallback.user_goal)),
        )

    def generate_options(
        self,
        project_context: str,
        problem_statement: str,
        user_goal: str,
        assumptions: List[str],
        existing_options: Optional[List[SolutionOption]] = None,
    ) -> SolutionOptionsResponse:
        fallback = self.fallback_engine.generate_options(
            project_context=project_context,
            problem_statement=problem_statement,
            user_goal=user_goal,
            assumptions=assumptions,
            existing_options=existing_options,
        )
        system_prompt = (
            "You are the AISDLC Solution Design Agent. Generate exactly 3 structured solution options as JSON. "
            "Ground the response in the supplied project context. "
            "Return only JSON with keys: options, overall_recommendation, assumptions. "
            "Each option must contain: name, description, pros, cons, dependencies, recommendation."
        )
        user_prompt = (
            f"Project context:\n{project_context}\n\n"
            f"Problem statement:\n{problem_statement}\n\n"
            f"User goal:\n{user_goal}\n\n"
            f"Existing assumptions:\n{json.dumps(assumptions)}"
        )
        payload = self._chat_json(system_prompt, user_prompt, fallback=fallback.to_dict())
        return self._coerce_solution_options_response(payload, fallback)

    def refine_option(
        self,
        project_context: str,
        current_option: SolutionOption,
        latest_user_input: str,
    ) -> SolutionOption:
        fallback = self.fallback_engine.refine_option(project_context, current_option, latest_user_input)
        system_prompt = (
            "You are refining exactly one solution option for AISDLC. "
            "Return only JSON with keys: name, description, pros, cons, dependencies, recommendation. "
            "Update only the requested option and preserve the schema."
        )
        user_prompt = (
            f"Project context:\n{project_context}\n\n"
            f"Current option:\n{json.dumps(current_option.to_dict(), indent=2)}\n\n"
            f"Refinement request:\n{latest_user_input}"
        )
        payload = self._chat_json(system_prompt, user_prompt, fallback=fallback.to_dict())
        return self._coerce_solution_option(payload, fallback)

    def _chat_json(self, system_prompt: str, user_prompt: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_configured():
            return fallback

        response_text = self._chat(system_prompt, user_prompt)
        if not response_text:
            return fallback

        parsed = self._extract_json_object(response_text)
        if isinstance(parsed, dict):
            return parsed
        return fallback

    def _chat(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "x-portkey-api-key": self.api_key,
            "x-portkey-virtual-key": self.virtual_key,
        }
        if self.provider:
            headers["x-portkey-provider"] = self.provider
        if self.trace_id:
            headers["x-portkey-trace-id"] = self.trace_id
        if self.metadata_json:
            headers["x-portkey-metadata"] = self.metadata_json

        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        req = request.Request(
            url=url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
            payload = json.loads(raw)
            return str(payload["choices"][0]["message"]["content"])
        except (error.HTTPError, error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError):
            return ""

    @staticmethod
    def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
        stripped = text.strip()
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{[\s\S]*\}", stripped)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None
        return None

    @staticmethod
    def _coerce_solution_option(payload: Dict[str, Any], fallback: SolutionOption) -> SolutionOption:
        try:
            return SolutionOption.from_dict(payload)
        except Exception:
            return fallback

    @staticmethod
    def _coerce_solution_options_response(
        payload: Dict[str, Any],
        fallback: SolutionOptionsResponse,
    ) -> SolutionOptionsResponse:
        try:
            raw_options = payload.get("options", [])
            options = [SolutionOption.from_dict(item) for item in raw_options if isinstance(item, dict)]
            if not options:
                return fallback
            overall_recommendation = str(payload.get("overall_recommendation", fallback.overall_recommendation))
            assumptions = payload.get("assumptions", fallback.assumptions)
            assumptions = [str(item) for item in assumptions] if isinstance(assumptions, list) else fallback.assumptions
            return SolutionOptionsResponse(
                options=options,
                overall_recommendation=overall_recommendation,
                assumptions=assumptions,
            )
        except Exception:
            return fallback


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
        engine: Optional[BaseEngine] = None,
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
# Builders
# -----------------------------
def build_solution_design_agent(
    use_portkey: bool = False,
    engine: Optional[BaseEngine] = None,
) -> AISDLCSolutionDesignAgent:
    if engine is not None:
        return AISDLCSolutionDesignAgent(engine=engine)
    if use_portkey:
        return AISDLCSolutionDesignAgent(engine=PortkeyLLMEngine())
    return AISDLCSolutionDesignAgent()


def build_portkey_solution_design_agent() -> AISDLCSolutionDesignAgent:
    return AISDLCSolutionDesignAgent(engine=PortkeyLLMEngine())


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


class TestPortkeyLLMEngine(unittest.TestCase):
    def test_portkey_engine_falls_back_when_not_configured(self) -> None:
        engine = PortkeyLLMEngine(api_key="", virtual_key="")
        self.assertFalse(engine.is_configured())
        intent = engine.detect_intent("Make Option 2 more detailed.", "")
        self.assertEqual(intent.intent, "refine_existing_option")
        self.assertEqual(intent.target_option_name, "Option 2")

    def test_build_portkey_agent_uses_portkey_engine(self) -> None:
        agent = build_solution_design_agent(use_portkey=True)
        self.assertIsInstance(agent.engine, PortkeyLLMEngine)

    def test_extract_json_object_handles_embedded_json(self) -> None:
        engine = PortkeyLLMEngine(api_key="x", virtual_key="y")
        parsed = engine._extract_json_object('prefix {"intent": "general_followup", "user_goal": "continue"} suffix')
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed["intent"], "general_followup")


if __name__ == "__main__":
    if os.getenv("RUN_TESTS", "1") == "1":
        unittest.main(argv=["ignored", "-v"], exit=False)

    use_portkey = os.getenv("USE_PORTKEY", "0") == "1"
    agent = build_solution_design_agent(use_portkey=use_portkey)
    session_id = agent.create_session()

    print("\nRunning with engine:", agent.engine.__class__.__name__)
    if isinstance(agent.engine, PortkeyLLMEngine):
        print("Portkey configured:", agent.engine.is_configured())

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
