import logging

from PIL.Image import Image

from bpm_ai_core.question_answering.question_answering import QuestionAnswering, QAResult

try:
    from transformers import pipeline, AutoTokenizer
    has_transformers = True
except ImportError:
    has_transformers = False

logger = logging.getLogger(__name__)


class TransformersExtractiveQA(QuestionAnswering):
    """
    Local extractive question answering model based on Huggingface transformers library.

    To use, you should have the ``transformers`` python package installed.
    """

    def __init__(self, model: str = "deepset/deberta-v3-large-squad2"):
        if not has_transformers:
            raise ImportError('transformers is not installed')
        self.model = model

    def answer_with_metadata(
            self,
            context: str | Image,
            question: str
    ) -> QAResult:
        if not isinstance(context, str):
            raise Exception('TransformersExtractiveQA only supports string input')

        qa_model = pipeline("question-answering", model=self.model)

        tokenizer = AutoTokenizer.from_pretrained(self.model)
        tokens = tokenizer.encode(context + question)
        logger.debug(f"Input tokens: {len(tokens)}")

        prediction = qa_model(
            question=question,
            context=context
        )
        logger.debug(f"prediction: {prediction}")

        return QAResult(
            answer=prediction['answer'],
            score=prediction['score'],
            start_index=prediction['start'],
            end_index=prediction['end'],
        )



