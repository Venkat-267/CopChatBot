import numpy as np
import openai
from fastapi import APIRouter, HTTPException
from azure.cosmos import CosmosClient
from dotenv import load_dotenv
import os
from sklearn.metrics.pairwise import cosine_similarity
from ..config import COSMOS_DB_URL,COSMOS_DB_KEY,DATABASE_NAME,CONTAINER_NAME_cosmos,OPENAI_API_KEY

# 🔹 Load environment variables (Replace with actual values)
# 🔹 Initialize CosmosDB client
client = CosmosClient(COSMOS_DB_URL, COSMOS_DB_KEY)
database = client.get_database_client(DATABASE_NAME)
container = database.get_container_client(CONTAINER_NAME_cosmos)

router = APIRouter(prefix="/chat", tags=["Chat"])

# 🔹 Function to generate query embeddings using text-embedding-ada-002
def generate_query_embedding(query):
    openai.api_key = OPENAI_API_KEY
    try:
        response = openai.embeddings.create(
            model="text-embedding-ada-002", input=query
        )
        embedding = np.array(response.data[0].embedding)
        
        print(f"\n🔎 Query Embedding Debugging:\n🔹 Query: {query}")
        print(f"🔹 Vector Length: {len(embedding)}\n🔹 Sample Vector: {embedding[:5]}\n")

        return embedding
    except Exception as e:
        print(f"❌ Error generating embeddings: {e}")
        return None

# 🔹 Function to find relevant document chunks
def find_relevant_document(query_embedding):
    results = list(container.read_all_items())  
    print(f"📁 Total Documents in CosmosDB: {len(results)}")  

    best_match = None
    best_file = None
    highest_score = -1  

    for item in results:
        file_name = item.get("file_name", "Unknown File")
        text = item.get("text", "")
        vector = np.array(item["vector"]).reshape(1, -1)  

        score = cosine_similarity(query_embedding.reshape(1, -1), vector)[0][0]
        print(f"🔍 Comparing with: {text[:100]}")  # Show preview of text
        print(f"🔹 Similarity Score: {score}\n")

        if score > highest_score:
            highest_score = score
            best_match = text
            best_file = file_name  

    if highest_score < 0.4:  # ✅ Adjust threshold if needed
        print("❌ No relevant match found. Scores too low.")
        return None, None, highest_score

    print(f"\n✅ Best Match Found in {best_file} with Score: {highest_score}")
    return best_match, best_file, highest_score

# 🔹 Function to generate AI response
def generate_response(context, query):
    try:
        openai.api_key = OPENAI_API_KEY
        prompt = f"Use the following context to answer the question.\n\nContext: {context}\n\nUser: {query}\nAI:"
        response = openai.chat.completions.create(  # ✅ FIXED API CALL
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content  # ✅ FIXED RESPONSE ACCESS
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I couldn't process your request."

# 🔹 Chat API Endpoint
@router.post("/")
async def chat(query: str):
    query_embedding = generate_query_embedding(query)
    if query_embedding is None:
        raise HTTPException(status_code=500, detail="Failed to generate query embeddings.")

    best_match, best_file, score = find_relevant_document(query_embedding)
    if best_match is None or score < 0.4:  # ✅ Threshold Adjusted
        return {"response": "I couldn't find relevant information."}

    ai_response = generate_response(best_match, query)
    return {"response": ai_response, "document": best_file}
