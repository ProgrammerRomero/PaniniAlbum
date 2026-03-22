from album import create_app


app = create_app()


if __name__ == "__main__":
    # Development server entry point.
    # Run with: python app.py
    app.run(debug=True)
