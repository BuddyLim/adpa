from asyncio import Queue
from uuid import uuid4

from fastapi import Depends
import logfire
from opentelemetry import context as otel_context

from app.repositories.pipeline import PipelineRepository, get_pipeline_repo
from app.services.pipeline import run_pipeline

# Module-level so streams are shared across all QueryService instances
_streams: dict[str, Queue] = {}


class QueryService:
    def __init__(self, repo: PipelineRepository):
        self.repo = repo

    async def initiate(
        self, question: str, conversation_id: str | None
    ) -> tuple[str, str]:
        task_id = str(uuid4())

        if conversation_id:
            conversation = await self.repo.get_conversation(conversation_id)
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")
            conv_id = conversation.id
        else:
            conv_id = await self.repo.create_conversation()

        message_id = await self.repo.create_user_message(conv_id, question)
        await self.repo.create_pipeline_run(run_id=task_id, message_id=message_id)

        queue: Queue = Queue()
        _streams[task_id] = queue

        logfire.info(
            "query initiated",
            task_id=task_id,
            conversation_id=conv_id,
            question=question,
        )

        # Capture the current trace context so the background task
        # continues the same trace instead of starting an orphaned one
        trace_context = otel_context.get_current()

        async def produce():
            token = otel_context.attach(trace_context)
            try:
                with logfire.span(
                    "pipeline run",
                    task_id=task_id,
                    conversation_id=conv_id,
                    question=question,
                ):
                    try:
                        async for chunk in run_pipeline(
                            task_id=task_id,
                            query=question,
                            pipeline_run_id=task_id,
                            conversation_id=conv_id,
                            pipeline_repo=self.repo,
                        ):
                            await queue.put(chunk)
                    except Exception as err:
                        logfire.error(
                            "pipeline run failed",
                            task_id=task_id,
                            error=str(err),
                            exc_info=True,
                        )
                    finally:
                        await queue.put(None) 
                        _streams.pop(task_id, None)
            finally:
                otel_context.detach(token)

        self._produce = produce
        return task_id, conv_id

    def get_producer(self):
        return self._produce

    def get_stream(self, task_id: str) -> Queue | None:
        return _streams.get(task_id)


def get_query_service(
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> QueryService:
    return QueryService(repo)
