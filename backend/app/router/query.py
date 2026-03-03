import logfire

from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from app.config import settings
from asyncio import Queue

router = APIRouter()

_provider = GoogleProvider(api_key=settings.gcp_key)
_model = GoogleModel("gemini-2.0-flash", provider=_provider)
agent = Agent(_model, system_prompt="You are a helpful assistant.")


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
            async with agent.run_stream(request.question) as result:
                async for chunk in result.stream_text(delta=True):
                    await queue.put(chunk)
            await queue.put(None)  # sentinel to signal end
            del _streams[task_id]

        background_tasks.add_task(produce)
        return {"task_id": task_id}

    except Exception as err:
        logfire.error(
            f"Task error: {task_id} - {err}", task_id=task_id, err=JSONResponse(err)
        )

        return HTTPException(status_code=500)

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

    return StreamingResponse(consume(), media_type="text/plain")
