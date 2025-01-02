from fastapi import FastAPI
from pydantic import BaseModel
from rag_app.query_rag import query_rag, QueryResponse
from query_model import QueryModel
import uvicorn
from mangum import Mangum
import os
import boto3
import json
WORKER_LAMBDA_NAME = os.environ.get("WORKER_LAMBDA_NAME", None)


app=FastAPI()

 # Entry point for AWS Lambda

class SubmitQueryRequest(BaseModel): 
    query_text:str

@app.get("/")
def index():
    return {"hello":"World"}

@app.get("/get_query")
def get_query_endpoint(query_id: str) -> QueryModel:
    query = QueryModel.get_item(query_id)
    return query

@app.post("/submit_query")
def submit_query_endpoint(request: SubmitQueryRequest) -> QueryModel:
    # Create the query item, and put it into the data-base.
    new_query = QueryModel(query_text=request.query_text)

    if WORKER_LAMBDA_NAME:
        # Make an async call to the worker (the RAG/AI app).
        new_query.put_item()
        invoke_worker(new_query)
    else:
        # Make a synchronous call to the worker (the RAG/AI app).
        query_response = query_rag(request.query_text)
        new_query.answer_text = query_response.response_text
        new_query.sources = query_response.sources
        new_query.is_complete = True
        new_query.put_item() 

    return new_query

handler=Mangum(app)

def invoke_worker(query: QueryModel):
    # Initialize the Lambda client
    lambda_client = boto3.client("lambda")

    # Get the QueryModel as a dictionary.
    payload = query.model_dump()

    # Invoke another Lambda function asynchronously
    response = lambda_client.invoke(
        FunctionName=WORKER_LAMBDA_NAME,
        InvocationType="Event",
        Payload=json.dumps(payload),
    )

    print(f"✅ Worker Lambda invoked: {response}")



if __name__ == "__main__":
    port=8000
    print(f"running the FastAPI server on port {port}")
    uvicorn.run("app_api_handler:app",host="0.0.0.0",port=port)