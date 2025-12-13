# tools.py
from strands import tool

# Mock Database with multiple users for demo scenarios
# Note: In a real system, this would be a persistent database
USER_DB = {
    # User 1: John Doe - London resident (will trigger fraud alert due to impossible travel)
    "user_123": {
        "name": "John Doe",
        "home_location": "London, UK",
        "last_transaction": {"time": "09:00", "location": "London, UK"},
        "status": "ACTIVE",
        "typical_spend": "$50-200",
        "preferred_merchants": ["grocery stores", "restaurants", "transit"],
    },
    # User 2: Jane Smith - New York resident (normal transaction pattern, no alerts)
    "user_456": {
        "name": "Jane Smith",
        "home_location": "New York, USA",
        "last_transaction": {"time": "14:00", "location": "New York, USA"},
        "status": "ACTIVE",
        "typical_spend": "$100-500",
        "preferred_merchants": ["department stores", "restaurants", "online shopping"],
    },
    # User 3: Bob Wilson - Berlin resident (frequent traveler, known pattern)
    "user_789": {
        "name": "Bob Wilson",
        "home_location": "Berlin, Germany",
        "last_transaction": {"time": "08:30", "location": "Frankfurt, Germany"},
        "status": "ACTIVE",
        "typical_spend": "$200-1000",
        "preferred_merchants": ["electronics", "business services", "hotels"],
    },
    # User 4: Alice Chen - Singapore resident (will trigger fraud alert)
    "user_321": {
        "name": "Alice Chen",
        "home_location": "Singapore",
        "last_transaction": {"time": "10:00", "location": "Singapore"},
        "status": "ACTIVE",
        "typical_spend": "$50-300",
        "preferred_merchants": ["food delivery", "retail", "entertainment"],
    },
}


@tool
def get_user_profile(user_id: str) -> dict:
    """Retrieves user details and account status.

    Args:
        user_id: The unique identifier for the user (e.g., 'user_123')

    Returns:
        User profile including name, home location, last transaction, and status.
    """
    return USER_DB.get(user_id, {"error": "User not found"})


@tool
def get_recent_transactions(user_id: str) -> dict:
    """Fetches the last known transaction for the user.

    Args:
        user_id: The unique identifier for the user (e.g., 'user_123')

    Returns:
        The most recent transaction with time and location details.
    """
    user = USER_DB.get(user_id)
    if user:
        return {
            "last_transaction": user["last_transaction"],
            "typical_spend": user.get("typical_spend", "unknown"),
            "preferred_merchants": user.get("preferred_merchants", []),
        }
    return {"error": "No history found"}


@tool
def block_credit_card(user_id: str, reason: str) -> dict:
    """Blocks the user's credit card and logs the reason.

    Use this tool when fraud is detected to immediately protect the user's account.
    If the card is already blocked, returns information about the existing block.

    Args:
        user_id: The unique identifier for the user whose card should be blocked
        reason: A detailed explanation of why the card is being blocked

    Returns:
        Confirmation of the block action with a ticket ID for tracking,
        or information that the card was already blocked.
    """
    user = USER_DB.get(user_id)
    if not user:
        return {"error": "User not found", "user_id": user_id}

    user_name = user["name"]

    # Check if card is already blocked
    if user.get("status") == "BLOCKED":
        existing_ticket = user.get("block_ticket", f"TICKET-{user_id[-3:]}-999")
        print(f"\n[INFO] Card for {user_id} ({user_name}) is ALREADY BLOCKED. Ticket: {existing_ticket}")
        return {
            "status": "ALREADY_BLOCKED",
            "ticket_id": existing_ticket,
            "user": user_name,
            "message": f"Card was already blocked. Original ticket: {existing_ticket}"
        }

    # Block the card and update status
    ticket_id = f"TICKET-{user_id[-3:]}-999"
    USER_DB[user_id]["status"] = "BLOCKED"
    USER_DB[user_id]["block_ticket"] = ticket_id
    USER_DB[user_id]["block_reason"] = reason

    print(f"\n[ACTION] BLOCKING CARD for {user_id} ({user_name}). REASON: {reason}")
    return {"status": "BLOCKED", "ticket_id": ticket_id, "user": user_name}
