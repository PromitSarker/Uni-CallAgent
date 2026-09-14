from agent.tools import (
	escalate,
	search_knowledge_base,
	save_collected_information,
	send_verification_email,
	write_to_chat,
	end_call
)

# Map function names to the actual implementations
LIVE_TOOLS_MAP = {
	"escalate": escalate.invoke,
	"search_knowledge_base": search_knowledge_base.invoke,
	"save_collected_information": save_collected_information.invoke,
	"send_verification_email": send_verification_email.invoke,
	"write_to_chat": write_to_chat.invoke,
	"end_call": end_call.invoke,
}

# Declarations formatted for Gemini's Multimodal Live API
LIVE_TOOL_DECLARATIONS = [
	{
		"name": "escalate",
		"description": "Use this tool when the user has a complex request, complaint, or wants to talk to a human. It will signal the system to transfer the conversation to a human support agent.",
		"parameters": {
			"type": "OBJECT",
			"properties": {
				"reason": {
					"type": "STRING",
					"description": "The reason for the escalation."
				}
			},
			"required": ["reason"]
		}
	},
	{
		"name": "search_knowledge_base",
		"description": "Search the knowledge base for general information, policies, or FAQs. Use this when the user asks a general question about Unified Cloud, its services, policies, or pricing.",
		"parameters": {
			"type": "OBJECT",
			"properties": {
				"query": {
					"type": "STRING",
					"description": "The search query to look up in the knowledge base."
				}
			},
			"required": ["query"]
		}
	},
	{
		"name": "save_collected_information",
		"description": "Save pieces of information gathered from the user (e.g., for IT services, lead gen, etc). Pass a dictionary mapping the exact requested keys to the user's provided values.",
		"parameters": {
			"type": "OBJECT",
			"properties": {
				"data": {
					"type": "OBJECT",
					"description": "A dictionary mapping the exact requested keys to the user's provided values."
				}
			},
			"required": ["data"]
		}
	},
	{
		"name": "send_verification_email",
		"description": "Generate a temporary password (verification code) and send it to the user's email. Use this when a user provides their email to log in or verify their identity.",
		"parameters": {
			"type": "OBJECT",
			"properties": {
				"email": {
					"type": "STRING",
					"description": "The user's email address."
				}
			},
			"required": ["email"]
		}
	},
	{
		"name": "write_to_chat",
		"description": "Write a message directly to the text chat interface for the user to see. Use this when the user asks you to \"write it down\", \"spell it\", or provide detailed text (like a price list or link) during a voice call.",
		"parameters": {
			"type": "OBJECT",
			"properties": {
				"message": {
					"type": "STRING",
					"description": "The message text you want to output into the chatbox."
				}
			},
			"required": ["message"]
		}
	},
	{
		"name": "end_call",
		"description": "End the current voice call. Use this when the conversation has naturally concluded or when the user explicitly asks to hang up or end the call. ALWAYS ask for confirmation before calling this tool.",
		"parameters": {
			"type": "OBJECT",
			"properties": {}
		}
	}
]

def get_live_tools():
	"""Returns the tools formatted for Gemini Multimodal Live API"""
	return [{"functionDeclarations": LIVE_TOOL_DECLARATIONS}]
