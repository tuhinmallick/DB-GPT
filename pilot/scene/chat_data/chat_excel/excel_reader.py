import logging

import duckdb
import os
import re
import sqlparse

import chardet
import pandas as pd
import numpy as np
from pyparsing import (
    CaselessKeyword,
    Word,
    alphas,
    alphanums,
    delimitedList,
    Forward,
    Group,
    Optional,
    Literal,
    infixNotation,
    opAssoc,
    unicodeString,
    Regex,
)

from pilot.common.pd_utils import csv_colunm_foramt
from pilot.common.string_utils import is_chinese_include_number


def excel_colunm_format(old_name: str) -> str:
    new_column = old_name.strip()
    return new_column.replace(" ", "_")


def detect_encoding(file_path):
    # 读取文件的二进制数据
    with open(file_path, "rb") as f:
        data = f.read()
    # 使用 chardet 来检测文件编码
    result = chardet.detect(data)
    encoding = result["encoding"]
    confidence = result["confidence"]
    return encoding, confidence


def add_quotes_ex(sql: str, column_names):
    sql = sql.replace("`", '"')
    for column_name in column_names:
        if sql.find(column_name) != -1 and sql.find(f'"{column_name}"') == -1:
            sql = sql.replace(column_name, f'"{column_name}"')
    return sql


def parse_sql(sql):
    # 定义关键字和标识符
    select_stmt = Forward()
    column = Regex(r"[\w一-龥]*")
    table = Word(alphanums)
    join_expr = Forward()
    where_expr = Forward()
    group_by_expr = Forward()
    order_by_expr = Forward()

    select_keyword = CaselessKeyword("SELECT")
    from_keyword = CaselessKeyword("FROM")
    join_keyword = CaselessKeyword("JOIN")
    on_keyword = CaselessKeyword("ON")
    where_keyword = CaselessKeyword("WHERE")
    group_by_keyword = CaselessKeyword("GROUP BY")
    order_by_keyword = CaselessKeyword("ORDER BY")
    and_keyword = CaselessKeyword("AND")
    or_keyword = CaselessKeyword("OR")
    in_keyword = CaselessKeyword("IN")
    not_in_keyword = CaselessKeyword("NOT IN")

    # 定义语法规则
    select_stmt <<= (
        select_keyword
        + delimitedList(column)
        + from_keyword
        + delimitedList(table)
        + Optional(join_expr)
        + Optional(where_keyword + where_expr)
        + Optional(group_by_keyword + group_by_expr)
        + Optional(order_by_keyword + order_by_expr)
    )

    join_expr <<= join_keyword + table + on_keyword + column + Literal("=") + column

    where_expr <<= (
        column + Literal("=") + Word(alphanums) + Optional(and_keyword + where_expr)
        | column + Literal(">") + Word(alphanums) + Optional(and_keyword + where_expr)
        | column + Literal("<") + Word(alphanums) + Optional(and_keyword + where_expr)
    )

    group_by_expr <<= delimitedList(column)

    order_by_expr <<= column + Optional(Literal("ASC") | Literal("DESC"))

    # 解析 SQL 语句
    parsed_result = select_stmt.parseString(sql)

    return parsed_result.asList()


def add_quotes(sql, column_names=[]):
    sql = sql.replace("`", "")
    sql = sql.replace("'", "")
    parsed = sqlparse.parse(sql)
    for stmt in parsed:
        for token in stmt.tokens:
            deep_quotes(token, column_names)
    return str(parsed[0])


def deep_quotes(token, column_names=[]):
    if hasattr(token, "tokens"):
        for token_child in token.tokens:
            deep_quotes(token_child, column_names)
    elif is_chinese_include_number(token.value):
        new_value = token.value.replace("`", "").replace("'", "")
        token.value = f'"{new_value}"'


def get_select_clause(sql):
    parsed = sqlparse.parse(sql)[0]  # 解析 SQL 语句，获取第一个语句块

    select_tokens = []
    is_select = False

    for token in parsed.tokens:
        if token.is_keyword and token.value.upper() == "SELECT":
            is_select = True
        elif is_select:
            if token.is_keyword and token.value.upper() == "FROM":
                break
            select_tokens.append(token)
    return "".join(str(token) for token in select_tokens)


def parse_select_fields(sql):
    parsed = sqlparse.parse(sql)[0]  # 解析 SQL 语句，获取第一个语句块
    fields = []

    for token in parsed.tokens:
        # 使用 flatten() 方法合并 '2022' 和 '年' 为一个 token
        if token.match(sqlparse.tokens.Literal.String.Single):
            token.flatten()
        if isinstance(token, sqlparse.sql.Identifier):
            fields.append(token.get_real_name())

    return [field.replace("field", f'"{field}"') for field in fields]


def add_quotes_to_chinese_columns(sql, column_names=[]):
    parsed = sqlparse.parse(sql)
    for stmt in parsed:
        process_statement(stmt, column_names)
    return str(parsed[0])


def process_statement(statement, column_names=[]):
    if isinstance(statement, sqlparse.sql.IdentifierList):
        for identifier in statement.get_identifiers():
            process_identifier(identifier)
    elif isinstance(statement, sqlparse.sql.Identifier):
        process_identifier(statement, column_names)
    elif isinstance(statement, sqlparse.sql.TokenList):
        for item in statement.tokens:
            process_statement(item)


