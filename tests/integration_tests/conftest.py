#  Copyright (c) Michele De Stefano - 2026.
import json
import re
import socket
import socketserver
import threading
import time
from collections.abc import Generator
from typing import Any, override

import pytest

from elegoo_robot_car4 import Car


class RobotMockServer(socketserver.BaseRequestHandler):
    @override
    def handle(self) -> None:
        self.request.sendall(b"{Heartbeat}{Heartbeat}{ok}{Heartbeat}")
        while True:
            data = self.request.recv(1024).strip()
            if not data:
                break
            commands = re.findall(r"\{.*?\}", data.decode("utf-8"))

            for command in commands:
                response = self.process_command(command)
                if response:
                    self.request.sendall(response.encode("utf-8"))

    @staticmethod
    def process_command(command: str) -> str:
        print(f"Process command: {command}\n")
        cmd = json.loads(command)
        cmd_id = cmd.get("H")
        if cmd_id is None:
            return ""
        cmd_code = cmd.get("N")
        match = re.search(r"\d+", cmd_id)
        code_number = int(match.group(0)) if match else None
        flag = "true" if (code_number and (code_number & 1 == 1)) else "false"
        response_for_sensor_reading = f"{{{cmd_id}_123456}}"
        response_for_check = f"{{{cmd_id}_{flag}}}"
        response_ok = f"{{{cmd_id}_ok}}"
        ok_response_codes = [5, 110]

        if cmd_code in ok_response_codes:
            return response_ok
        elif cmd_code == 21:  # Requested the reading from the ultrasonic sensor
            if cmd["D1"] == 2:  # Requested the distance
                return response_for_sensor_reading
            else:  # == 1 ... Requested an obstacle check
                return response_for_check
        elif cmd_code == 22:
            return response_for_sensor_reading
        elif cmd_code == 23:
            return response_for_check
        elif cmd_code == 1000:  # Requested MPU data
            response_data = {
                "id": cmd_id,
                "t": int(time.time() * 1000),
                "a": [110, 220, 330],  # Quantized values
                "g": [440, 550, 660],  # Quantized values
            }
            return json.dumps(response_data, separators=(",", ":"))
        else:
            # No response is expected
            return ""


@pytest.fixture(scope="session")
def server_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))  # Bind to any address and let the OS assign a port.
        _, port = s.getsockname()
    return port


@pytest.fixture(scope="session")
def mock_robot_server(server_port: int) -> Generator[None, Any, None]:
    mock_server = socketserver.ThreadingTCPServer(
        server_address=("localhost", server_port),
        RequestHandlerClass=RobotMockServer,
    )
    mock_server_thread = threading.Thread(target=mock_server.serve_forever)
    mock_server_thread.daemon = True
    mock_server_thread.start()
    yield
    mock_server.shutdown()


@pytest.fixture(scope="session")
def car(mock_robot_server, server_port: int) -> Generator[Car, Any, None]:
    car = Car(ip="localhost", port=server_port)
    yield car
    car.disconnect()
