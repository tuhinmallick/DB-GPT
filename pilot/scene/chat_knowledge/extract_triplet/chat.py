from typing import Dict

from pilot.scene.base_chat import BaseChat
from pilot.scene.base import ChatScene
from pilot.configs.config import Config

from pilot.scene.chat_knowledge.extract_triplet.prompt import prompt

CFG = Config()


class ExtractTriplet(BaseChat):
    chat_scene: str = ChatScene.ExtractTriplet.value()

    """extracting triplets by llm"""

    def __init__(self, chat_param: Dict):
        """ """
        chat_param["chat_mode"] = ChatScene.ExtractTriplet
        super().__init__(
            chat_param=chat_param,
        )

        self.user_input = chat_param["current_user_input"]
        self.extract_mode = chat_param["select_param"]

    def generate_input_values(self):
        return {
            "text": self.user_input,
        }

    @property
    def chat_type(self) -> str:
        return ChatScene.ExtractTriplet.value
