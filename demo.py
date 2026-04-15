from aisdlc_solution_design_agent import build_solution_design_agent

agent = build_solution_design_agent()
session_id = agent.create_session()

state = agent.run_turn(
    "We need a solution-design assistant for AISDLC that supports multi-turn refinement.",
    session_id=session_id,
)

print(state.last_response)

state = agent.run_turn(
    "Make Option 2 more detailed and include security.",
    session_id=session_id,
)

print("\n--- Updated ---\n")
print(state.last_response)

state = agent.run_turn(
    "Export this to the Word section format.",
    session_id=session_id,
)

print("\n--- Export Payload ---\n")
print(state.last_response)
