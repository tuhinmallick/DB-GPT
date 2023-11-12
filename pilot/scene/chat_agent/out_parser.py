import json
from typing import Dict, NamedTuple
from pilot.out_parser.base import BaseOutputParser, T


class PluginAction(NamedTuple):
    command: Dict
    speak: str = ""
    thoughts: str = ""


class PluginChatOutputParser(BaseOutputParser):
    def parse_view_response(self, speak, data) -> str:
        ### tool out data to table view
        print(f"parse_view_response:{speak},{str(data)}")
        return f"##### {speak}" + "\n" + str(data)

    def get_format_instructions(self) -> str:
        pass
