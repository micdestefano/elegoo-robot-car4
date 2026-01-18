#  Copyright (c) Michele De Stefano - 2023.
import json
import numpy as np
import re
import scipy.integrate
import socket

from collections import deque
from typing import *


class Car:
    """
    Controller of the Elegoo Smart Car Robot v. 4.

    WARNING: Sometimes it is needed to sleep between different method calls, otherwise
             the robot starts not responding on the socket.

    :author: Michele De Stefano
    """

    TRACKING_MODE = 1
    OBSTACLE_AVOIDANCE_MODE = 2
    FOLLOW_MODE = 3
    __IR_LEFT = 0
    __IR_MIDDLE = 1
    __IR_RIGHT = 2

    __no_response_cmds = ['stop','fw','bw','l','r','fl','fr','bl','br']
    __heartbeat_re = re.compile('\{Heartbeat\}')
    __ok_re = re.compile('\{ok\}')

    __num_quant_steps = 1 << 16
    __accel_quantum = 4.0 / __num_quant_steps # +/- 2g, quantized with 16 bit (it is 1 / 16384)
    __gyro_quantum = 500. / __num_quant_steps # +/- 250 deg/s quantized with 16 bit (it is about 1 / 131)

    def __init__(self,ip: str = '192.168.4.1', port: int = 100,
                 log: bool = False, dry_run: bool = False):
        """
        Initializes the connection with the car.

        :param ip:      IP address (numeric or symbolic) of the car.
        :param port:    Listening port on the car.
        :param log:     Put this to True if you want to see logging information.
        :param dry_run: Put this to True if you want to simulate commands without execution.
        """
        self.state = 'stop'
        self.__log = log
        self.__dry_run = dry_run
        self.__cmd_queue = deque()
        self.__recv_msg_queue = ''
        self.__head_angle = 0
        self.__a_offsets = np.zeros(3)
        self.__g_offsets = np.zeros(3)
        # Ultrasonic regression coefficients for sensor -> real measurement conversion
        self.__ultrasonic_q, self.__ultrasonic_m = -0.37779223, 1.26030353
        if not dry_run:
            self.socket = socket.socket()
            # Set a timeout of 2 seconds for all the blocking operations on this socket
            self.socket.settimeout(2)
            self.socket.connect((ip, port))
            self.__compute_mpu_offsets()
            self.set_head_angle()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def disconnect(self) -> None:
        """
        Closes the connection with the robot car.
        """
        try:
            self.socket.close()
        except:
            pass

    def request_mpu_data(self) -> str:
        """
        Sends the request for MPU data.

        :return: The ID of the sent command.
        """
        id = f'MPU_Request_{np.random.randint(0,1 << 32)}'
        cmd = {'H': id, 'N': 1000}
        self.__send_cmd(cmd)
        return id

    def receive_mpu_data(self, id_str: str) -> dict:
        """
        Waits for MPU data returned by the robot car (this is a blocking operation).
        Call this only if you have previously called request_mpu_data.

        :param id_str:  The string ID of the request command (value returned by request_mpu_data).

        :return: A dictionary with the MPU data. The dictionary is composed as follows:

        {
            'id': <the string ID of the request>,
            't': <the acquisition time in seconds>,
            'a': [ax, ay, az], # The three components of the acceleration (as fraction of g)
            'g': [wx, wy, wz] # The three angular velocities (in degrees per second) around the three axes
        }
        """
        expected_pattern = f'{{"id":"{id_str}",.+]}}'
        data = json.loads(self.__recv_until_confirmation(expected_pattern))
        data['t'] *= 0.001 # Convert to seconds
        data['a'] = [x*self.__accel_quantum for x in data['a']]
        data['g'] = [x*self.__gyro_quantum for x in data['g']]
        if self.__log:
            print(f'Retrieved MPU data: {data}')
        return data

    def get_mpu_data(self) -> dict:
        """
        Convenience method that combines a call to request_mpu_data and receive_mpu_data.

        :return: The dictionary with MPU data (see documentation of receive_mpu_data).
        """
        return self.receive_mpu_data(self.request_mpu_data())

    def __compute_mpu_offsets(self):
        if self.__log:
            print('Computing MPU offsets ...')
        accelerations = []
        omegas = []
        for _ in range(30):
            d = self.get_mpu_data()
            accelerations += [d['a']]
            omegas += [d['g']]
        self.__a_offsets = np.mean(accelerations,axis=0)
        self.__g_offsets = np.mean(omegas,axis=0)
        if self.__log:
            print(f'acceleration offsets: {self.__a_offsets}')
            print(f'gyro offsets: {self.__g_offsets}')

    def get_ultrasonic_value(self) -> float:
        """
        Returns the reading of the ultrasonic sensor.

        :return: The reading (in cm) of the ultrasonic sensor. The reading is clipped to 150cm directly
                 by the onboard software.
        """
        id =  f'Ultrasonic_Value_Request_{np.random.randint(0,1 << 32)}'
        cmd = {'H': id , 'N': 21, 'D1': 2}
        self.__send_cmd(cmd)
        pattern = f'{{{id}_(\d+)}}'
        recv_message = self.__recv_until_confirmation(pattern)
        m = re.search(pattern, recv_message)
        sensor_value = float(m.group(1))
        real_distance = self.__ultrasonic_q + self.__ultrasonic_m * sensor_value
        if self.__log:
            print(f'Ultrasonic distance: {real_distance}')
        return real_distance

    def check_obstacle(self) -> bool:
        """
        Check if there is an obstacle in front of the ultrasonic sensor.

        :return: True if there is an obstacle. False otherwise.
        """
        id = f'Check_Obstacle_{np.random.randint(0,1 << 32)}'
        cmd = {'H': id , 'N': 21, 'D1': 1}
        self.__send_cmd(cmd)
        pattern = f'{{{id}_(true|false)}}'
        recv_message = self.__recv_until_confirmation(pattern)
        m = re.search(pattern, recv_message)
        return 'true' == m.group(1)

    def get_ir_left(self) -> int:
        """
        Retrieves the reading of the left IR sensor.

        :return: The value read by the left IR sensor.
        """
        return self.__get_ir_value(self.__IR_LEFT)

    def get_ir_middle(self) -> int:
        """
        Retrieves the reading of the middle IR sensor.

        :return: The value read by the middle IR sensor.
        """
        return self.__get_ir_value(self.__IR_MIDDLE)

    def get_ir_right(self) -> int:
        """
        Retrieves the reading of the right IR sensor.

        :return: The value read by the right IR sensor.
        """
        return self.__get_ir_value(self.__IR_RIGHT)

    def get_ir_all(self) -> dict:
        """
        Convenience method for retrieving the readings of the three IR sensors at once.

        :return: A dictionary with the following structure:

        {
            'left': <left reading>,
            'middle': <middle reading>,
            'right': <right reading>
        }
        """
        l = self.get_ir_left()
        m = self.get_ir_middle()
        r = self.get_ir_right()
        return {'left': l, 'middle': m, 'right': r}

    def is_far_from_the_ground(self) -> bool:
        """
        Checks if the car is far from the ground.

        :return: True if the car is far from the ground. False otherwise.
                 The result is deduced from the IR sensor readings.
        """
        id = f'Leaves_the_ground_{np.random.randint(0,1 << 32)}'
        cmd = {'H': id , 'N': 23}
        self.__send_cmd(cmd)
        pattern = f'{{{id}_(true|false)}}'
        recv_message = self.__recv_until_confirmation(pattern)
        m = re.search(pattern, recv_message)
        return 'true' == m.group(1)

    def __get_ir_value(self,sensor: int) -> int:
        id = f'IR_{sensor}_{np.random.randint(0,1 << 32)}'
        cmd = {'H':id , 'N': 22, 'D1': sensor}
        self.__send_cmd(cmd)
        pattern = f'{{{id}_(\d+)}}'
        recv_message = self.__recv_until_confirmation(pattern)
        m = re.search(pattern, recv_message)
        return int(m.group(1))

    def set_mode(self,mode: int) -> None:
        """
        Changes the operation mode of the car.

        :param mode: An integer flag for switching the operation mode. See the available public
                     constants in this class.
        """
        cmd = {'N': 101, 'D1': mode}
        self.__send_cmd(cmd)

    def clear_all_states(self) -> None:
        """
        Clears all states in execution.
        """
        id = f'clear_all_states_{np.random.randint(0,1 << 32)}'
        cmd = {'H': id, 'N': 110}
        self.__send_cmd(cmd)
        expected_pattern = f'{{{id}_ok}}'
        self.__recv_until_confirmation(expected_pattern)

    def forward(self,speed: int = 50, lazy: bool = False) -> None:
        """
        Moves forward.

        :param speed: Speed [0,255] of the car.
        :param lazy: If True, you need to call the move method for performing the action.
        """
        cmd = {'H': 'fw', 'N': 102, 'D1': 1, 'D2': speed}
        self.__process_cmd(cmd,lazy)

    def backward(self,speed: int = 50, lazy: bool = False) -> None:
        """
        Moves backward.

        :param speed: Speed [0,255] of the car.
        :param lazy: If True, you need to call the move method for performing the action.
        """
        cmd = {'H': 'bw', 'N': 102, 'D1': 2, 'D2': speed}
        self.__process_cmd(cmd,lazy)

    def left(self,speed: int = 50, lazy: bool = False) -> None:
        """
        Turns left in-place.

        :param speed: Speed [0,255] of the car.
        :param lazy: If True, you need to call the move method for performing the action.
        """
        cmd = {'H': 'l', 'N': 102, 'D1': 3, 'D2': speed}
        self.__process_cmd(cmd,lazy)

    def right(self,speed: int = 50, lazy: bool = False) -> None:
        """
        Turns right in-place.

        :param speed: Speed [0,255] of the car.
        :param lazy: If True, you need to call the move method for performing the action.
        """
        cmd = {'H': 'r', 'N': 102, 'D1': 4, 'D2': speed}
        self.__process_cmd(cmd,lazy)

    def turn_by(self,angle: int) -> None:
        """
        Turns in-place by a specified angle. Speed is hardcoded to a value that
        allows the most accurate rotation control

        :param angle: The rotation angle in degrees. Positive angle is counterclockwise.
        """
        if self.__log:
            print('====== TURNING ======')
        speed = 50 # Hardcoded because higher speed does not allow accurate rotation control
        direction_flag = 'l' if angle > 0 else 'r'
        direction = 3 if angle > 0 else 4
        turn_cmd = {'H': direction_flag, 'N': 102, 'D1': direction, 'D2': speed}
        mpu_data = self.get_mpu_data()
        t0 = mpu_data['t']
        wz0 = mpu_data['g'][-1] - self.__g_offsets[-1]
        alpha = 0
        angle = abs(angle)
        self.__process_cmd(turn_cmd,lazy=False)
        while abs(alpha) < angle:
            mpu_data = self.get_mpu_data()
            t = mpu_data['t']
            delta_t = t - t0
            wz = mpu_data['g'][-1] - self.__g_offsets[-1]
            delta_angle = scipy.integrate.trapezoid([wz0,wz],dx=delta_t)
            alpha += delta_angle
            if self.__log:
                print(f'delta_t = {delta_t}')
                print(f'wz0 = {wz0}')
                print(f'wz = {wz}')
                print(f'delta angle = {delta_angle}')
                print(f'alpha = {alpha}')
            t0 = t
            wz0 = wz
        self.stop(lazy=False)
        if self.__log:
            print('====== END TURNING ======')

    def forward_left(self, speed: int = 50, lazy: bool = False) -> None:
        """
        Turns left while moving forward.

        :param speed: Speed [0,255] of the car.
        :param lazy: If True, you need to call the move method for performing the action.
        """
        cmd = {'H': 'fl', 'N': 102, 'D1': 5, 'D2': speed}
        self.__process_cmd(cmd,lazy)

    def backward_left(self, speed: int = 50, lazy: bool = False) -> None:
        """
        Turns left while moving backward.

        :param speed: Speed [0,255] of the car.
        :param lazy: If True, you need to call the move method for performing the action.
        """
        cmd = {'H': 'bl', 'N': 102, 'D1': 6, 'D2': speed}
        self.__process_cmd(cmd,lazy)

    def forward_right(self, speed: int = 50, lazy: bool = False) -> None:
        """
        Turns right while moving forward.

        :param speed: Speed [0,255] of the car.
        :param lazy: If True, you need to call the move method for performing the action.
        """
        cmd = {'H': 'fr', 'N': 102, 'D1': 7, 'D2': speed}
        self.__process_cmd(cmd,lazy)

    def backward_right(self, speed: int = 50, lazy: bool = False) -> None:
        """
        Turns right while moving backward.

        :param speed: Speed [0,255] of the car.
        :param lazy: If True, you need to call the move method for performing the action.
        """
        cmd = {'H': 'br', 'N': 102, 'D1': 8, 'D2': speed}
        self.__process_cmd(cmd,lazy)

    def stop(self, lazy: bool = False) -> None:
        """
        Stops car's wheels.

        :param lazy: If True, you need to call the move method for performing the action.
        """
        cmd = {'H': 'stop', 'N': 100}
        self.__process_cmd(cmd,lazy)

    def forward_until(self, has_to_stop: Callable[[],bool], speed: int = 50) -> None:
        """
        Moves forward until a stopping condition is met.

        :param has_to_stop:  A callable that returns True when the robot has to stop.
        :param speed: Speed [0,255] of the car.
        """
        self.forward(speed)
        while not has_to_stop(): ...
        self.stop()

    def turn_head(self,delta: int, lazy: bool = False) -> None:
        """
        Moves head by a delta-angle.

        :param delta: The delta-angle. Positive is counterclockwise.
        :param lazy: If True, you need to call the move method for performing the action.
        """
        self.set_head_angle(self.__head_angle + delta,lazy)

    def set_head_angle(self,angle: int = 0, lazy: bool = False) -> None:
        """
        Set head angle to what specified.

        :param angle: The desired head rotation angle, in [-80,80]. 0 = front, 80 = left, -80 = right.
        :param lazy: If True, you need to call the move method for performing the action.
        """
        angle = int(np.clip(angle,-80,80))
        head_angle = angle + 90 # For the robot, 0 = right, 90 = front, 180 = left.
        cmd = {'H':'set_head','N':5,'D1':1,'D2':head_angle}
        self.__process_cmd(cmd,lazy)

    def get_head_angle(self) -> int:
        """
        Retrieves the current head rotation angle.

        :return: The head rotation angle, in [-80,80]. 0 = front, -80 = right, 80 = left.
        """
        return self.__head_angle

    def move(self) -> None:
        """
        Applies all the lazy movement commands previously issued.
        Lazy commands are stacked into a queue and then the queue is progressively depleted.
        This behavior is handy for interactive remote control (video-game style).

        Warning: If more than one movement command is in the queue then the car is stopped and
        the queue is cleared. This is because the care is not able to deal with more than one
        command at the same time.
        """
        num_cmd_received = len(self.__cmd_queue)
        if num_cmd_received == 0:
            self.stop()
        elif num_cmd_received > 1:
            self.__cmd_queue.clear()
        while len(self.__cmd_queue) > 0:
            new_state_cmd = self.__cmd_queue.popleft()
            self.__change_state_to(new_state_cmd)

    def find_best_front_direction(self, scan_range: Tuple[int,int] = (-80, 80)) -> Tuple[int,float]:
        """
        Scans the surroundings in front of the robot and returns the best
        movement direction angle.

        :param scan_range:  The front angles to scan. They are going to be
                            scanned with a 10 degrees step. The widest
                            allowed range is (-80,80) (the default).
                            If you specify a range outside this one, it will
                            be clipped to the maximum allowed.

        :return: A pair (best_angle, best_distance). The best angle is the best movement angle
                 with respect to robot front. The returned angle is in the [-80,80] range, where
                 positive angle is counterclockwise. 0 is robot front.
        """
        scan_angles = range(
            np.clip(scan_range[0],-80,80),
            np.clip(scan_range[1],-80,80) + 10,
            10
        )
        distances = []
        for cur_angle in scan_angles:
            self.set_head_angle(cur_angle)
            try_getting_obstacle_dist = True
            obstacle_dist = None
            while try_getting_obstacle_dist:
                try:
                    obstacle_dist = self.get_ultrasonic_value()
                    try_getting_obstacle_dist = False
                except TimeoutError:
                    pass
            distances += [obstacle_dist]
        distances = np.array(distances)
        ind_best_dir = round(np.argwhere(distances == distances.max()).ravel().mean())
        self.set_head_angle(0)
        return scan_angles[ind_best_dir],distances[ind_best_dir]

    def turn_to_best_direction(self, angle: Union[int,None] = None) -> None:
        """
        Turns the car to the best direction. The best direction is the one with
        maximum obstacle distance.

        :param angle:   The best direction angle. None means that the angle must
                        be found.
        """
        if angle is None:
            angle, dist = self.find_best_front_direction()
        num_trials = 0
        while abs(angle) > 10 and num_trials < 4:
            num_front_trials = 0
            while abs(angle) > 10 and num_front_trials < 3:
                self.turn_by(angle)
                num_front_trials += 1
                angle, dist = self.find_best_front_direction(scan_range=(-30, 30))
            if abs(angle) > 10 or dist < 30:
                self.turn_by(90)
            num_trials += 1
        if self.__log:
            print(f'Best distance up to now: {dist}')
            print(f'Best angle found: {angle}')

    def __change_state_to(self,state_cmd: dict):
        new_state = state_cmd['H']
        wait_for_confirmation = new_state not in self.__no_response_cmds
        set_head_cmd = new_state == 'set_head'
        if 'D2' in state_cmd:
            new_state += f'_{str(state_cmd["D2"])}'
        state_cmd['H'] = new_state
        if new_state == self.state:
            return
        self.__send_cmd(state_cmd)
        if wait_for_confirmation:
            self.__recv_until_confirmation('{' + new_state + '_ok}')
        if set_head_cmd:
            self.__head_angle = state_cmd["D2"] - 90
        self.state = new_state

    def __send_cmd(self,cmd_data: dict) -> None:
        json_cmd = json.dumps(cmd_data).encode()
        if not self.__dry_run:
            self.socket.sendall(json_cmd)
        if self.__log:
            print(f'Sent command: {json_cmd}')

    def __recv_until_confirmation(self,expected_confirmation: str) -> str:
        if self.__dry_run:
            return ''
        pattern = re.compile(expected_confirmation)
        m = pattern.search(self.__recv_msg_queue)
        while not m:
            self.__recv_msg_queue += self.socket.recv(4096).decode()
            # Remove all received {Heartbeat} messages
            self.__recv_msg_queue = self.__heartbeat_re.sub('',self.__recv_msg_queue)
            # Remove all received {ok} messages
            self.__recv_msg_queue = self.__ok_re.sub('',self.__recv_msg_queue)
            m = pattern.search(self.__recv_msg_queue)
            if self.__log:
                print(f'Received message: {self.__recv_msg_queue}')
        self.__recv_msg_queue = pattern.sub('',self.__recv_msg_queue)
        return m.group(0)

    def __process_cmd(self,cmd: dict, lazy: bool) -> None:
        if lazy:
            self.__cmd_queue += [cmd]
            return
        self.__send_cmd(cmd)
        new_state = cmd['H']
        wait_for_confirmation = new_state not in self.__no_response_cmds
        if wait_for_confirmation:
            self.__recv_until_confirmation('{' + new_state + '_ok}')
