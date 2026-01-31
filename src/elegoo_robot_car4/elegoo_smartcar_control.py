#  Copyright (c) Michele De Stefano - 2023.

import argparse
import functools as fun
from collections.abc import Callable
from typing import Any

import cv2 as cv
import numpy as np
import pygame as pg
from ultralytics.engine.results import Results

from .__init__ import __version__
from .car import Car
from .person_follower import PersonFollower


class GameEngine:
    __joysticks: dict[int, pg.joystick.JoystickType]
    __head_delta: int = 10
    __min_speed: int = 50
    __max_speed: int = 200
    __dry_run: bool
    __dry_run_size: tuple[int, int] = (400, 200)
    __autonomous_mode: bool

    __key_to_move_cmd: dict[int, Callable[[Car], Any]] = {
        pg.K_UP: fun.partial(Car.forward, speed=__min_speed, lazy=True),
        pg.K_DOWN: fun.partial(Car.backward, speed=__min_speed, lazy=True),
        pg.K_LEFT: fun.partial(Car.left, speed=__min_speed, lazy=True),
        pg.K_RIGHT: fun.partial(Car.right, speed=__min_speed, lazy=True),
        pg.K_a: fun.partial(Car.turn_head, delta=__head_delta, lazy=True),
        pg.K_d: fun.partial(Car.turn_head, delta=-__head_delta, lazy=True),
        pg.K_s: fun.partial(Car.set_head_angle, lazy=True),
    }

    __axis_thr: float = 0.5
    __small_axis_thr: float = 0.1

    __car: Car

    __last_track_results: list[Results]

    __person_follower: PersonFollower
    __run_person_follower: bool

    def __init__(self, robot_ip: str, log: bool = False, dry_run: bool = False):
        """
        Constructor.

        Args:
            robot_ip:   IP address of the robot.

            log:        Set this to True if you want to activate logging.

            dry_run:    Set this to True for debugging purpose (no socket call
                        will be actually made).
        """
        self.__joysticks = {}
        self.__dry_run = dry_run
        self.__autonomous_mode = False
        self.__run_person_follower = False
        self.__car = Car(ip=robot_ip, log=log, dry_run=dry_run)
        self.__last_track_results = []
        # capture shape (height, width), OpenCV format
        capture_shape = np.array(
            self.__dry_run_size if dry_run else self.__car.capture().shape[:2]
        )
        # pygame requires frames in (width, height) format
        display_size = self.__dry_run_size if dry_run else capture_shape[::-1]
        self.__person_follower = PersonFollower(
            car=self.__car, frame_shape_hw=capture_shape
        )
        self.__display = pg.display.set_mode(display_size)
        pg.display.set_caption("Elegoo Smart Robot Car v4.0 controller")

        self.__delta_speed = self.__max_speed - self.__min_speed

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release_resources()

    def __display_new_frame(self) -> None:
        if self.__dry_run:
            return
        frame = self.__car.capture()
        frame = self.__process_frame(frame)
        # blit it to the display surface.  simple!
        pg.surfarray.blit_array(self.__display, frame)
        pg.display.update()

    def __process_frame(self, frame: np.ndarray) -> np.ndarray:
        if self.__car.vision_tracking_is_on:
            self.__last_track_results = self.__car.track(
                frame,
                classes=[0],
                conf=0.5,
                max_det=2,
                verbose=False,
                persist=True,
            )
            for result in self.__last_track_results:
                frame = result.plot(img=frame)
        else:
            self.__last_track_results = []
        # Returned frame must be ready to be consumed by pygame
        frame = cv.transpose(cv.cvtColor(frame, cv.COLOR_BGR2RGB))
        return frame

    def run(self) -> None:
        """
        Runs the game loop, translating player commands to the robot.
        """

        while True:
            self.__display_new_frame()
            events = pg.event.get()
            if any([e.type == pg.QUIT for e in events]):
                break

            if self.__car.is_far_from_the_ground():
                self.__car.stop()
                continue

            joystick_buttons = self.__detect_relevant_events(events)

            keyboard_player_actions = self.__handle_keyboard_player_actions()
            if keyboard_player_actions["command_received"] == "finish":
                break

            move_command_received = keyboard_player_actions[
                "command_received"
            ] == "movement" or self.__handle_controller_player_actions(
                joystick_buttons
            )

            if not self.__autonomous_mode:
                if not move_command_received:
                    self.__car.stop(lazy=True)
                self.__car.move()

            if keyboard_player_actions["command_received"] == "terminal":
                self.__handle_terminal_input()

            if self.__run_person_follower:
                self.__person_follower.follow(self.__last_track_results)

    def __detect_relevant_events(self, events: list[pg.Event]) -> list[int]:
        joystick_buttons = []
        for e in events:
            # Handle hotplugging
            if e.type == pg.JOYDEVICEADDED:
                # This event will be generated for every joystick when the
                # program starts, filling up the list without needing to
                # create them manually.
                joy = pg.joystick.Joystick(e.device_index)
                self.__joysticks[joy.get_instance_id()] = joy

            if e.type == pg.JOYDEVICEREMOVED:
                del self.__joysticks[e.instance_id]

            if e.type == pg.JOYBUTTONDOWN:
                joystick_buttons += [e.button]
        return joystick_buttons

    def __handle_keyboard_player_actions(self) -> dict[str, int | str | None]:
        retval: dict[str, int | str | None] = {
            "command_received": None,
            "key": None,
        }
        was_pressed = pg.key.get_pressed()
        if was_pressed[pg.K_ESCAPE]:
            retval["key"] = pg.K_ESCAPE
            retval["command_received"] = "finish"
        elif was_pressed[pg.K_t]:
            retval["key"] = pg.K_t
            retval["command_received"] = "terminal"
        else:
            for key_cmd in self.__key_to_move_cmd:
                if was_pressed[key_cmd]:
                    self.__key_to_move_cmd[key_cmd](self.__car)
                    retval["command_received"] = "movement"
                    retval["key"] = key_cmd
                    break
        return retval

    def __handle_controller_player_actions(self, buttons: list[int]) -> bool:
        command_received = False
        for stick in self.__joysticks.values():
            lr_axis = stick.get_axis(0)
            fb_axis = stick.get_axis(1)
            head_axis = stick.get_axis(3)
            num_hats = stick.get_numhats()
            hat = stick.get_hat(0) if num_hats > 0 else None
            # Use right trigger for tuning speed
            speed_axis = 0.5 * (
                stick.get_axis(5) + 1.0
            )  # Now this is a number in [0,1]
            cur_speed = round(
                np.clip(
                    self.__min_speed + speed_axis * self.__delta_speed,
                    a_min=0,
                    a_max=255,
                )
            )

            reset_head_pos = 2 in buttons  # 2 is the X button
            move_command_received = (
                abs(lr_axis) > 0.2
                or abs(fb_axis) > 0.2
                or abs(head_axis) > 0.2
                or reset_head_pos
                or (num_hats > 0 and (hat[0] != 0 or hat[1] != 0))
            )

            if not move_command_received:
                return move_command_received

            if head_axis < -self.__axis_thr:
                self.__car.turn_head(self.__head_delta, lazy=True)
                return move_command_received
            if head_axis > self.__axis_thr:
                self.__car.turn_head(-self.__head_delta, lazy=True)
                return move_command_received
            if reset_head_pos:
                self.__car.set_head_angle(lazy=True)
                return move_command_received

            if num_hats > 0:
                if hat[0] < 0:
                    self.__car.left(speed=cur_speed, lazy=True)
                    return move_command_received
                if hat[0] > 0:
                    self.__car.right(speed=cur_speed, lazy=True)
                    return move_command_received
                if hat[1] > 0:
                    self.__car.forward(speed=cur_speed, lazy=True)
                    return move_command_received
                if hat[1] < 0:
                    self.__car.backward(speed=cur_speed, lazy=True)
                    return move_command_received

            if abs(lr_axis) < self.__small_axis_thr:
                if fb_axis > self.__axis_thr:
                    self.__car.backward(speed=cur_speed, lazy=True)
                elif fb_axis < -self.__axis_thr:
                    self.__car.forward(speed=cur_speed, lazy=True)
                return move_command_received

            if fb_axis > 0:
                if lr_axis < 0:
                    self.__car.backward_left(speed=cur_speed, lazy=True)
                elif lr_axis > 0:
                    self.__car.backward_right(speed=cur_speed, lazy=True)
                return move_command_received

            if fb_axis < 0:
                if lr_axis < 0:
                    self.__car.forward_left(speed=cur_speed, lazy=True)
                elif lr_axis > 0:
                    self.__car.forward_right(speed=cur_speed, lazy=True)
                return move_command_received

            command_received |= move_command_received

        return command_received

    def __handle_terminal_input(self) -> None:
        print("Options:")
        print("========\n")
        print("0 - Clear all states")
        print(f"{Car.TRACKING_MODE} - Activate line tracking mode")
        print(
            f"{Car.OBSTACLE_AVOIDANCE_MODE} - Activate obstacle avoidance mode"
        )
        print(f"{Car.FOLLOW_MODE} - Activate (ultrasonic) follow mode")
        print("4 - Toggle person tracking mode")
        print("5 - Toggle person tracking and following mode")
        print()

        retry_input = True
        user_choice = -1
        while retry_input:
            try:
                user_choice = int(input("Enter your choice: "))
                retry_input = not (0 <= user_choice <= 5)
                if retry_input:
                    print("Please enter a number between 0 and 5")
            except Exception:
                print("Please enter a number between 0 and 5")

        if user_choice == 0:
            self.__autonomous_mode = False
            self.__run_person_follower = False
            self.__car.clear_all_states()
            if self.__car.vision_tracking_is_on:
                self.__car.toggle_vision_tracking()
        elif user_choice == 4:
            self.__autonomous_mode = False
            self.__run_person_follower = False
            self.__car.toggle_vision_tracking()
        elif user_choice == 5:
            self.__autonomous_mode = not self.__autonomous_mode
            self.__run_person_follower = not self.__run_person_follower
            toggle_vision_tracking = (
                not self.__car.vision_tracking_is_on
                and self.__run_person_follower
            ) or (
                not self.__run_person_follower
                and self.__car.vision_tracking_is_on
            )
            if toggle_vision_tracking:
                self.__car.toggle_vision_tracking()
        else:
            self.__autonomous_mode = True
            self.__car.set_mode(user_choice)

    def release_resources(self):
        self.__car.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Program for remotely controlling Elegoo Smart "
        "Robot Car v4.0"
    )
    parser.add_argument(
        "--robot-ip",
        dest="robot_ip",
        type=str,
        default=None,
        help="Robot IP address.",
    )
    parser.add_argument(
        "--log",
        dest="log",
        action="store_true",
        help="Acquired commands are printed to the console. "
        "Default: %(default)s.",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Run without sending any command to the car. "
        "Default: %(default)s.",
    )
    parser.add_argument(
        "-v",
        "--version",
        dest="version_requested",
        action="store_true",
        help="Print the version and exit.",
    )
    args = parser.parse_args()

    if args.version_requested:
        print(f"Version: {__version__}")
        return

    if not args.robot_ip:
        print("Specify a robot IP address!")
        exit(1)

    pg.init()

    with GameEngine(
        args.robot_ip, log=args.log, dry_run=args.dry_run
    ) as engine:
        engine.run()

    pg.quit()
