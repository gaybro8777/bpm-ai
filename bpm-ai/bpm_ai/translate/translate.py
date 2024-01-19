from bpm_ai_core.llm.common.llm import LLM
from bpm_ai_core.llm.common.message import ToolCallsMessage
from bpm_ai_core.llm.common.tool import Tool
from bpm_ai_core.prompt.prompt import Prompt
from bpm_ai_core.speech.stt.stt import STTModel
from bpm_ai_core.tracing.decorators import trace

from bpm_ai.common.multimodal import prepare_audio
from bpm_ai.translate.schema import get_translation_output_schema


@trace("bpm-ai-translate")
def run_translate(
    llm: LLM,
    input_data: dict[str, str | dict],
    target_language: str,
    stt: STTModel | None = None
) -> dict:
    tool = Tool.from_callable(
        "store_translation",
        f"Stores the finished translation into {target_language}.",
        args_schema=get_translation_output_schema(input_data, target_language),
        callable=lambda **x: x
    )

    #input_data = prepare_images(input_data)  todo enable once GPT-4V is stable
    input_data = prepare_audio(input_data, stt)

    prompt = Prompt.from_file(
        "translate",
        input=input_data
    )

    result = llm.predict(prompt, tools=[tool])

    if isinstance(result, ToolCallsMessage):
        return result.tool_calls[0].invoke()
    else:
        return {}



