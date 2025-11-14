from fastapi import APIRouter, Request
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

router = APIRouter()

#  Initialize your local Ollama model
llm = ChatOllama(
    model="qwen2.5:1.5b",  # or llama3, phi3, etc.
    temperature=0.3,
)

@router.post("/chat")
async def chatbot_response(request: Request):
    """Handle incoming chat messages and return LLM-generated replies."""
    data = await request.json()
    user_message = data.get("message", "")

    if not user_message:
        return {"reply": "Please enter a message."}

    # System prompt to define the chatbot’s behavior
    system_prompt = (
    "You are WBL Assist, an AI tutor for Whitebox Learning (WBL). "
    "Whitebox Learning offers classroom and online training for Engineers and Machine Learning enthusiasts. "
    "You must answer only questions related to technology, Artificial Intelligence, Machine Learning, Data Science, or WBL’s training programs. "
    "Keep every answer very short — maximum 2 to 3 sentences. "
    "Avoid long explanations, lists, or detailed breakdowns. "
    "If the user asks anything unrelated to these topics (such as movies, celebrities, personal questions, or general knowledge), "
    "strictly reply only with: 'Please contact our recruiting team at recruiting@whitebox-learning.com for assistance.' "
    "Do not generate long responses under any circumstance."
)



    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    try:
        response = llm.invoke(messages)
        return {"reply": response.content}
    except Exception as e:
        return {"reply": f" Error processing message: {str(e)}"}
