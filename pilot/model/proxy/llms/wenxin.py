import os
import requests
import json
from typing import List
from pilot.model.proxy.llms.proxy_model import ProxyModel
from pilot.scene.base_message import ModelMessage, ModelMessageRoleType
from cachetools import cached, TTLCache


@cached(TTLCache(1, 1800))
def _build_access_token(api_key: str, secret_key: str) -> str:
    """
    Generate Access token according AK, SK
    """

    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": api_key,
        "client_secret": secret_key,
    }

    res = requests.get(url=url, params=params)

    if res.status_code == 200:
        return res.json().get("access_token")


def wenxin_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    MODEL_VERSION = {
        "ERNIE-Bot": "completions",
        "ERNIE-Bot-turbo": "eb-instant",
    }

    model_params = model.get_params()
    model_name = model_params.proxyllm_backend
    model_version = MODEL_VERSION.get(model_name)
    if not model_version:
        yield f"Unsupport model version {model_name}"

    proxy_api_key = model_params.proxy_api_key
    proxy_api_secret = model_params.proxy_api_secret
    access_token = _build_access_token(proxy_api_key, proxy_api_secret)

    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    proxy_server_url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{model_version}?access_token={access_token}"

    if not access_token:
        yield "Failed to get access token. please set the correct api_key and secret key."

    history = []

    messages: List[ModelMessage] = params["messages"]
    # Add history conversation
    system = ""
    if len(messages) > 1 and messages[0].role == ModelMessageRoleType.SYSTEM:
        role_define = messages.pop(0)
        system = role_define.content
    else:
        message = messages.pop(0)
        if message.role == ModelMessageRoleType.HUMAN:
            history.append({"role": "user", "content": message.content})
    for message in messages:
        if message.role == ModelMessageRoleType.SYSTEM:
            history.append({"role": "user", "content": message.content})
        elif message.role == ModelMessageRoleType.AI:
            history.append({"role": "assistant", "content": message.content})
    # temp_his = history[::-1]
    temp_his = history
    if last_user_input := next(
        (m for m in temp_his if m["role"] == "user"), None
    ):
        history.remove(last_user_input)
        history.append(last_user_input)

    payload = {
        "messages": history,
        "system": system,
        "temperature": params.get("temperature"),
        "stream": True,
    }

    text = ""
    res = requests.post(proxy_server_url, headers=headers, json=payload, stream=True)
    print(f"Send request to {proxy_server_url} with real model {model_name}")
    for line in res.iter_lines():
        if line:
            if not line.startswith(b"data: "):
                yield line.decode("utf-8")
            else:
                json_data = line.split(b": ", 1)[1]
                decoded_line = json_data.decode("utf-8")
                if decoded_line.lower() != "[DONE]".lower():
                    obj = json.loads(json_data)
                    if obj["result"] is not None:
                        content = obj["result"]
                        text += content
                yield text
