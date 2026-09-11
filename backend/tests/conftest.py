import os

# Ensure all tests run against an isolated test database so they never mutate or drop the active dev database
os.environ["DATABASE_URL"] = "sqlite:///./test_suite.db"
