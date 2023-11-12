import json
import logging
from typing import Dict, NamedTuple, List
from pilot.out_parser.base import BaseOutputParser, T
from pilot.configs.config import Config

CFG = Config()


class ExcelResponse(NamedTuple):
    desciption: str
    clounms: List
    plans: List


logger = logging.getLogger(__name__)


class LearningExcelOutputParser(BaseOutputParser):
    def __init__(self, sep: str, is_stream_out: bool):
        super().__init__(sep=sep, is_stream_out=is_stream_out)

    def parse_prompt_response(self, model_out_text):
        clean_str = super().parse_prompt_response(model_out_text)
        print("clean prompt response:", clean_str)
        try:
            response = json.loads(clean_str)
            for key in sorted(response):
                if key.strip() == "DataAnalysis":
                    desciption = response[key]
                if key.strip() == "ColumnAnalysis":
                    clounms = response[key]
                if key.strip() == "AnalysisProgram":
                    plans = response[key]
            return ExcelResponse(desciption=desciption, clounms=clounms, plans=plans)
        except Exception as e:
            return model_out_text

    def parse_view_response(self, speak, data) -> str:
        if not data or isinstance(data, str):
            return speak
        ### tool out data to table view
        html_title = f"### **Data Summary**\n{data.desciption} "
        html_colunms = f"### **Data Structure**\n"
        for column_index, item in enumerate(data.clounms, start=1):
            keys = item.keys()
            for key in keys:
                html_colunms = f"{html_colunms}- **{column_index}.[{key}]**   _{item[key]}_\n"

        html_plans = f"### **Recommended analysis plan**\n"
        for item in data.plans:
            html_plans = f"{html_plans}{item} \n"
        return f"""{html_title}\n{html_colunms}\n{html_plans}"""
