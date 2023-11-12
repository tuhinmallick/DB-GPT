from typing import Dict
from vllm import AsyncLLMEngine
from vllm.utils import random_uuid
from vllm.sampling_params import SamplingParams


async def generate_stream(
    model: AsyncLLMEngine, tokenizer, params: Dict, device: str, context_len: int
):
    """
    Adapted from https://github.com/lm-sys/FastChat/blob/main/fastchat/serve/vllm_worker.py
    """
    prompt = params["prompt"]
    request_id = params.pop("request_id") if "request_id" in params else random_uuid()
    temperature = float(params.get("temperature", 1.0))
    top_p = float(params.get("top_p", 1.0))
    max_new_tokens = int(params.get("max_new_tokens", 2048))
    echo = bool(params.get("echo", True))
    stop_str = params.get("stop", None)

    stop_token_ids = params.get("stop_token_ids", None) or []
    if tokenizer.eos_token_id is not None:
        stop_token_ids.append(tokenizer.eos_token_id)

    # Handle stop_str
    stop = set()
    if isinstance(stop_str, str) and stop_str != "":
        stop.add(stop_str)
    elif isinstance(stop_str, list) and stop_str != []:
        stop.update(stop_str)

    for tid in stop_token_ids:
        if tid is not None:
            stop.add(tokenizer.decode(tid))

    top_p = 1.0 if temperature <= 1e-5 else max(top_p, 1e-5)
    sampling_params = SamplingParams(
        n=1,
        temperature=temperature,
        top_p=top_p,
        use_beam_search=False,
        stop=list(stop),
        max_tokens=max_new_tokens,
    )
    results_generator = model.generate(prompt, sampling_params, request_id)
    async for request_output in results_generator:
        prompt = request_output.prompt
        if echo:
            text_outputs = [prompt + output.text for output in request_output.outputs]
        else:
            text_outputs = [output.text for output in request_output.outputs]
        text_outputs = " ".join(text_outputs)
        yield {"text": text_outputs, "error_code": 0, "usage": {}}
