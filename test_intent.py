from app.services.llm_service import detect_intent


test_messages = [
    "Paid ₹500 to Rahul",

    "How much did I spend?",
    "How much have I spent so far?",

    "How much did I spend today?",
    "What did I spend today?",
    "Show today's expenses",

    "How much did I spend yesterday?",
    "What did I spend yesterday?",

    "How much did I spend this week?",
    "What did I spend this week?",

    "How much did I spend this month?",
    "What did I spend this month?",

    "How much did I spend last month?",
    "What did I spend last month?",

    "Show my recent transactions",
    "What did I spend recently?",

    "Hello",
]


for message in test_messages:
    try:
        intent = detect_intent(message)

        print(message)
        print(f"  → {intent}")
        print()

    except Exception as e:
        print(message)
        print(f"  → ERROR: {e}")
        print()