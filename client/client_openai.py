import asyncio
import sys
import json
import os
import re

from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession
# from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

from anthropic import Anthropic
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

class MCPClient:
    def __init__(self):
        self.session = None
        self.exit_stack = AsyncExitStack()
        # self.anthropic = Anthropic()
        self.openai = OpenAI(api_key = os.environ.get("OPENAI_API_KEY"))

    async def connect_to_sse_server(self, server_url: str):
        """Connect to an SSE MCP server."""
        print(f"Connecting to SSE MCP server at {server_url}")

        self._streams_context = sse_client(url=server_url)
        streams = await self._streams_context.__aenter__()

        self._session_context = ClientSession(*streams)
        self.session = await self._session_context.__aenter__()

        # Initialize
        await self.session.initialize()
        
        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print(f"Connected to SSE MCP Server at {server_url}. Available tools: {[tool.name for tool in tools]}")

    async def connect_to_server(self, server_path_or_url: str):
        """Connect to an MCP server (either stdio or SSE)."""
        # Check if the input is a URL (for SSE server)
        # url_pattern = re.compile(r'^https?://')
        
        # if url_pattern.match(server_path_or_url):
        #     # It's a URL, connect to SSE server
        #     await self.connect_to_sse_server(server_path_or_url)
        # else:
        #     # It's a script path, connect to stdio server
        #     await self.connect_to_stdio_server(server_path_or_url)
        await self.connect_to_sse_server(server_path_or_url)

    async def process_query(self, query: str, previous_messages: list = None) -> tuple[str, list]:
        """Process a query using the MCP server and available tools."""
        model = "gpt-4o-mini"

        if not self.session:
            raise RuntimeError("Client session is not initialized.")
        
        messages = []
        if previous_messages:
            messages.extend(previous_messages)

        messages.append( 
            {
                "role": "user",
                "content": query
            }
        )
        
        response = await self.session.list_tools()
        # available_tools = [{
        #     "name": tool.name,
        #     "description": tool.description,
        #     "input_schema": dict(tool.inputSchema) if tool.inputSchema else {}
        #      } for tool in response.tools]
        
        available_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                }
            } for tool in response.tools]
        
        # Initialize Claude API call
        # print(f"Sending query to {model}...")
        response = self.openai.chat.completions.create(
            model=model,
            messages=messages,
            tools=available_tools,
            tool_choice = "auto",
            max_tokens=1000
        )

        # Process response and handle tool calls
        final_text = []
        assistant_message_content = []
        message = response.choices[0].message
        # for content in response.choices[0].message:
        #     if content.type == 'text':
        #         final_text.append(content.text)
        #         assistant_message_content.append(content)
        #     elif content.type == 'tool_use':
        #         tool_name = content.name
        #         tool_args = content.input

        #         # Execute tool call
        #         print(f"Calling tool {tool_name} with args {tool_args}...")
        #         result = await self.session.call_tool(tool_name, tool_args)
        #         final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")
                
        #         assistant_message_content.append(content)
        #         messages.append({
        #             "role": "assistant",
        #             "content": assistant_message_content
        #         })
        #         messages.append({
        #             "role": "user",
        #             "content": [
        #                 {
        #                     "type": "tool_result",
        #                     "tool_use_id": content.id,
        #                     "content": result.content
        #                 }
        #             ]
        #         })

        #         # Get next response from Claude
        #         next_response = self.openai.chat.completions.create(
        #             model=model,
        #             messages=messages,
        #             tools=available_tools,
        #             max_tokens=1000
        #         )
            
        #         final_text.append(next_response.choices[0].message.content)
        #         messages.append({
        #             "role": "assistant",
        #             "content": next_response.choices[0].message.content
        #         })
        if message.tool_calls:
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                # Execute tool call
                print(f"Calling tool {tool_name}...")
                result = await self.session.call_tool(tool_name, tool_args)

                # Add tool call and result to messages
                messages.append({
                    "role": "assistant",
                    "tool_calls": [tool_call.model_dump()]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result.content
                })

                # Get next response from OpenAI
                next_response = self.openai.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=available_tools,
                    max_tokens=1000
                )
                final_text.append(next_response.choices[0].message.content)
                messages.append({
                    "role": "assistant",
                    "content": next_response.choices[0].message.content
                })

        else:
            # Normal assistant response
            final_text.append(message.content)
            messages.append({
                "role": "assistant",
                "content": message.content
            })

        return "\n".join(final_text), messages
    
    async def chat_loop(self):
        """Run an interactive chat loop with the server."""
        previous_messages = []
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                if query.lower() == "quit":
                    break
                
                #  Check if the user wants to refresh conversation (history)
                if query.lower() == "refresh":
                    previous_messages = []
            
                response, previous_messages = await self.process_query(query, previous_messages=previous_messages)
                print("\nResponse:", response)
            except Exception as e:
                print("Error:", str(e))

    async def clenup(self):
        """Clean up resources."""
        await self.exit_stack.aclose()
        if hasattr(self, '_session_context') and self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if hasattr(self, '_streams_context') and self._streams_context:
            await self._streams_context.__aexit__(None, None, None)


async def main():
    client = MCPClient()
    try:
        await client.connect_to_server("http://localhost:8000/mcp")
        await client.chat_loop()
    finally:
        await client.clenup()
        print("\nMCP Client Closed!")


if __name__ == "__main__":
    asyncio.run(main())