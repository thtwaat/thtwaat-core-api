"""AI Calling — telephony provider abstraction + call runtime.

Telephony Provider -> Incoming Call -> Call Session (a Conversation with
channel="call") -> AgentRuntime.run_turn() -> Telephony Provider -> Caller.
"""
