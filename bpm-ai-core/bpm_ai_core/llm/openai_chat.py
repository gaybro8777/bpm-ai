import json
from typing import Dict, Any, Optional, List
import logging

from bpm_ai_core.llm.common.llm import LLM
from bpm_ai_core.llm.common.message import ChatMessage, ToolCallsMessage, SingleToolCallMessage
from bpm_ai_core.llm.common.tool import Tool
from bpm_ai_core.util.openai import messages_to_openai_dicts, json_schema_to_openai_function

logger = logging.getLogger(__name__)

try:
    from openai import AsyncOpenAI, APIConnectionError, InternalServerError, RateLimitError, OpenAIError
    from openai.types.chat import ChatCompletionMessage, ChatCompletion
    import httpx

    has_openai = True
    try:
        client = AsyncOpenAI(
            http_client=httpx.AsyncClient(
                limits=httpx.Limits(max_connections=1000, max_keepalive_connections=100)
            ),
            max_retries=0  # we use own retry logic
        )
    except OpenAIError as e:
        logger.error(e)
except ImportError:
    has_openai = False


class ChatOpenAI(LLM):
    """
    `OpenAI` Chat large language models API.

    To use, you should have the ``openai`` python package installed, and the
    environment variable ``OPENAI_API_KEY`` set with your API key.
    """

    def __init__(
        self,
        model: str = "gpt-3.5-turbo-0125",
        temperature: float = 0.0,
        seed: Optional[int] = None,
        max_retries: int = 8
    ):
        if not has_openai:
            raise ImportError('openai is not installed')
        super().__init__(
            model=model,
            temperature=temperature,
            max_retries=max_retries,
            retryable_exceptions=[
                RateLimitError, InternalServerError, APIConnectionError
            ]
        )
        self.seed = seed

    async def _predict(
        self,
        messages: List[ChatMessage],
        output_schema: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Tool]] = None
    ) -> ChatMessage:
        openai_tools = []
        if output_schema:
            tools = [Tool.from_callable(name="store_result", description="Stores your result", args_schema=output_schema)]
        if tools:
            openai_tools = [json_schema_to_openai_function(f.name, f.description, f.args_schema) for f in tools]
        completion = await self._run_completion(messages, openai_tools)

        message = completion.choices[0].message
        if message.tool_calls:
            if output_schema:
                return ChatMessage(role=message.role, content=self._load_tool_call_json(message))
            else:
                return self._openai_tool_calls_to_tool_message(message, tools)
        else:
            return ChatMessage(role=message.role, content=message.content)

    async def _run_completion(self, messages: List[ChatMessage], functions: List[dict]) -> ChatCompletion:
        args = {
            "model": self.model,
            "temperature": self.temperature,
            **({"seed": self.seed} if self.seed else {}),
            "messages": messages_to_openai_dicts(messages),
            **({
                   "tool_choice": {
                       "type": "function",
                       "function": {"name": functions[0]["function"]["name"]}
                   } if (len(functions) == 1) else ("auto" if functions else "none"),
                   "tools": functions
               } if functions else {})
        }
        return await client.chat.completions.create(**args)

    @staticmethod
    def _openai_tool_calls_to_tool_message(message: ChatCompletionMessage, tools: List[Tool]) -> ToolCallsMessage:
        return ToolCallsMessage(
            name=", ".join([t.function.name for t in message.tool_calls]),
            content=message.content,
            tool_calls=[
                SingleToolCallMessage(
                    id=t.id,
                    name=t.function.name,
                    payload=t.function.arguments,
                    tool=next((item for item in tools if item.name == t.function.name), None)
                )
                for t in message.tool_calls
            ]
        )

    @staticmethod
    def _load_tool_call_json(message: ChatCompletionMessage):
        try:
            json_object = json.loads(message.tool_calls[0].function.arguments)
        except ValueError as e:
            json_object = None
        return json_object

    def supports_images(self) -> bool:
        return "vision" in self.model

    def supports_audio(self) -> bool:
        return False

    def name(self) -> str:
        return "openai"
