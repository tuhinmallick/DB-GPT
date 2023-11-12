from typing import Dict

from pilot.scene.base_chat import BaseChat
from pilot.scene.base import ChatScene
from pilot.common.sql_database import Database
from pilot.configs.config import Config
from pilot.scene.chat_db.auto_execute.prompt import prompt
from pilot.utils.executor_utils import blocking_func_to_async
from pilot.utils.tracer import root_tracer, trace

CFG = Config()


class ChatWithDbAutoExecute(BaseChat):
    chat_scene: str = ChatScene.ChatWithDbExecute.value()

    """Number of results to return from the query"""

    def __init__(self, chat_param: Dict):
        """Chat Data Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) dbname
        """
        chat_mode = ChatScene.ChatWithDbExecute
        self.db_name = chat_param["select_param"]
        chat_param["chat_mode"] = chat_mode
        """ """
        super().__init__(
            chat_param=chat_param,
        )
        if not self.db_name:
            raise ValueError(
                f"{ChatScene.ChatWithDbExecute.value} mode should chose db!"
            )
        with root_tracer.start_span(
            "ChatWithDbAutoExecute.get_connect", metadata={"db_name": self.db_name}
        ):
            self.database = CFG.LOCAL_DB_MANAGE.get_connect(self.db_name)
        self.top_k: int = 200

    @trace()
    async def generate_input_values(self) -> Dict:
        """
        generate input values
        """
        try:
            from pilot.summary.db_summary_client import DBSummaryClient
        except ImportError:
            raise ValueError("Could not import DBSummaryClient. ")
        client = DBSummaryClient(system_app=CFG.SYSTEM_APP)
        table_infos = None
        try:
            # table_infos = client.get_db_summary(
            #     dbname=self.db_name,
            #     query=self.current_user_input,
            #     topk=CFG.KNOWLEDGE_SEARCH_TOP_SIZE,
            # )
            with root_tracer.start_span("ChatWithDbAutoExecute.get_db_summary"):
                table_infos = await blocking_func_to_async(
                    self._executor,
                    client.get_db_summary,
                    self.db_name,
                    self.current_user_input,
                    CFG.KNOWLEDGE_SEARCH_TOP_SIZE,
                )
        except Exception as e:
            print(f"db summary find error!{str(e)}")
        if not table_infos:
            # table_infos = self.database.table_simple_info()
            table_infos = await blocking_func_to_async(
                self._executor, self.database.table_simple_info
            )

        return {
            "input": self.current_user_input,
            "top_k": str(self.top_k),
            "dialect": self.database.dialect,
            "table_info": table_infos,
        }

    def do_action(self, prompt_response):
        print(f"do_action:{prompt_response}")
        with root_tracer.start_span(
            "ChatWithDbAutoExecute.do_action.run_sql",
            metadata=prompt_response.to_dict(),
        ):
            return self.database.run(prompt_response.sql)
