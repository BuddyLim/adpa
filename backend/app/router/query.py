import logfire

from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from asyncio import Queue

from app.services.pipeline import run_pipeline

router = APIRouter()


class QueryRequest(BaseModel):
    question: str


_streams: dict[str, Queue] = {}


@router.post("/query")
async def query(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
):
    task_id = str(uuid4())

    try:
        queue: Queue = Queue()
        _streams[task_id] = queue
        logfire.info(f"Task query: {task_id}", task_id=task_id)

        async def produce():
            try:
                async for chunk in run_pipeline(
                    task_id=task_id, query=request.question
                ):
                    await queue.put(chunk)
                await queue.put(None)  # sentinel to signal end

            finally:
                del _streams[task_id]

        background_tasks.add_task(produce)
        return {"task_id": task_id}

    except Exception as err:
        logfire.error(
            f"Task error: {task_id} - {err}",
            task_id=task_id,
        )

        raise HTTPException(status_code=500)

    # return StreamingResponse(stream_response(), media_type="text/plain")


@router.get("/query/{id}/stream")
async def get_query_stream(id: str):
    queue = _streams.get(id)
    if not queue:
        raise HTTPException(status_code=404)

    async def consume():
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk

    return StreamingResponse(consume(), media_type="text/event-stream")
