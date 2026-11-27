# Chapter 3 - System Design

FinGuard AI uses a modular service-based architecture.
The React frontend communicates with a FastAPI backend.
PostgreSQL stores users, transactions, savings goals
and advisor conversation records.

JWT authentication protects user-specific resources.
Docker Compose connects the backend, database, fraud
detection, forecasting and advisor services.

# Chapter 8 - Implementation and Testing

Member D implemented backend APIs, authentication,
CSV processing, database integration, frontend screens,
dashboard visualization and service integration.

Backend testing produced 17 successful tests.
Core browser and financial planning tests passed.

The dashboard benchmark processed a database containing
50,000 synthetic transactions with a P95 response time
of 122.95 ms against a target of 300 ms.

Dataset validation produced six passes and three failures
due to missing amount and balance values.

# Chapter 10 - Conclusion and Limitations

The implemented backend and frontend provide an
integrated financial monitoring platform with transaction
management, fraud feedback, forecasts and savings goals.

The tested dashboard satisfies its sequential response
time requirement. Full advisor response verification
requires LLM provider configuration. Fraud missing-data
handling requires agreement with the model owner.
