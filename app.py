from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

from album import create_app


app = create_app()


if __name__ == "__main__":
    # Development server entry point.
    # Run with: python app.py
    app.run(debug=True)
