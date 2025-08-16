import asyncio
import logging
from typing import Callable, Any
from akinus_utils.utils.logger import log

async def retry_async(
    func: Callable,
    *args,
    retries: int = 1,
    delay: float = 0,
    exceptions: tuple = (Exception,),
    logger: Callable[[str], Any] = None,
    **kwargs
):
    """
    Retry an async function up to `retries` times if it raises specified exceptions.

    Args:
        func (Callable): The async function to call.
        *args: Positional arguments for the function.
        retries (int): Number of retries before giving up.
        delay (float): Delay in seconds between retries.
        exceptions (tuple): Tuple of exception classes to catch.
        logger (Callable): Optional logger function that takes a message string.
        **kwargs: Keyword arguments for the function.

    Returns:
        The return value of `func` if successful.

    Raises:
        The last exception if all retries fail.
    """
    attempt = 0
    while True:
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            attempt += 1
            if attempt > retries:
                if logger:
                    await _maybe_await(logger(f"Function {func.__name__} failed after {retries} retries: {e}"))
                raise
            if logger:
                await _maybe_await(logger(f"Retry {attempt}/{retries} for {func.__name__} due to: {e}"))
            if delay > 0:
                await asyncio.sleep(delay)


async def retry_until_condition(worker_func, condition_func, condition_check, *args,
                                check_interval=2, max_retries=None, logger=None, **kwargs):
    """
    Repeatedly runs `worker_func` until `condition_check(result)` returns True.
    - `worker_func`: async function to run each loop.
    - `condition_func`: async function returning a value to check.
    - `condition_check`: function/lambda that receives condition_func's result and returns True to stop.
    - `check_interval`: seconds between retries.
    - `max_retries`: optional limit on how many retries before failing.
    - `logger`: optional logging function.
    """
    attempts = 0
    while True:
        attempts += 1
        await worker_func(*args, **kwargs)

        result = await condition_func(*args, **kwargs)
        if condition_check(result):  # ✅ fully customizable condition
            if logger:
                await _maybe_await(logger(f"Condition met after {attempts} attempts (result: {result})."))
            return result

        if max_retries and attempts >= max_retries:
            if logger:
                await _maybe_await(logger(f"Max retries reached ({max_retries}) without meeting condition. Last result: {result}"))
            return result

        if logger:
            await _maybe_await(logger(f"Condition check failed (result: {result}), retrying... (attempt {attempts})"))
        await asyncio.sleep(check_interval)

async def _maybe_await(result):
    """Helper to await loggers that may be async or sync."""
    if asyncio.iscoroutine(result):
        await result
