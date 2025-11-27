import logging
from typing import List, Dict, Any, Optional

import ollama
from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """
    Service class for TinyLlama LLM integrations.

    Provides AI-powered features including:
    - Text summarization for RFQs and bids
    - Negotiation message generation
    - AI co-pilot chat functionality
    - Industry extraction
    """

    def __init__(self):
        """Initialize the Ollama client with TinyLlama."""
        self.client = ollama.AsyncClient(host=settings.ollama_base_url)
        self.model = settings.ollama_model

    async def _make_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Make a completion request to Ollama.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            max_tokens: Not used by Ollama python client directly in chat, but kept for interface compatibility
            temperature: Temperature for response

        Returns:
            str: AI response content

        Raises:
            Exception: If API call fails
        """
        try:
            options = {}
            if temperature is not None:
                options["temperature"] = temperature

            # Note: Ollama python client handles the API call
            response = await self.client.chat(
                model=self.model, messages=messages, options=options
            )

            content = response.get("message", {}).get("content")
            if not content:
                raise Exception("Empty response received from Ollama")

            return content.strip()

        except Exception as e:
            logger.error(f"Ollama API error: {str(e)}")
            raise Exception(f"Failed to get AI response: {str(e)}")

    async def summarize_text(self, text: str) -> str:
        """
        Generate a concise summary of the provided text.
        """
        if not text or not text.strip():
            return "No content to summarize."

        system_prompt = """Summarize this procurement document. Focus on key requirements, deadlines, and budget. Keep it brief."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Summarize this:\n\n{text}"},
        ]

        return await self._make_completion(messages, temperature=0.3)

    async def generate_negotiation_message(self, context: str, goal: str) -> str:
        """
        Generate a professional negotiation message.
        """
        if not context or not goal:
            raise Exception("Context and goal required.")

        system_prompt = """Write a professional negotiation message for procurement. Be persuasive and concise."""

        user_prompt = f"""Context: {context}
        Goal: {goal}
        Write the message:"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        return await self._make_completion(messages, temperature=0.6)

    async def chat_with_ai(
        self, rfq_context: str, history: List[Dict[str, str]], new_message: str
    ) -> str:
        """
        Provide AI co-pilot assistance.
        """
        if not new_message or not new_message.strip():
            raise Exception("Message cannot be empty.")

        system_prompt = f"""You are a procurement assistant. Context: {rfq_context}. Answer questions about procurement. Be helpful and concise."""

        messages = [{"role": "system", "content": system_prompt}]

        # Add history (Ollama handles context window, but good to limit)
        recent_history = history[-10:] if len(history) > 10 else history
        messages.extend(recent_history)

        messages.append({"role": "user", "content": new_message})

        return await self._make_completion(messages, temperature=0.7)

    async def extract_company_industry(self, company_description: str) -> List[str]:
        """
        Extract relevant industries from a company description.
        """
        if not company_description or not company_description.strip():
            return []

        system_prompt = """List 1-3 main industries for this company. Format: Industry1, Industry2"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": company_description},
        ]

        try:
            response = await self._make_completion(messages, temperature=0.3)
            industries = [ind.strip() for ind in response.split(",") if ind.strip()]
            return industries
        except Exception as e:
            logger.error(f"Failed to extract industries: {str(e)}")
            return []

    async def simple_chat(self, message: str) -> str:
        """
        Simple chat interface with TinyLlama.
        """
        if not message or not message.strip():
            return "Please provide a message."

        messages = [
            {"role": "user", "content": message}
        ]

        try:
            return await self._make_completion(messages, temperature=0.7)
        except Exception as e:
            logger.error(f"Chat error: {str(e)}")
            return "Sorry, I'm having trouble responding right now."


# Create service instance
llm_service = LLMService()
