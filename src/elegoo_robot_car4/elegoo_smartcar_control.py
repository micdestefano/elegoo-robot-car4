#!/usr/bin/env python

#  Copyright (c) Michele De Stefano - 2023.

import argparse

import cv2 as cv
import functools as fun
import numpy as np
import pygame as pg
import requests as req

from typing import *

from .car import Car


class GameEngine:

    __head_delta = 10
    __min_speed = 50
    __max_speed = 200
    __dry_run_size = (400,200)

    __move_key_to_cmd = {
        pg.K_UP: fun.partial(Car.forward,speed=__min_speed,lazy=True),
        pg.K_DOWN: fun.partial(Car.backward,speed=__min_speed,lazy=True),
        pg.K_LEFT: fun.partial(Car.left,speed=__min_speed,lazy=True),
        pg.K_RIGHT: fun.partial(Car.right,speed=__min_speed,lazy=True),
        pg.K_a: fun.partial(Car.turn_head,delta=__head_delta,lazy=True),
        pg.K_d: fun.partial(Car.turn_head,delta=-__head_delta,lazy=True),
        pg.K_s: fun.partial(Car.set_head_angle,lazy=True),
        pg.K_m: fun.partial(Car.set_mode,mode=Car.FOLLOW_MODE),
        pg.K_o: fun.partial(Car.set_mode,mode=Car.OBSTACLE_AVOIDANCE_MODE),
        pg.K_l: fun.partial(Car.set_mode,mode=Car.TRACKING_MODE),
        pg.K_q: Car.clear_all_states
    }

    __axis_thr = 0.5
    __small_axis_thr = 0.1

    def __init__(self,robot_ip: str, log: bool = False, dry_run: bool = False):
        self.car_ip = robot_ip
        self.capture_ip = f'http://{self.car_ip}/capture'
        self.dry_run = dry_run
        self.size = self.__capture(size_only=True)
        self.display = pg.display.set_mode(self.size)
        pg.display.set_caption('Elegoo Smart Car Robot v4 controller')

        self.car = Car(ip=self.car_ip,log=log, dry_run=dry_run)
        self.__delta_speed = self.__max_speed - self.__min_speed

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release_resoruces()

    def __capture(self,size_only: bool = False) -> Tuple[int,int]:
        if self.dry_run:
            return self.__dry_run_size
        r = req.get(self.capture_ip)
        frame = np.asarray(bytearray(r.content),dtype=np.int8)
        frame = cv.transpose(cv.cvtColor(cv.imdecode(frame,cv.IMREAD_UNCHANGED),cv.COLOR_BGR2RGB))
        if not size_only:
            # blit it to the display surface.  simple!
            pg.surfarray.blit_array(self.display,frame)
            pg.display.update()
        return frame.shape[:2]

    def run(self) -> None:
        joysticks = {}
        while True:
            self.__capture()
            events = pg.event.get()
            if any([e.type == pg.QUIT for e in events]):
                break

            if self.car.is_far_from_the_ground():
                self.car.stop()
                continue

            joybuttons = []
            for e in events:
                # Handle hotplugging
                if e.type == pg.JOYDEVICEADDED:
                    # This event will be generated when the program starts for every
                    # joystick, filling up the list without needing to create them manually.
                    joy = pg.joystick.Joystick(e.device_index)
                    joysticks[joy.get_instance_id()] = joy

                if e.type == pg.JOYDEVICEREMOVED:
                    del joysticks[e.instance_id]

                if e.type == pg.JOYBUTTONDOWN:
                    joybuttons += [e.button]

            was_pressed = pg.key.get_pressed()
            if was_pressed[pg.K_ESCAPE]:
                break
            move_command_received = False
            for move_key in self.__move_key_to_cmd.keys():
                if was_pressed[move_key]:
                    self.__move_key_to_cmd[move_key](self.car)
                    move_command_received = True
            if not move_command_received:
                for stick in joysticks.values():
                    move_command_received = self.__controller_handler(stick,joybuttons)
            if not move_command_received:
                self.car.stop(lazy=True)
            self.car.move()
            #pg.time.delay(200)

    def __controller_handler(self,stick: pg.joystick.Joystick,buttons: List[int]) -> bool:
        lr_axis = stick.get_axis(0)
        fb_axis = stick.get_axis(1)
        head_axis = stick.get_axis(3)
        num_hats = stick.get_numhats()
        hat = stick.get_hat(0) if num_hats > 0 else None
        # Use right trigger for tuning speed
        speed_axis = 0.5 * (stick.get_axis(5) + 1.0) # Now this is a number in [0,1]
        cur_speed = round(np.clip(self.__min_speed + speed_axis * self.__delta_speed,0,255))

        reset_head_pos = 2 in buttons # 2 is the X button
        move_command_received = (
                abs(lr_axis) > 0.2 or abs(fb_axis) > 0.2 or
                abs(head_axis) > 0.2 or reset_head_pos or
                (num_hats > 0 and (hat[0] != 0 or hat[1] != 0))
        )

        if not move_command_received:
            return move_command_received

        if head_axis < -self.__axis_thr:
            self.car.turn_head(self.__head_delta,lazy=True)
            return move_command_received
        if head_axis > self.__axis_thr:
            self.car.turn_head(-self.__head_delta,lazy=True)
            return move_command_received
        if reset_head_pos:
            self.car.set_head_angle(lazy=True)
            return move_command_received

        if num_hats > 0:
            if hat[0] < 0:
                self.car.left(speed=cur_speed,lazy=True)
                return move_command_received
            if hat[0] > 0:
                self.car.right(speed=cur_speed,lazy=True)
                return move_command_received
            if hat[1] > 0:
                self.car.forward(speed=cur_speed,lazy=True)
                return move_command_received
            if hat[1] < 0:
                self.car.backward(speed=cur_speed,lazy=True)
                return move_command_received

        if abs(lr_axis) < self.__small_axis_thr:
            if fb_axis > self.__axis_thr:
                self.car.backward(speed=cur_speed,lazy=True)
            elif fb_axis < -self.__axis_thr:
                self.car.forward(speed=cur_speed,lazy=True)
            return move_command_received

        if fb_axis > 0:
            if lr_axis < 0:
                self.car.backward_left(speed=cur_speed,lazy=True)
            elif lr_axis > 0:
                self.car.backward_right(speed=cur_speed,lazy=True)
            return move_command_received

        if fb_axis < 0:
            if lr_axis < 0:
                self.car.forward_left(speed=cur_speed,lazy=True)
            elif lr_axis > 0:
                self.car.forward_right(speed=cur_speed,lazy=True)
            return move_command_received

        return move_command_received

    def release_resoruces(self):
        self.car.disconnect()


def main():
    parser = argparse.ArgumentParser(description='Program for remotely controlling Elegoo Smart Car Robot v.4')
    parser.add_argument('robot_ip',type=str,help='Robot IP address')
    parser.add_argument('--log',dest='log',action='store_true',
                        help='Acquired commands are printed to the console. Default: %(default)s')
    parser.add_argument('--dry-run',dest='dry_run',action='store_true',
                        help='Run without sending any command to the car. Default: %(default)s')
    args = parser.parse_args()

    pg.init()

    with GameEngine(args.robot_ip,log=args.log,dry_run=args.dry_run) as engine:
        engine.run()

    pg.quit()


if __name__ == '__main__':
    main()
