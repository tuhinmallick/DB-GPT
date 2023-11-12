from typing import Dict

from pilot.scene.base_chat import BaseChat
from pilot.scene.base import ChatScene
from pilot.common.sql_database import Database
from pilot.configs.config import Config
from pilot.scene.chat_db.professional_qa.prompt import prompt
from pilot.utils.executor_utils import blocking_func_to_async
from pilot.utils.tracer import root_tracer, trace

CFG = Config()


class ChatWithDbQA(BaseChat):
    chat_scene: str = ChatScene.ChatWithDbQA.value()

    """As a DBA, Chat DB Module, chat with combine DB meta schema """

    def __init__(self, chat_param: Dict):
        """Chat DB Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) dbname
        """
        self.db_name = chat_param["select_param"]
        chat_param["chat_mode"] = ChatScene.ChatWithDbQA
        super().__init__(chat_param=chat_param)

        if self.db_name:
            self.database = CFG.LOCAL_DB_MANAGE.get_connect(self.db_name)
            self.db_connect = self.database.session
            self.tables = self.database.get_table_names()

        self.top_k = min(len(self.tables), CFG.KNOWLEDGE_SEARCH_TOP_SIZE)

    @trace()
    async def generate_input_values(self) -> Dict:
        table_info = ""
        dialect = "mysql"
        try:
            from pilot.summary.db_summary_client import DBSummaryClient
        except ImportError:
            raise ValueError("Could not import DBSummaryClient. ")
        if self.db_name:
            client = DBSummaryClient(system_app=CFG.SYSTEM_APP)
            try:
                # table_infos = client.get_db_summary(
                #     dbname=self.db_name, query=self.current_user_input, topk=self.top_k
                # )
                table_infos = await blocking_func_to_async(
                    self._executor,
                    client.get_db_summary,
                    self.db_name,
                    self.current_user_input,
                    self.top_k,
                )
            except Exception as e:
                print(f"db summary find error!{str(e)}")
                # table_infos = self.database.table_simple_info()
                table_infos = await blocking_func_to_async(
                    self._executor, self.database.table_simple_info
                )

            # table_infos = self.database.table_simple_info()
            dialect = self.database.dialect

        return {
            "input": self.current_user_input,
            # "top_k": str(self.top_k),
            # "dialect": dialect,
            "table_info": table_infos,
        }
