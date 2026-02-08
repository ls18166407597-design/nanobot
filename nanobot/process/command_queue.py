import asyncio
import time
from typing import Callable, Awaitable, TypeVar, Dict, List, Optional, Any
from dataclasses import dataclass, field
from loguru import logger
from .lanes import CommandLane

T = TypeVar("T")

@dataclass
class QueueEntry:
    task: Callable[[], Awaitable[Any]]
    future: asyncio.Future
    enqueued_at: float
    lane: str

@dataclass
class LaneState:
    name: str
    queue: List[QueueEntry] = field(default_factory=list)
    active: int = 0
    max_concurrent: int = 1
    draining: bool = False

class CommandQueue:
    """
    In-process queue to serialize command executions within specific 'Lanes'.
    
    Ensures that:
    1. Tasks in the same lane (e.g. 'main') run serially (or with limited concurrency).
    2. Tasks in different lanes can run in parallel.
    3. Background tasks don't block user interactions if separated by lanes.
    """
    _lanes: Dict[str, LaneState] = {}

    @classmethod
    def get_lane(cls, name: str) -> LaneState:
        if name not in cls._lanes:
            # Default concurrency is 1 (serial)
            cls._lanes[name] = LaneState(name=name, max_concurrent=1)
        return cls._lanes[name]

    @classmethod
    def set_lane_concurrency(cls, name: str, max_concurrent: int):
        lane = cls.get_lane(name)
        lane.max_concurrent = max(1, max_concurrent)
        cls._drain(lane)

    @classmethod
    async def enqueue(cls, lane_name: str, task: Callable[[], Awaitable[T]]) -> T:
        """
        Add a task to the specified lane.
        
        Args:
            lane_name: The name of the lane (use CommandLane constants).
            task: An async function (coroutine factory) to execute.
            
        Returns:
            The result of the task once completed.
        """
        lane = cls.get_lane(lane_name)
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        
        entry = QueueEntry(
            task=task, 
            future=future, 
            enqueued_at=time.time(),
            lane=lane_name
        )
        
        lane.queue.append(entry)
        logger.debug(f"[CommandQueue] Enqueued task in '{lane_name}'. Pos: {len(lane.queue)}, Active: {lane.active}")
        
        cls._drain(lane)
        return await future

    @classmethod
    def _drain(cls, lane: LaneState):
        """
        Process items in the lane if safe to do so.
        """
        if lane.draining:
            return
        lane.draining = True
        
        try:
            loop = asyncio.get_running_loop()
            
            while lane.active < lane.max_concurrent and lane.queue:
                entry = lane.queue.pop(0)
                lane.active += 1
                
                # Check wait time warning
                wait_ms = (time.time() - entry.enqueued_at) * 1000
                if wait_ms > 2000:
                    logger.warning(f"[CommandQueue] Slow lane '{lane.name}': Task waited {wait_ms:.0f}ms")

                async def runner(e: QueueEntry):
                    start_time = time.time()
                    try:
                        result = await e.task()
                        if not e.future.cancelled():
                             e.future.set_result(result)
                        logger.debug(f"[CommandQueue] Task done in '{e.lane}'. Duration: {(time.time() - start_time)*1000:.0f}ms")
                    except Exception as ex:
                        logger.exception(f"[CommandQueue] Task failed in '{e.lane}': {ex}")
                        if not e.future.cancelled():
                             e.future.set_exception(ex)
                    finally:
                        lane.active -= 1
                        # Trigger drain again for this lane to pick up next item
                        cls._drain(lane)

                loop.create_task(runner(entry))
                
        except Exception as e:
            logger.error(f"[CommandQueue] Drain error in '{lane.name}': {e}")
        finally:
            lane.draining = False

    @classmethod
    def get_queue_size(cls, lane_name: str = CommandLane.MAIN) -> int:
        lane = cls.get_lane(lane_name)
        return len(lane.queue) + lane.active

    @classmethod
    def clear_lane(cls, lane_name: str = CommandLane.MAIN) -> int:
        """
        Clears pending tasks in a lane (active tasks continue).
        """
        lane = cls.get_lane(lane_name)
        removed = len(lane.queue)
        # Cancel all pending futures
        for entry in lane.queue:
            entry.future.cancel()
        lane.queue.clear()
        return removed
