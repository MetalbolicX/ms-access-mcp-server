import fastmcp as fm
import inspect

# Find the server module that handles MCP requests
server_cls = fm.FastMCP
src = inspect.getsource(server_cls)

# Search for tool call handling
for i, line in enumerate(src.split('\n')):
    if 'tool' in line.lower() and ('call' in line.lower() or 'invoke' in line.lower()):
        print(f'{i}: {line}')
