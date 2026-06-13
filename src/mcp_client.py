import subprocess
import json
import logging
import sys
from typing import Dict, Any, Optional

logger = logging.getLogger("MCPClient")

class MCPClient:
    def __init__(self, command: str, args: list, env: Optional[Dict[str, str]] = None):
        self.command = command
        self.args = args
        self.env = env
        self.process: Optional[subprocess.Popen] = None
        self._next_id = 1

    def start(self):
        logger.info(f"Starting MCP server subprocess: {self.command} {' '.join(self.args)}")
        
        # Dynamically append Windows shell wrappers if running on Windows
        cmd = self.command
        if sys.platform == "win32" and cmd == "npx":
            cmd = "npx.cmd"

        self.process = subprocess.Popen(
            [cmd] + self.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # Redirect to DEVNULL to prevent OS pipe deadlocks
            env=self.env,
            text=True,
            bufsize=1  # Line buffered
        )
        
        # Perform initialize handshake
        self.initialize()

    def initialize(self):
        init_params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "WellActually-Governance-Client",
                "version": "1.0.0"
            }
        }
        res = self.send_request("initialize", init_params)
        logger.info("MCP Server handshake initialized successfully.")
        
        # Send initialized notification
        self.send_notification("notifications/initialized", {})

    def send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        msg_id = self._next_id
        self._next_id += 1
        
        payload = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method,
            "params": params
        }
        
        data = json.dumps(payload) + "\n"
        self.process.stdin.write(data)
        self.process.stdin.flush()
        
        # Read stdout line-by-line until we get the response matching our msg_id
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise EOFError("MCP server terminated stdout connection prematurely.")
            
            decoded_line = line.strip()
            if not decoded_line:
                continue
            
            try:
                msg = json.loads(decoded_line)
                if "id" in msg and msg["id"] == msg_id:
                    if "error" in msg:
                        raise RuntimeError(msg["error"])
                    return msg.get("result", msg)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON-RPC message: {decoded_line}")

    def send_notification(self, method: str, params: Dict[str, Any]):
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        data = json.dumps(payload) + "\n"
        self.process.stdin.write(data)
        self.process.stdin.flush()

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        res = self.send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        return res

    def close(self):
        if self.process:
            try:
                self.process.stdin.close()
            except Exception:
                pass
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                pass
            logger.info("MCP server process terminated.")
