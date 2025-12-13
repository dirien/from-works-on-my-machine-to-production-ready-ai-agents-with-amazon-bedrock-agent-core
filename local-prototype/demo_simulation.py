# demo_simulation.py
from agent import fraud_agent

# The "Trigger" Event (Simulated Payload)
new_transaction_event = """
ALERT: New Transaction Attempt
User ID: user_123
Amount: $2000
Merchant: Electronics Store
Location: Tokyo, Japan
Time: 09:15
"""


def run_demo():
    print("--- INCOMING EVENT STREAM ---")
    print(new_transaction_event)
    print("-----------------------------------")

    print("\nAGENT ACTIVATED. Analyzing...\n")

    # Run the agent - the callback_handler will stream the output
    result = fraud_agent(new_transaction_event)

    print("\n--- ANALYSIS COMPLETE ---")


if __name__ == "__main__":
    run_demo()
