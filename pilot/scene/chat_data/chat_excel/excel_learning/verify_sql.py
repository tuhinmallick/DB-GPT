import re
import sqlparse


def add_quotes(sql, column_names=[]):
    parsed = sqlparse.parse(sql)
    for stmt in parsed:
        for token in stmt.tokens:
            deep_quotes(token, column_names)
    return str(parsed[0])


def deep_quotes(token, column_names=[]):
    if hasattr(token, "tokens"):
        for token_child in token.tokens:
            deep_quotes(token_child, column_names)
    elif (
        len(column_names) > 0
        and token.value in column_names
        or len(column_names) <= 0
    ):
        if token.ttype == sqlparse.tokens.Name:
            token.value = f'"{token.value}"'


if __name__ == "__main__":
    sql = "SELECT SUM(预算) AS 总预算 FROM yhj-zx"
    new_sql = add_quotes(sql, ["预算"])
    print(new_sql)
