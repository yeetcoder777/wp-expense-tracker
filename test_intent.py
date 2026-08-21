from app.services.llm_service import detect_intent

tests = [
    "Paid ₹500 to Rahul",
    "How much did I spend?",
    "How much have I spent so far?",
    "How much did I spend today?",
    "What did I spend today?",
    "Show today's expenses",
    "Show my recent transactions",
    "What did I spend recently?",
    "Hello",
    "How much did I spend this month?",
    "How much have I spent this month?",
    "What did I spend this month?",
]

for text in tests:
    print(f"{text}")
    print(f"  → {detect_intent(text)}")
    print()
