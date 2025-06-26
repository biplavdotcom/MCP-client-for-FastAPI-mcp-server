# FastAPI MCP Server and Clients

This project provides a FastAPI-based server implementing the Model Context Protocol (MCP) and includes example client implementations for interacting with various AI providers like OpenAI, Anthropic, and Google Gemini. The server supports basic user authentication (signup and login).

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Environment Setup](#environment-setup)
- [Running the Server](#running-the-server)
- [Running the Clients](#running-the-clients)
  - [Anthropic Client](#anthropic-client)
  - [OpenAI Client](#openai-client)
  - [Google Gemini Client](#google-gemini-client)
- [Security Notes](#security-notes)
- [Contributing](#contributing)
- [License](#license)

## Features

- **MCP Server:** FastAPI application implementing the Model Context Protocol.
- **User Authentication:** Basic user signup and login functionality (in-memory storage, for demonstration purposes).
- **Multi-AI Provider Clients:** Example clients for:
    - Anthropic (Claude models)
    - OpenAI (GPT models)
    - Google (Gemini models)
- **Interactive Chat:** Clients provide a command-line interface for interactive chat sessions.
- **Tool Use:** Demonstrates how clients can list and call tools exposed by the MCP server.
- **SSE (Server-Sent Events):** Clients connect to the server using SSE for real-time communication.

## Project Structure

```
.
├── .gitignore
├── .python-version      # Specifies Python version (used by pyenv, etc.)
├── README.md            # This file
├── client/              # Contains client implementations
│   ├── client_anthropic.py # Client for Anthropic (Claude)
│   ├── client_gemini.py    # Client for Google (Gemini)
│   ├── client_openai.py    # Client for OpenAI (GPT)
│   └── mcp_client.log      # Log file for client activities (example)
├── main.py              # Main FastAPI server application
├── models/              # Pydantic models
│   └── user.py          # User model for authentication
├── pyproject.toml       # Project metadata and dependencies for Poetry/uv
└── uv.lock              # Lock file for uv (alternative to requirements.txt)
```

## Prerequisites

- Python 3.8+
- `uv` (Python package manager, recommended) or `pip`
- API keys for the AI services you intend to use (Anthropic, OpenAI, Google).

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/biplavdotcom/MCP-client-for-fastapi-mcp-server.git
    cd MCP-client-for-fastapi-mcp-server
    ```

2.  **Install `uv` (if you don't have it):**
    ```bash
    pip install uv
    ```

3.  **Create and activate a virtual environment using `uv`:**
    ```bash
    uv venv  # Creates a .venv directory
    ```
    -   On Windows:
        ```bash
        .venv\Scripts\activate
        ```
    -   On Unix/macOS:
        ```bash
        source .venv/bin/activate
        ```

4.  **Install dependencies using `uv`:**
    ```bash
    uv pip install -r requirements.txt  # If requirements.txt exists
    # Or, if using pyproject.toml with uv/Poetry:
    uv pip install .
    ```
    *(Note: The original README mentioned `requirements.txt`, but the repo structure suggests `pyproject.toml` is primary. If `requirements.txt` is not present or up-to-date, generate it with `uv pip freeze > requirements.txt` or install directly from `pyproject.toml`)*

## Environment Setup

Create a `.env` file in the **root** directory of the project (alongside `main.py` and the `client/` directory). The clients (`client_anthropic.py`, `client_openai.py`, `client_gemini.py`) load this `.env` file.

```env
# .env

# Required for client/client_anthropic.py
ANTHROPIC_API_KEY="your_anthropic_api_key"

# Required for client/client_openai.py
OPENAI_API_KEY="your_openai_api_key"

# Required for client/client_gemini.py
# Note: The client_gemini.py uses genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
# Ensure your environment variable is named GOOGLE_API_KEY or update the client code.
GOOGLE_API_KEY="your_google_api_key"
```

**Important:**
- Ensure the `.env` file is in the project's root directory, not inside the `client/` directory, as `python-dotenv` loads it from the current working directory or its parents.
- Add `.env` to your `.gitignore` file to prevent committing your API keys.

## Running the Server

Start the FastAPI server using `uvicorn` (which `uv run` can manage):

```bash
uv run main:app --reload
# Or directly with uvicorn:
# uvicorn main:app --reload
```

The server will typically be available at `http://127.0.0.1:8000`. The MCP endpoint will be at `http://127.0.0.1:8000/mcp`.

## Running the Clients

Each client connects to the MCP server, lists available tools, and then interacts with a specific AI provider, using the MCP server to facilitate tool calls if requested by the AI.

Make sure the FastAPI server is running before starting any client.

### Anthropic Client

-   Uses the Anthropic API (e.g., Claude models like `claude-3-5-sonnet-20241022`).
-   Supports tool use by declaring server-provided tools to the Anthropic API.

To run the Anthropic client:

```bash
uv run python client/client_anthropic.py
```

### OpenAI Client

-   Uses the OpenAI API (e.g., GPT models like `gpt-4o-mini`).
-   Supports tool use by passing server-provided tool schemas to the OpenAI API.

To run the OpenAI client:

```bash
uv run python client/client_openai.py
```

### Google Gemini Client

-   Uses the Google Generative AI API (e.g., Gemini models like `gemini-2.0-flash`).
-   Converts MCP tool schemas into a format compatible with Gemini's function calling.
-   Manages chat history and tool call/result sequences.

To run the Google Gemini client:

```bash
uv run python client/client_gemini.py
```

All clients provide an interactive command-line interface. Type your queries and press Enter. Type `quit` to exit. The Gemini and OpenAI clients also support a `refresh` command to clear the conversation history.

## Security Notes

This project is a demonstration and includes simplified implementations for clarity. For production environments, consider the following:

-   **User Authentication:**
    -   **Database:** Use a robust database (e.g., PostgreSQL, MySQL) instead of an in-memory list for user storage.
    -   **Password Hashing:** Securely hash passwords using strong algorithms like bcrypt or Argon2. Never store plain-text passwords.
    -   **Session Management:** Implement secure session management (e.g., using JWTs or server-side sessions with secure cookies).
-   **API Key Management:**
    -   Store API keys securely (e.g., using a secrets manager like HashiCorp Vault, AWS Secrets Manager, or Google Cloud Secret Manager) instead of just `.env` files in production.
    -   Restrict API key permissions to the minimum necessary.
-   **Input Validation:**
    -   Rigorously validate and sanitize all user inputs on both client and server sides to prevent injection attacks (XSS, SQLi, etc.).
    -   Validate data types, lengths, and formats.
-   **HTTPS:** Always use HTTPS in production to encrypt data in transit.
-   **Rate Limiting:** Implement rate limiting on API endpoints to prevent abuse.
-   **Error Handling:** Implement comprehensive error handling that does not leak sensitive information.
-   **Dependency Management:** Keep dependencies up-to-date and regularly scan for vulnerabilities.
-   **Logging and Monitoring:** Implement robust logging and monitoring to detect and respond to security incidents.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
Some areas for potential contribution:
- Adding more sophisticated error handling.
- Implementing more robust user authentication.
- Expanding the toolset available through the MCP server.
- Adding clients for other AI providers.
- Writing unit and integration tests.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details (if one is added to the repository, otherwise assume MIT as per original README).
