import asyncio
import re

from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.sse import sse_client

from google import genai
from google.genai import types as genai_types
import aiohttp
import requests
from dotenv import load_dotenv
import pika
import json

load_dotenv()


class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.gemini = genai.Client()
        self.rabbit_connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
        self.rabbit_channel = self.rabbit_connection.channel()
        self.rabbit_channel.queue_declare(queue="tool_args")
        self.pending_tool_args: dict = {}

    async def connect_to_sse_server(self, server_url: str):
        """Connect to an SSE MCP server.
        
        Args:
            server_url (str): URL of the SSE MCP server.
        """
        # Store the context managers so they stay alive
        self._streams_context = sse_client(url=server_url)
        streams = await self._streams_context.__aenter__()

        self._session_context = ClientSession(*streams)
        self.session: ClientSession = await self._session_context.__aenter__()

        # Initialize
        await self.session.initialize()
        
        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print(f"Connected to SSE MCP Server at {server_url}. Available tools: {[tool.name for tool in tools]}")

    def login_creds(self, data: dict):
        try:
            required_fields = ["email", "password"]
            if not all(field in data for field in required_fields):
                print(f"Missig required fields:")
                return False
            
            response = requests.post("http://localhost:8000/creds_login", json=data)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Error pushing credentials: {e}")
            return False
        
    def signup_creds(self, data: dict):
        try:
            required_fields = ["name", "email", "password", "re_password"]
            if not all(field in data for field in required_fields):
                print(f"Missig required fields:")
                return False
            if data["password"] != data["re_password"]:
                print("Passwords do not match")
                return False
            response = requests.post("http://localhost:8000/creds_signup", json=data)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Error pushing credentials: {e}")
            return False
        
    def project_info(self, data: dict):
        try:
            required_fields = ["project_name", "project_description"]
            if not all(field in data for field in required_fields):
                print(f"Missig required fields:")
                return False
            response = requests.post("http://localhost:8000/create-project", json=data)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Error pushing credentials: {e}")
            return False    
    
    async def connect_to_server(self, server_path_or_url: str):
        """Connect to an MCP server (either stdio or SSE).
        
        Args:
            server_path_or_url (str): Path to the server script or URL of SSE server.
        """
        # Check if the input is a URL (for SSE server)
        url_pattern = re.compile(r'^https?://')
        
        if url_pattern.match(server_path_or_url):
            # It's a URL, connect to SSE server
            await self.connect_to_sse_server(server_path_or_url)
        else:
            # It's a script path, connect to stdio server
            await self.connect_to_stdio_server(server_path_or_url)
    
    async def process_query(self, query: str, previous_messages: list = None) -> tuple[str, list]:
        """Process a query using the MCP server and available tools.
        
        Args:
            query (str): The query to send to the server.
            previous_messages (list, optional): Previous conversation history.

        Returns:
            tuple[str, list]: The response from the server and updated messages.
        """
        if not self.session:
            raise RuntimeError("Client session is not initialized.")
        
        # Get available tools
        response = await self.session.list_tools()
        available_tools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": dict(tool.inputSchema) if tool.inputSchema else {}
        } for tool in response.tools]
        
        return await self._process_query_gemini(query, available_tools, previous_messages)
    
    async def _process_query_gemini(self, query: str, available_tools: list, previous_messages: list = None) -> tuple[str, list]:
        """Process a query using Google's Gemini models."""
        model = "gemini-2.0-flash"
        
        # Convert available_tools to a format suitable for Gemini
        gemini_tools = self._convert_tools_to_gemini_format(available_tools)
        tools = genai_types.Tool(function_declarations=gemini_tools)
        config = genai_types.GenerateContentConfig(tools=[tools])
        
        # Prepare chat history
        chat_history = self._prepare_gemini_chat_history(previous_messages)
        
        chat = self.gemini.chats.create(
            model=model,
            config=config,
            history=chat_history
        )
        
        # Initialize variables for tracking conversation
        final_text = []
        messages = previous_messages.copy() if previous_messages else []
        messages.append({"role": "user", "content": query})
        
        try:
            response = chat.send_message(query)
            
            # Process the response
            final_text, messages = await self._process_gemini_response(
                response, 
                final_text, 
                messages, 
                model, 
                config
            )
                
        except Exception as e:
            final_text.append(f"I encountered an error while processing your request: {str(e)}")
            
        return "\n".join(final_text), messages
    
    def _convert_tools_to_gemini_format(self, available_tools: list) -> list:
        """Convert tools from MCP format to Gemini format."""
        
        # Map JSON schema types to Gemini types
        type_mapping = {
            "number": "NUMBER",
            "integer": "INTEGER",
            "boolean": "BOOLEAN",
            "array": "ARRAY",
            "object": "OBJECT",
        }



        gemini_tools = []
        for tool in available_tools:
            # Create basic tool structure
            function_declaration = {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": {"type": "OBJECT", "properties": {}, "required": []}
            }
            
            # Convert schema if available
            if "input_schema" in tool and tool["input_schema"]:
                schema = tool["input_schema"]
                
                # Add properties from the schema
                if "properties" in schema:
                    for prop_name, prop_details in schema["properties"].items():
                        prop_type = prop_details.get("type", "STRING").upper()
                        prop_type = type_mapping.get(prop_type.lower(), "STRING")
                            
                        property_schema = {"type": prop_type}
                        if "description" in prop_details:
                            property_schema["description"] = prop_details["description"]
                            
                        function_declaration["parameters"]["properties"][prop_name] = property_schema
                        
                # Add required properties
                if "required" in schema:
                    function_declaration["parameters"]["required"] = schema["required"]
                    
            gemini_tools.append(function_declaration)
        return gemini_tools
    
    def _prepare_gemini_chat_history(self, previous_messages: list) -> list:
        """Prepare chat history in Gemini's format."""
        chat_history = []
        if not previous_messages:
            return chat_history
            
        for message in previous_messages:
            if message["role"] == "user" and isinstance(message["content"], str):
                chat_history.append({
                    "role": "user",
                    "parts": [{"text": message["content"]}]
                })
            elif message["role"] == "assistant" and isinstance(message["content"], str):
                chat_history.append({
                    "role": "model",
                    "parts": [{"text": message["content"]}]
                })
        return chat_history
    
    async def _process_gemini_response(self, response, final_text, messages, model, config):
        """Process the response from Gemini, including any function calls."""
        if not hasattr(response, "candidates") or not response.candidates:
            final_text.append("I couldn't generate a proper response.")
            return final_text, messages
            
        candidate = response.candidates[0]
        if not hasattr(candidate, "content") or not hasattr(candidate.content, "parts"):
            final_text.append("I received an incomplete response.")
            return final_text, messages
            
        # Process text and function calls
        for part in candidate.content.parts:
            # Process text part
            if hasattr(part, "text") and part.text:
                final_text.append(part.text)
                
            # Process function call part
            if hasattr(part, "function_call") and part.function_call:
                function_call = part.function_call
                tool_name = function_call.name
                
                # Parse tool arguments
                tool_args = self._parse_gemini_function_args(function_call)

                if tool_name == "signup" :
                    self.signup_creds(tool_args)   
                elif tool_name == "login":
                    self.login_creds(tool_args)
                elif tool_name == "create_project":
                    self.project_info(tool_args)

                # Add function call info to response
                function_call_text = f"I need to call the {tool_name} function to help with your request."
                final_text.append(function_call_text)
                
                # Execute tool call
                try:
                    result = await self.session.call_tool(tool_name, tool_args)
                    
                    # Create a function response and send to Gemini for follow-up
                    final_text, messages = await self._handle_tool_result(
                        tool_name, 
                        function_call, 
                        result, 
                        final_text, 
                        messages,
                        model,
                        config
                    )
                except Exception as e:
                    error_msg = f"Error executing tool {tool_name}: {str(e)}"
                    final_text.append(error_msg)
                
        return final_text, messages
    
    def tool_args_to_queue_in_string(self, tool_args: dict):
            payload = json.dumps(tool_args)
            self.rabbit_channel.basic_publish(exchange="", routing_key="tool_args", body=payload)
    
    def _parse_gemini_function_args(self, function_call):
        """Parse function arguments from Gemini function call."""
        tool_args = {}
        try:
            if hasattr(function_call.args, "items"):
                for k, v in function_call.args.items():
                    for_queue = {k: v}
                    tool_args[k] = v
                    self.tool_args_to_queue_in_string(for_queue)
                
            else:
                # Fallback if it's a string
                args_str = str(function_call.args)
                if args_str.strip():
                    tool_args = json.loads(args_str)
                    
        except Exception as e:
            final_text.append(f"Failed to parse function args: {e} - {type(function_call.args)}")
            
        return tool_args
    
    async def _handle_tool_result(self, tool_name, function_call, result, final_text, messages, model, config):
        """Handle the result of a tool call and get follow-up response."""
        try:
            # Prepare function response
            function_response_part = genai_types.Part.from_function_response(
                name=tool_name,
                response={"result": result.content if hasattr(result, "content") else str(result)},
            )

            # Prepare contents for follow-up
            contents = [
                genai_types.Content(
                    role="model", 
                    parts=[genai_types.Part(function_call=function_call)]
                )
            ]
            
            # Add to messages history                               
            messages.append({
                "role": "assistant", 
                "content": function_call.model_dump_json()
            })

            # Add function response to contents
            contents.append(
                genai_types.Content(
                    role="user", 
                    parts=[function_response_part]
                )
            )
            
            # Add to messages history
            result_content = result.content if hasattr(result, "content") else str(result)                           
            messages.append({
                "role":   "user", 
                "content": {"result": result_content}
            })
           
            # Send function response to get final answer
            follow_up_response = self.gemini.models.generate_content(
                model=model,
                config=config,
                contents=contents,
            )
            
            # Extract text from follow-up response
            if hasattr(follow_up_response, "candidates") and follow_up_response.candidates:
                follow_up_candidate = follow_up_response.candidates[0]
                if (hasattr(follow_up_candidate, "content") and 
                    hasattr(follow_up_candidate.content, "parts")):
                    
                    follow_up_text = ""
                    for follow_up_part in follow_up_candidate.content.parts:
                        if hasattr(follow_up_part, "text"):
                            follow_up_text += follow_up_part.text
                            
                    if follow_up_text:
                        final_text.append(follow_up_text)
                        messages.append({
                            "role": "assistant", 
                            "content": follow_up_text
                        })
                    else:
                        final_text.append("I received the tool results but couldn't generate a follow-up response.")
                        
            else:
                final_text.append("I processed your request but couldn't generate a follow-up response.")
                
        except Exception as e:
            final_text.append(f"I received the tool results but encountered an error: {str(e)}")
            
        return final_text, messages

    async def chat_loop(self):
        """Run an interactive chat loop with the server."""
        previous_messages = []
        print("Type your queries or 'quit' to exit.")
        print("Type 'refresh' to clear conversation history.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                if query.lower() == "quit":
                    break
                
                #  Check if the user wants to refresh conversation (history)
                if query.lower() == "refresh":
                    previous_messages = []
                    print("Conversation history cleared.")
                    continue
            
                response, previous_messages = await self.process_query(query, previous_messages=previous_messages)
                print("\nResponse:", response)
            except Exception as e:
                print("Error:", str(e))

    # def credentials(self, username, password, email):

    async def cleanup(self):
        """Clean up resources."""
        await self.exit_stack.aclose()
        if hasattr(self, '_session_context') and self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if hasattr(self, '_streams_context') and self._streams_context:
            await self._streams_context.__aexit__(None, None, None)

    def get_signup_creds(self):
        return getattr(self, "signup_creds", None)

    def get_login_creds(self):
        return getattr(self, "login_creds", None)

async def run_mcp():
    client = MCPClient()
    try:
        await client.connect_to_server("http://localhost:8000/mcp")
        await client.chat_loop()
    finally:
        await client.cleanup()
        print("\nMCP Client Closed!")


if __name__ == "__main__":
    asyncio.run(run_mcp())