import urllib.parse
from typing_extensions import TypedDict, Annotated
from langchain_community.utilities import SQLDatabase
from langchain.chat_models import init_chat_model
from langchain_core.prompts import SystemMessagePromptTemplate 
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool
from langgraph.graph import START, StateGraph
import os

class DatabaseConfig:
    USERNAME = "postgres"
    PASSWORD = urllib.parse.quote_plus("db_password")
    HOST = "localhost"
    PORT = "5432"
    DATABASE = "db_name"
    
    @classmethod
    def get_connection_string(cls):
        return f"postgresql://{cls.USERNAME}:{cls.PASSWORD}@{cls.HOST}:{cls.PORT}/{cls.DATABASE}"

class State(TypedDict):
    question: str
    query: str
    result: str
    answer: str

class QueryOutput(TypedDict):
    """Generated SQL query."""
    query: Annotated[str, ..., "Syntactically valid SQL query."]

def init_llm():
    return init_chat_model(
        "deepseek-r1-distill-llama-70b",
        model_provider="groq",
        api_key= os.getenv("GROQ_API_KEY")
    )

def init_database():
    return SQLDatabase.from_uri(
        DatabaseConfig.get_connection_string()
    )

CUSTOM_TEMPLATE = """Given an input question, create a syntactically correct {dialect} query to run to help find the answer. Unless the user specifies in his question a specific number of examples they wish to obtain, always limit your query to at most {top_k} results. You can order the results by a relevant column to return the most interesting examples in the database.

Never query for all the columns from a specific table, only ask for a the few relevant columns given the question.

Pay attention to use only the column names that you can see in the schema description. Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.

Put the column names in " " in the query sentence, for example SELECT SUM("TotalSatisTL") AS TotalAdet FROM products

Only use the following tables:
{table_info}

Question: {input}"""

def write_query(state: State, db, llm):
    """Generate SQL query to fetch information."""
    prompt = SystemMessagePromptTemplate.from_template(CUSTOM_TEMPLATE).format_messages(
        dialect=db.dialect,
        top_k=100,
        table_info=db.get_table_info(),
        input=state["question"],
    )
    structured_llm = llm.with_structured_output(QueryOutput)
    result = structured_llm.invoke(prompt[0].content)
    return {"query": result["query"]}

def execute_query(state: State, db):
    """Execute SQL query."""
    execute_query_tool = QuerySQLDatabaseTool(db=db)
    return {"result": execute_query_tool.invoke(state["query"])}

def generate_answer(state: State, llm):
    """Answer question using retrieved information as context."""
    prompt = (
        "Given the following user question, corresponding SQL query, "
        "and SQL result, answer the user question.\n\n"
        f'Question: {state["question"]}\n'
        f'SQL Query: {state["query"]}\n'
        f'SQL Result: {state["result"]}'
    )
    response = llm.invoke(prompt)
    return {"answer": response.content}

def main():
    db = init_database()
    llm = init_llm()
    
    def create_graph():
        graph_builder = StateGraph(State)
        graph_builder.add_node("write_query", lambda state: write_query(state, db, llm))
        graph_builder.add_node("execute_query", lambda state: execute_query(state, db))
        graph_builder.add_node("generate_answer", lambda state: generate_answer(state, llm))
        
        graph_builder.add_edge(START, "write_query")
        graph_builder.add_edge("write_query", "execute_query")
        graph_builder.add_edge("execute_query", "generate_answer")
        
        return graph_builder.compile()
    
    graph = create_graph()
    question = "Ürünlerin toplam satış tutarını öğrenmek istiyorum. Bu bilgiyi alabilir miyim?"
    
    for step in graph.stream({"question": question}, stream_mode="updates"):
        print(step)

if __name__ == "__main__":
    main()