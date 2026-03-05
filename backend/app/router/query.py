import logfire
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.query import QueryService, get_query_service

router = APIRouter()


class QueryRequest(BaseModel):
    question: str
    conversation_id: str | None = None


@router.post("/query")
async def query(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    service: QueryService = Depends(get_query_service),
):
    try:
        task_id, conversation_id = await service.initiate(
            request.question, request.conversation_id
        )
        background_tasks.add_task(service.get_producer())
        logfire.info("query accepted", task_id=task_id, conversation_id=conversation_id)
        return {"task_id": task_id, "conversation_id": conversation_id}
    except ValueError as err:
        logfire.warn("conversation not found", conversation_id=request.conversation_id)
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        logfire.error("query initiation failed", error=str(err), exc_info=True)
        raise HTTPException(status_code=500) from err


@router.get("/query/{id}/stream")
async def get_query_stream(
    id: str,
    service: QueryService = Depends(get_query_service),
):
    queue = service.get_stream(id)
    if not queue:
        logfire.warn("stream not found", task_id=id)
        raise HTTPException(status_code=404)

    async def consume():
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk

    return StreamingResponse(consume(), media_type="text/event-stream")
