state = getattr(tool_context, "state", {}) or {}

# Extract user message from multiple possible ADK keys
user_text = None
for key in ("input", "text", "message", "query", "user_message"):
    v = state.get(key) if isinstance(state, dict) else getattr(state, key, None)
    if isinstance(v, str) and v.strip():
        user_text = v.strip()
        break

# Fallback: some ADK builds store last message in tool_context.input.text
if not user_text and hasattr(tool_context, "input"):
    maybe_text = getattr(tool_context.input, "text", None)
    if isinstance(maybe_text, str) and maybe_text.strip():
        user_text = maybe_text.strip()
