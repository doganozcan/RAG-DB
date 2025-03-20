import urllib.parse
from typing_extensions import TypedDict, Annotated
from langchain_community.utilities import SQLDatabase
from langchain.chat_models import init_chat_model
from langchain_core.prompts import SystemMessagePromptTemplate 
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool
from langgraph.graph import START, StateGraph
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# FastAPI app initialization
app = FastAPI(title="SQL Query API")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Database Configuration
class DatabaseConfig:
    USERNAME = "postgres"
    PASSWORD = urllib.parse.quote_plus("password")
    HOST = "localhost"
    PORT = "5432"
    DATABASE = "db_name"
    
    @classmethod
    def get_connection_string(cls):
        return f"postgresql://{cls.USERNAME}:{cls.PASSWORD}@{cls.HOST}:{cls.PORT}/{cls.DATABASE}"

# State Definition
class State(TypedDict):
    question: str
    query: str
    result: str
    answer: str

class QueryOutput(TypedDict):
    """Generated SQL query."""
    query: Annotated[str, ..., "Syntactically valid SQL query."]

# Request Model for API
class QuestionRequest(BaseModel):
    question: str

# Response Model for API
class QueryResponse(BaseModel):
    question: str
    sql_query: str
    sql_result: str
    answer: str

# Initialize LLM and Database (global instances)
def init_llm():
    return init_chat_model(
        "deepseek-r1-distill-llama-70b",
        model_provider="groq",
        api_key=os.environ.get("API_KEY")
    )

def init_database():
    return SQLDatabase.from_uri(
        DatabaseConfig.get_connection_string()
    )

# Custom Template
CUSTOM_TEMPLATE = """Given an input question, create a syntactically correct {dialect} query to run to help find the answer. Unless the user specifies in his question a specific number of examples they wish to obtain, always limit your query to at most {top_k} results. You can order the results by a relevant column to return the most interesting examples in the database.

Never query for all the columns from a specific table, only ask for a the few relevant columns given the question.

Pay attention to use only the column names that you can see in the schema description. Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.

Put the column names in " " in the query sentence, for example SELECT SUM("TotalSatisTL") AS TotalAdet FROM products

Only use the following tables:
{table_info}

Question: {input}"""

# Global instances
db = init_database()
llm = init_llm()

# Graph Functions
def write_query(state: State):
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

def execute_query(state: State):
    """Execute SQL query."""
    execute_query_tool = QuerySQLDatabaseTool(db=db)
    try:
        result = execute_query_tool.invoke(state["query"])
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query execution failed: {str(e)}")

def generate_answer(state: State):
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

# Create Graph
def create_graph():
    graph_builder = StateGraph(State)
    graph_builder.add_node("write_query", write_query)
    graph_builder.add_node("execute_query", execute_query)
    graph_builder.add_node("generate_answer", generate_answer)
    
    graph_builder.add_edge(START, "write_query")
    graph_builder.add_edge("write_query", "execute_query")
    graph_builder.add_edge("execute_query", "generate_answer")
    
    return graph_builder.compile()

graph = create_graph()

# API Endpoint
@app.post("/query", response_model=QueryResponse)
async def process_query(request: QuestionRequest):
    """Process a user question and return the SQL query, result, and answer."""
    initial_state = {"question": request.question, "query": "", "result": "", "answer": ""}
    
    try:
        final_state = initial_state
        for step in graph.stream(initial_state, stream_mode="updates"):
            for node, state_update in step.items():
                final_state.update(state_update)
        
        return QueryResponse(
            question=final_state["question"],
            sql_query=final_state["query"],
            sql_result=final_state["result"],
            answer=final_state["answer"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

# Run the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)