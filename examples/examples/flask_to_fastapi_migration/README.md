# Flask to FastAPI Migration Example

[![Documentation](https://img.shields.io/badge/docs-graph-sitter.com-blue)](https://graph-sitter.com/tutorials/flask-to-fastapi)

This example demonstrates how to use Graph-sitter to automatically migrate a Flask application to FastAPI. For a complete walkthrough, check out our [tutorial](https://graph-sitter.com/tutorials/flask-to-fastapi).

## What This Example Does

The migration script handles four key transformations:

1. **Updates Imports and Initialization**

   ```python
   # From:
   from flask import Flask

   app = Flask(__name__)

   # To:
   from fastapi import FastAPI

   app = FastAPI()
   ```

1. **Converts Route Decorators**

   ```python
   # From:
   @app.route("/users", methods=["POST"])

   # To:
   @app.post("/users")
   ```

1. **Sets Up Static File Handling**

   ```python
   # Adds:
   from fastapi.staticfiles import StaticFiles

   app.mount("/static", StaticFiles(directory="static"), name="static")
   ```

1. **Updates Template Rendering**

   ```python
   # From:
   return render_template("users.html", users=users)

   # To:
   return Jinja2Templates(directory="templates").TemplateResponse("users.html", context={"users": users}, request=request)
   ```

## Running the Example

```bash
# Install Graph-sitter
pip install graph-sitter

# Run the migration
python run.py
```

The script will process all Python files in the `repo-before` directory and apply the transformations in the correct order.

## Understanding the Code

- `run.py` - The migration script
- `input_repo/` - Sample Flask application to migrate

## Learn More

- [Full Tutorial](https://graph-sitter.com/tutorials/flask-to-fastapi)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Graph-sitter Documentation](https://graph-sitter.com)
