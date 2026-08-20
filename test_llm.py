from app.services.llm_service import extract_transaction


message = "Paid ₹50 to Siddhesh for lunch"

transaction = extract_transaction(message)

print(transaction)
print()
print(transaction.model_dump())