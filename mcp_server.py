from mcp.server import Server
import handler

server = Server("luna-mcp")

@server.tool(name="open_app", description="Open an application by name")
def open_app(app_name: str):
    return handler.open_app(app_name)

@server.tool(name="shutdown", description="Shut down the assistant/system")
def shutdown():
    return handler.shutdown()

@server.tool(name="change_user_name", description="Change the stored user name")
def change_user_name(new_name: str):
    return handler.change_user_name(new_name)

@server.tool(name="change_assistant_name", description="Change the assistant's name")
def change_assistant_name(new_name: str):
    return handler.change_assistant_name(new_name)

@server.tool(name="get_user_name", description="Get the stored user name")
def get_user_name():
    return handler.get_user_name()

@server.tool(name="get_assistant_name", description="Get the assistant's name")
def get_assistant_name():
    return handler.get_assistant_name()

# Add more mappings as needed...

if __name__ == "__main__":
    server.run(port=3001)  # MCP_SERVER_URL points here