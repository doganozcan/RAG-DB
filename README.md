# RAG-DB Chat Application

This project is a chatbot application that uses RAG (Retrieval-Augmented Generation) to answer questions about database content by generating and executing SQL queries.

## Prerequisites

- Node.js (v16 or higher)
- Python (v3.8 or higher)
- PostgreSQL database
- Groq API key

## Installation

### Frontend Setup
1. Install Node.js dependencies:
```bash
npm install
```

### Backend Setup
1. Navigate to the API directory:
```bash
cd API
```

2. Create a Python virtual environment:
```bash
python -m venv venv
```

3. Activate the virtual environment:
- Windows:
```bash
venv\Scripts\activate
```
- Unix/MacOS:
```bash
source venv/bin/activate
```

4. Install Python dependencies:
```bash
pip install fastapi uvicorn langchain langgraph typing_extensions psycopg2-binary
```

5. Set up your environment variables:
```bash
export API_KEY=your_groq_api_key
```

## Database Configuration

Update the database configuration in `API/rag_database.py`:
```python
class DatabaseConfig:
    USERNAME = "your_username"
    PASSWORD = "your_password"
    HOST = "localhost"
    PORT = "5432"
    DATABASE = "your_database_name"
```

## Running the Application

1. Start the backend server:
```bash
cd API
python rag_database.py
```
The API will be available at http://localhost:8000

2. Start the frontend development server:
```bash
npm start
```
The application will open in your browser at http://localhost:3000

## Usage

1. Open the application in your browser
2. Type your question about the database in the chat input
3. The application will:
   - Generate an appropriate SQL query
   - Execute the query on your database
   - Return the results and a natural language answer

## Features

- Natural language to SQL query conversion
- Dark/Light mode toggle
- Real-time chat interface
- SQL query and result display
- Loading animations
