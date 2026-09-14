from typing import Any, Dict, List, Union

from langchain_core.tools import tool
from pydantic import BaseModel

from agent.db import get_connection


@tool
def escalate(reason: str) -> str:
	"""
	Use this tool when the user has a complex request, complaint, or wants to talk to a human.
	It will signal the system to transfer the conversation to a human support agent.
	
	Why it's needed: Bots shouldn't handle arguments or disputes! This acts like an "emergency exit"
	button for the LLM to easily hand the interaction over to real customer support.
	"""
	return "I am connecting you to a human agent who can assist with this request. They will be with you shortly!"


@tool
def search_knowledge_base(query: str) -> str:
	"""
	Search the knowledge base for general information, policies, or FAQs.
	
	Why it's needed: Use this when the user asks a general question about Unified Cloud, its services, policies, or pricing.
	"""
	from agent.rag import search_documents
	return search_documents(query)


class SaveCollectedInformationInput(BaseModel):
	data: Dict[str, str]
	session_id: str = "" # Injected by the system, LLM does not need to provide this.


@tool(args_schema=SaveCollectedInformationInput)
def save_collected_information(data: Dict[str, str], session_id: str = "") -> str:
	"""
	Save pieces of information gathered from the user (e.g., for IT services, lead gen, etc).
	Pass a dictionary mapping the exact requested keys to the user's provided values.
	Do NOT provide session_id, it is injected automatically.
	
	Why it's needed: When the user wants to buy a service or provide their information, use this tool to securely store all the details at once.
	"""
	if not session_id:
		return "ERROR: session_id is missing."
	
	if not data:
		return "ERROR: No data provided to save."
	
	saved_keys = []
	try:
		with get_connection() as conn:
			for key, value in data.items():
				cur = conn.execute("UPDATE collected_data SET value = ?, created_at = CURRENT_TIMESTAMP WHERE session_id = ? AND key = ?", (value, session_id, key))
				if cur.rowcount == 0:
					conn.execute("INSERT INTO collected_data (session_id, key, value) VALUES (?, ?, ?)", (session_id, key, value))
				saved_keys.append(key)
			conn.commit()
		return f"Successfully saved: {', '.join(saved_keys)}."
	except Exception as e:
		return f"ERROR: Could not save information: {str(e)}"


class SendVerificationEmailInput(BaseModel):
	email: str
	session_id: str = "" # Injected by the system, LLM does not need to provide this.


@tool(args_schema=SendVerificationEmailInput)
def send_verification_email(email: str, session_id: str = "") -> str:
	"""
	Generate a temporary password (verification code) and send it to the user's email.
	
	Why it's needed: When a user provides their email to log in or verify their identity, this tool generates a secure code and emails it to them.
	"""
	import random
	import string
	import resend
	from agent.config import RESEND_API_KEY
	
	# Generate 6-character random code
	code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
	
	# Save to DB (user_auth_codes and collected_data)
	auth_query = "INSERT INTO user_auth_codes (email, code) VALUES (?, ?)"
	collected_query = "INSERT INTO collected_data (session_id, key, value) VALUES (?, ?, ?)"
	
	try:
		with get_connection() as conn:
			conn.execute(auth_query, (email, code))
			if session_id:
				conn.execute(collected_query, (session_id, "Temporary Password", code))
			conn.commit()
	except Exception as e:
		return f"ERROR: Could not save verification code: {str(e)}"
	
	# Try sending email
	if RESEND_API_KEY:
		try:
			from agent.config import RESEND_FROM_EMAIL
			resend.api_key = RESEND_API_KEY
			params = {
				"from": f"Unified Cloud <{RESEND_FROM_EMAIL}>",
				"to": [email],
				"subject": "Unified Cloud Verification Code",
				"text": f"Hello,\n\nYour temporary password is: {code}\n\nIMPORTANT: This is a temporary password, and you need to change it immediately after you log in.\n\nThank you,\nUnified Cloud"
			}
			resend.Emails.send(params)
			return "Verification code successfully sent to email."
		except Exception as e:
			print(f"Failed to send email via Resend: {e}")
			return f"Code generated ({code}) but failed to send email due to Resend API error."
	else:
		print(f"MOCK EMAIL SENT TO {email}: Code is {code}")
		return "Verification code successfully generated and mock-sent (Resend API key not configured)."


class WriteToChatInput(BaseModel):
	message: str
	session_id: str = "" # Injected by the system, LLM does not need to provide this.


@tool(args_schema=WriteToChatInput)
def write_to_chat(message: str, session_id: str = "") -> str:
	"""
	Write a message directly to the text chat interface for the user to see.
	
	Why it's needed: Use this when the user asks you to "write it down", "spell it", or provide detailed text (like a price list or link) during a voice call.
	"""
	# The actual broadcasting logic is handled in proxy_gemini_to_client.
	# This function just acts as a stub to return success to the LLM.
	return "Message successfully written to chat."


@tool
def end_call() -> str:
	"""
	End the current voice call with the user.
	
	Why it's needed: Use this when the conversation has naturally concluded or when the user explicitly asks to hang up or end the call. ALWAYS ask for confirmation before calling this tool.
	"""
	return "Call ended successfully."