def process_identifier(identifier, column_names=[]):
    # if identifier.has_alias():
    #     alias = identifier.get_alias()
    #     identifier.tokens[-1].value = '[' + alias + ']'
    if hasattr(identifier, "tokens") and identifier.value in column_names:
        if is_chinese(identifier.value):
            new_value = get_new_value(identifier.value)
            identifier.value = new_value
            identifier.normalized = new_value
            identifier.tokens = [sqlparse.sql.Token(sqlparse.tokens.Name, new_value)]
    elif hasattr(identifier, "tokens"):
        for token in identifier.tokens:
            if isinstance(token, sqlparse.sql.Function):
                process_function(token)
            elif token.ttype in sqlparse.tokens.Name:
                new_value = get_new_value(token.value)
                token.value = new_value
                token.normalized = new_value
            elif token.value in column_names:
                new_value = get_new_value(token.value)
                token.value = new_value
                token.normalized = new_value
                token.tokens = [sqlparse.sql.Token(sqlparse.tokens.Name, new_value)]


def get_new_value(value):
    return f""" "{value.replace("`", "").replace("'", "").replace('"', "")}" """


def process_function(function):
    function_params = list(function.get_parameters())
    # for param in function_params:
    for function_param in function_params:
        param = function_param
        # 如果参数部分是一个标识符（字段名）
        if isinstance(param, sqlparse.sql.Identifier):
            # 判断是否需要替换字段值
            # if is_chinese(param.value):
            # 替换字段值
            new_value = get_new_value(param.value)
            # new_parameter = sqlparse.sql.Identifier(f'[{param.value}]')
            function_param.tokens = [
                sqlparse.sql.Token(sqlparse.tokens.Name, new_value)
            ]
    print(function)


def is_chinese(text):
    return any("一" <= char <= "鿿" for char in text)


if __name__ == "__main__":
    # sql = "SELECT 姓名, 年龄 FROM table1 JOIN table2 ON table1.id = table2.id WHERE 字段 = '值' AND 字段2 > 10 GROUP BY 姓名 ORDER BY 年龄 DESC"
    #
    # parsed_result = parse_sql(sql)
    # print(parsed_result)
    # sql_2 = 'SELECT "省份", "2022年" AS "GDP", ROUND(("2022年" / (SELECT SUM("2022年") FROM excel_data)) * 100, 2) AS "占比" FROM excel_data ORDER BY "占比" DESC'
    # print(add_quotes_to_chinese_columns(sql_2))

    # sql = """ SELECT 省份, 2021年, 2022年 as GDP FROM excel_data """
    sql = """ SELECT 省份, 2022年, 2021年 FROM excel_data """
    sql_2 = """ SELECT "省份", "2022年" as "2022年实际GDP增速", "2021年" as "2021年实际GDP增速" FROM excel_data """
    sql_3 = """ SELECT "省份", ("2022年" / ("2022年" + "2021年")) * 100 as "2022年实际GDP增速占比", ("2021年" / ("2022年" + "2021年")) * 100 as "2021年实际GDP增速占比" FROM excel_data """

    sql = add_quotes_to_chinese_columns(sql_3)
    print(f"excute sql:{sql}")


class ExcelReader:
    def __init__(self, file_path):
        file_name = os.path.basename(file_path)
        file_name_without_extension = os.path.splitext(file_name)[0]
        encoding, confidence = detect_encoding(file_path)
        logging.error(f"Detected Encoding: {encoding} (Confidence: {confidence})")
        self.excel_file_name = file_name
        self.extension = os.path.splitext(file_name)[1]
        # read excel file
        if file_path.endswith(".xlsx") or file_path.endswith(".xls"):
            df_tmp = pd.read_excel(file_path)
            self.df = pd.read_excel(
                file_path,
                converters={i: csv_colunm_foramt for i in range(df_tmp.shape[1])},
            )
        elif file_path.endswith(".csv"):
            df_tmp = pd.read_csv(file_path, encoding=encoding)
            self.df = pd.read_csv(
                file_path,
                encoding=encoding,
                converters={i: csv_colunm_foramt for i in range(df_tmp.shape[1])},
            )
        else:
            raise ValueError("Unsupported file format.")

        self.df.replace("", np.nan, inplace=True)
        self.columns_map = {}
        for column_name in df_tmp.columns:
            self.columns_map.update({column_name: excel_colunm_format(column_name)})
            try:
                self.df[column_name] = pd.to_numeric(self.df[column_name])
                self.df[column_name] = self.df[column_name].fillna(0)
            except Exception as e:
                print("transfor column error！" + column_name)

        self.df = self.df.rename(columns=lambda x: x.strip().replace(" ", "_"))

        # connect DuckDB
        self.db = duckdb.connect(database=":memory:", read_only=False)

        self.table_name = "excel_data"
        # write data in duckdb
        self.db.register(self.table_name, self.df)

    def run(self, sql):
        try:
            if f'"{self.table_name}"' in sql:
                sql = sql.replace(f'"{self.table_name}"', self.table_name)
            sql = add_quotes_to_chinese_columns(sql)
            print(f"excute sql:{sql}")
            results = self.db.execute(sql)
            colunms = [descrip[0] for descrip in results.description]
            return colunms, results.fetchall()
        except Exception as e:
            logging.error("excel sql run error!", e)
            raise ValueError(f"Data Query Exception!\\nSQL[{sql}].\\nError:{str(e)}")

    def get_df_by_sql_ex(self, sql):
        colunms, values = self.run(sql)
        return pd.DataFrame(values, columns=colunms)

    def get_sample_data(self):
        return self.run(f"SELECT * FROM {self.table_name} LIMIT 5;")
