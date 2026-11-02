import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import HTTPException
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from agent.graph import agent
from agent.nodes import summarize_conversation_node
from api.schemas import (
	ChatMessageRequest,
	ChatMessageResponse,
	ConversationHistoryResponse,
	ConversationMessage,
	HistorySummary,
	MessageState,
)
from api.store import conversation_store

_ALLOWED_INTENTS = {"inquiry", "lead", "escalate"}

# --- Background conversation summaries ---------------------------------------------
# The rolling summary is only needed for the *next* turn, so it is computed after the
# reply has been returned instead of blocking it with an extra LLM call.
# One worker => summaries run FIFO and can never finish out of order; a job whose
# conversation has already been re-submitted with newer messages is skipped.
_summary_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="summary")
_summary_lock = threading.Lock()
_summary_latest: Dict[str, int] = {}
_summary_counter = 0


def _summarize_in_background(conversation_id: str, state: Dict[str, Any]) -> None:
	global _summary_counter
	with _summary_lock:
		_summary_counter += 1
		ticket = _summary_counter
		_summary_latest[conversation_id] = ticket

	def job() -> None:
		try:
			with _summary_lock:
				superseded = _summary_latest.get(conversation_id) != ticket
			if superseded:
				return  # a newer turn will produce a more complete summary
			summarize_conversation_node(state)
		except Exception as e:
			print(f"Background summarize failed for {conversation_id}: {e}")
		finally:
			with _summary_lock:
				if _summary_latest.get(conversation_id) == ticket:
					_summary_latest.pop(conversation_id, None)

	try:
		_summary_executor.submit(job)
	except Exception as e:  # e.g. executor shut down during exit
		print(f"Could not schedule summary for {conversation_id}: {e}")


def _now_utc() -> datetime:
	return datetime.now(timezone.utc)


def _sanitize_input(text: str, max_length: int = 2000) -> str:
	"""Strip control characters and truncate to prevent prompt injection via token stuffing."""
	# Remove null bytes and non-printable control chars (keep newlines/tabs for readability)
	sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
	if len(sanitized) > max_length:
		sanitized = sanitized[:max_length]
	return sanitized.strip()


def _to_langchain_messages(messages: List[ConversationMessage]) -> List[BaseMessage]:
	lang_messages: List[BaseMessage] = []
	for message in messages:
		if message.role in ("assistant", "system"):
			lang_messages.append(AIMessage(content=message.content))
		else:
			lang_messages.append(HumanMessage(content=message.content))
	return lang_messages


def send_message(conversation_id: str, payload: ChatMessageRequest) -> ChatMessageResponse:
	user_message = _sanitize_input(payload.message)
	if not user_message:
		raise HTTPException(
			status_code=400,
			detail={
				"error": "INVALID_INPUT",
				"message": "message is required and must be a non-empty string",
			},
		)

	# Load prior conversation history
	try:
		history = conversation_store.get_messages(conversation_id)
	except Exception:
		raise HTTPException(
			status_code=503,
			detail={
				"error": "DEPENDENCY_FAILURE",
				"message": "Could not load conversation context right now",
			},
		)

	# Build the full message list: history + new user turn.
	# Because AgentState uses add_messages reducer, passing the complete list
	# here gives the LLM full context without the reducer double-appending.
	lang_messages = _to_langchain_messages(history)
	lang_messages.append(HumanMessage(content=user_message))

	try:
		session_summary = conversation_store.get_session_summary(conversation_id)
	except Exception:
		session_summary = ""

	state_input: Dict[str, Any] = {
		"conversation_id": conversation_id,
		"messages": lang_messages,
		"intent": None,
		"extracted_params": None,
		"missing_fields": None,
		"tool_result": None,
		"final_response": None,
		"escalate": False,
		"session_summary": session_summary,
	}

	# Invoke the LangGraph agent
	try:
		result_state = agent.invoke(state_input)
	except Exception as e:
		import traceback
		print(f"ERROR: Agent invocation failed: {e}")
		traceback.print_exc()
		raise HTTPException(
			status_code=503,
			detail={
				"error": "DEPENDENCY_FAILURE",
				"message": "Could not process message right now",
			},
		)

	intent = str(result_state.get("intent") or "escalate")
	if intent not in _ALLOWED_INTENTS:
		intent = "escalate"

	assistant_response = str(result_state.get("final_response") or "")
	escalate = bool(result_state.get("escalate", False))
	tool_result = result_state.get("tool_result")

	# Use distinct timestamps: user turn vs assistant reply
	user_timestamp = _now_utc()
	assistant_timestamp = _now_utc()

	# Persist both turns
	try:
		conversation_store.append(
			conversation_id,
			ConversationMessage(role="user", content=user_message, timestamp=user_timestamp),
		)
		conversation_store.append(
			conversation_id,
			ConversationMessage(
				role="assistant",
				content=assistant_response,
				timestamp=assistant_timestamp,
			),
			intent=intent,
			escalate=escalate,
		)
	except Exception:
		raise HTTPException(
			status_code=503,
			detail={
				"error": "DEPENDENCY_FAILURE",
				"message": "Could not store conversation right now",
			},
		)

	# Reply is ready and stored; update the rolling summary off the request path.
	_summarize_in_background(conversation_id, result_state)

	return ChatMessageResponse(
		conversation_id=conversation_id,
		intent=intent,  # type: ignore[arg-type]
		assistant_response=assistant_response,
		escalate=escalate,
		timestamp=assistant_timestamp,  # response timestamp = when assistant replied
	)


def get_history(conversation_id: str) -> ConversationHistoryResponse:
	try:
		exists = conversation_store.exists(conversation_id)
	except Exception:
		raise HTTPException(
			status_code=500,
			detail={
				"error": "HISTORY_READ_FAILED",
				"message": "Could not load conversation history",
			},
		)

	if not exists:
		raise HTTPException(
			status_code=404,
			detail={
				"error": "CONVERSATION_NOT_FOUND",
				"message": f"No history found for conversation_id {conversation_id}",
			},
		)

	try:
		messages = conversation_store.get_messages(conversation_id)
		last_intent = conversation_store.get_last_intent(conversation_id)
		escalate = conversation_store.get_escalate(conversation_id)
		session_summary = conversation_store.get_session_summary(conversation_id)
	except Exception:
		raise HTTPException(
			status_code=500,
			detail={
				"error": "HISTORY_READ_FAILED",
				"message": "Could not load conversation history",
			},
		)

	if last_intent not in _ALLOWED_INTENTS:
		last_intent = None

	return ConversationHistoryResponse(
		conversation_id=conversation_id,
		messages=messages,
		summary=HistorySummary(
			total_messages=len(messages),
			last_intent=last_intent,  # type: ignore[arg-type]
			escalate=escalate,
			session_summary=session_summary,
		),
	)
